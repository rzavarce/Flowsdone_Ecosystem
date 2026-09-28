"""Semantic Text Splitter (Flowsdone): structure-aware semantic chunking.

Langflow's native "Semantic Text Splitter" (LangChain SemanticChunker) only
splits by meaning: it has no size limits (one run left most of a 28-page
manual in a single chunk), splits sentences on every "." (a table of
contents with dot leaders took all the breakpoints) and its threshold field
can't go past 2.0 in the editor, so "percentile" can't be set to 90-95.

This component chunks Markdown (the output of "Convertir a Markdown", or any
text) in four steps:

1. Sections: split by headings ("#".."###" by default), so a chunk never
   mixes two sections. Text without headings is one section.
2. Units: inside a section, tables and code blocks are kept whole, each list
   item is a unit, and paragraphs are split into sentences with a
   Spanish-aware splitter (¿…? ¡…!, abbreviations like "p. ej.", numbers
   like "1.000").
3. Meaning: sections longer than the maximum size are cut where the meaning
   changes (distance between consecutive units' embeddings above a
   threshold). Short sections need no embeddings - it's cheaper.
4. Size: pieces are packed up to the maximum size, oversized units are split
   (tables by rows, repeating their header) and chunks under the minimum are
   merged with a neighbour of the same section.

Each chunk starts with its heading path ("Planes y precios > Pro — 99 €/mes")
and keeps the document's metadata plus `section`, `chunk_index` and
`chunk_chars`. The embeddings input is optional: without it, steps 1, 2 and 4
still apply.
"""

from __future__ import annotations

import math
import re

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import BoolInput, DropdownInput, FloatInput, HandleInput, IntInput, Output
from langflow.schema import Data

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
_FENCE = re.compile(r"^\s*(```|~~~)")
# A sentence ends at . ! ? … followed by space and something that starts a
# sentence (uppercase, digit, opening ¿ ¡ quote or bracket).
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+(?=[¿¡\"“«(\[]?[A-ZÁÉÍÓÚÜÑ0-9])")
_ABBREVIATIONS = (
    "p. ej.", "P. ej.", "EE. UU.", "etc.", "Sr.", "Sra.", "Srta.", "Dr.", "Dra.", "Ud.", "Uds.", "núm.", "Núm.",
    "pág.", "págs.", "aprox.", "art.", "cap.", "tel.", "Tel.", "e.g.", "i.e.", "vs.", "approx.", "No.",
)
_PROTECTED_DOT = "․"  # one dot leader: never a sentence end
_INLINE_MARKS = re.compile(r"[*_`]+")

THRESHOLD_TYPES = ["percentile", "standard_deviation", "interquartile", "gradient"]


# Plain classes, not dataclasses: Langflow executes component code in its own
# namespace, where dataclasses can't resolve their module.
class Section:
    """A block of text under one heading path.

    Attributes:
        path (list[str]): Headings from the top level down to this section.
        body (str): Text of the section, without its heading line.
    """

    __slots__ = ("path", "body")

    def __init__(self, path: list[str], body: str) -> None:
        self.path = path
        self.body = body


class Unit:
    """The smallest piece chunking works with.

    Attributes:
        text (str): The piece.
        kind (str): "sentence", "item", "table" or "code".
        block (int): Paragraph it belongs to: sentences of one paragraph are
            joined with a space, different blocks with a line break.
    """

    __slots__ = ("text", "kind", "block")

    def __init__(self, text: str, kind: str, block: int) -> None:
        self.text = text
        self.kind = kind
        self.block = block


class Chunk:
    """A finished chunk, before it becomes a Data object.

    Attributes:
        path (list[str]): Heading path of its section.
        units (list[Unit]): Its units, in order.
    """

    __slots__ = ("path", "units")

    def __init__(self, path: list[str], units: list[Unit] | None = None) -> None:
        self.path = path
        self.units = units if units is not None else []

    @property
    def body(self) -> str:
        """Text of the chunk, joining units as they were in the document."""
        return join_units(self.units)


def clean_heading(text: str) -> str:
    """Heading text without Markdown emphasis marks.

    Args:
        text (str): Raw heading text.

    Returns:
        str: Plain heading.
    """
    return _INLINE_MARKS.sub("", text).strip()


def split_sections(text: str, max_level: int = 3) -> list[Section]:
    """Split Markdown into sections by headings up to `max_level`.

    Deeper headings stay as content lines. Headings inside code fences are
    ignored.

    Args:
        text (str): Markdown.
        max_level (int): Deepest heading level that opens a section.

    Returns:
        list[Section]: Sections in order (empty ones included, so a parent
        heading with no text of its own still gives its path to children).
    """
    sections: list[Section] = []
    path: list[str] = []
    lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
        match = None if in_fence else _HEADING.match(line)
        if match and len(match.group(1)) <= max_level:
            sections.append(Section(path=list(path), body="\n".join(lines).strip()))
            level = len(match.group(1))
            path = path[: level - 1] + [clean_heading(match.group(2))]
            lines = []
        else:
            lines.append(line)
    sections.append(Section(path=list(path), body="\n".join(lines).strip()))
    return [s for s in sections if s.body or s.path]


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences (Spanish and English aware).

    Args:
        paragraph (str): One paragraph, on a single line.

    Returns:
        list[str]: Its sentences.
    """
    protected = paragraph
    for abbreviation in _ABBREVIATIONS:
        protected = protected.replace(abbreviation, abbreviation.replace(".", _PROTECTED_DOT))
    return [s.replace(_PROTECTED_DOT, ".").strip() for s in _SENTENCE_END.split(protected) if s.strip()]


def split_units(body: str) -> list[Unit]:
    """Split a section body into units: tables, code blocks, list items, sentences.

    Consecutive text lines form a paragraph (PDF text often breaks lines
    mid-sentence), which is then split into sentences.

    Args:
        body (str): Section text.

    Returns:
        list[Unit]: Units in order.
    """
    units: list[Unit] = []
    block = 0
    paragraph: list[str] = []
    lines = body.splitlines()

    def flush_paragraph() -> None:
        nonlocal block
        if paragraph:
            for sentence in split_sentences(" ".join(p.strip() for p in paragraph)):
                units.append(Unit(sentence, "sentence", block))
            paragraph.clear()
            block += 1

    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE.match(line):
            flush_paragraph()
            fence = [line]
            i += 1
            while i < len(lines):
                fence.append(lines[i])
                i += 1
                if _FENCE.match(fence[-1]):
                    break
            units.append(Unit("\n".join(fence), "code", block))
            block += 1
            continue
        stripped = line.strip()
        if stripped.startswith("|"):
            flush_paragraph()
            table = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table.append(lines[i].strip())
                i += 1
            units.append(Unit("\n".join(table), "table", block))
            block += 1
            continue
        if _LIST_ITEM.match(line):
            flush_paragraph()
            item = [stripped]
            i += 1
            # Indented continuation lines belong to the item.
            while i < len(lines) and lines[i].startswith(("  ", "\t")) and lines[i].strip() and not _LIST_ITEM.match(lines[i]):
                item.append(lines[i].strip())
                i += 1
            units.append(Unit(" ".join(item), "item", block))
            block += 1
            continue
        if not stripped:
            flush_paragraph()
        else:
            paragraph.append(stripped)
        i += 1
    flush_paragraph()
    return units


def join_units(units: list[Unit]) -> str:
    """Join units back into text: same paragraph with spaces, else line breaks.

    Args:
        units (list[Unit]): Units in order.

    Returns:
        str: The text.
    """
    text = ""
    for n, unit in enumerate(units):
        if n:
            text += " " if unit.block == units[n - 1].block and unit.kind == "sentence" else "\n"
        text += unit.text
    return text


def breakpoints(distances: list[float], threshold_type: str, amount: float) -> set[int]:
    """Where the meaning changes: indexes i whose distance to unit i+1 is high.

    Args:
        distances (list[float]): Cosine distance between consecutive units.
        threshold_type (str): One of THRESHOLD_TYPES.
        amount (float): Percentile (0-100) for "percentile"/"gradient";
            number of deviations / IQRs for the others.

    Returns:
        set[int]: Indexes to break after. Empty with fewer than 3 distances.
    """
    if len(distances) < 3:
        return set()
    values = [float(d) for d in distances]
    mean = sum(values) / len(values)
    if threshold_type == "standard_deviation":
        threshold = mean + amount * math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    elif threshold_type == "interquartile":
        threshold = mean + amount * (percentile(values, 75) - percentile(values, 25))
    elif threshold_type == "gradient":
        values = gradient(values)
        threshold = percentile(values, amount)
    else:
        threshold = percentile(values, amount)
    return {i for i, value in enumerate(values) if value > threshold}


def percentile(values: list[float], amount: float) -> float:
    """Percentile with linear interpolation (same result as numpy's default).

    Args:
        values (list[float]): Non-empty values.
        amount (float): Percentile, 0-100.

    Returns:
        float: The percentile.
    """
    ordered = sorted(values)
    position = (len(ordered) - 1) * min(max(amount, 0.0), 100.0) / 100
    low = math.floor(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def gradient(values: list[float]) -> list[float]:
    """Discrete gradient: central differences inside, one-sided at the ends.

    Args:
        values (list[float]): At least two values.

    Returns:
        list[float]: Gradient of each point (as numpy.gradient).
    """
    last = len(values) - 1
    return [
        values[1] - values[0] if i == 0
        else values[last] - values[last - 1] if i == last
        else (values[i + 1] - values[i - 1]) / 2
        for i in range(len(values))
    ]


def cosine_distance(a: list[float], b: list[float]) -> float:
    """1 - cosine similarity (0 = same meaning).

    Args:
        a (list[float]): Vector.
        b (list[float]): Vector.

    Returns:
        float: The distance; 1.0 if a vector is zero.
    """
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return 1.0 - (sum(x * y for x, y in zip(a, b)) / norm) if norm else 1.0


def split_oversized(unit: Unit, max_chars: int) -> list[Unit]:
    """Split a unit longer than `max_chars`.

    Tables are split by rows, repeating the header; anything else by words.

    Args:
        unit (Unit): The unit.
        max_chars (int): Maximum size.

    Returns:
        list[Unit]: Pieces no longer than `max_chars` (a single word or row
        longer than that is kept whole).
    """
    if len(unit.text) <= max_chars:
        return [unit]
    if unit.kind == "table":
        rows = unit.text.splitlines()
        header = rows[:2] if len(rows) > 1 and set(rows[1].replace("|", "").strip()) <= set("-: ") else rows[:1]
        pieces, current = [], list(header)
        for row in rows[len(header):]:
            if len(current) > len(header) and len("\n".join(current + [row])) > max_chars:
                pieces.append(current)
                current = list(header)
            current.append(row)
        pieces.append(current)
        return [Unit("\n".join(p), "table", unit.block) for p in pieces]
    pieces, current = [], ""
    for word in unit.text.split():
        if current and len(current) + 1 + len(word) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    pieces.append(current)
    return [Unit(p, unit.kind, unit.block) for p in pieces]


def pack(path: list[str], units: list[Unit], breaks: set[int], min_chars: int, max_chars: int) -> list[Chunk]:
    """Group a section's units into chunks.

    A chunk ends before it would pass `max_chars`, or at a meaning
    breakpoint once it has `min_chars`; then a chunk still under
    `min_chars` (e.g. the last one) is merged with its neighbour when the
    result fits.

    Args:
        path (list[str]): Heading path of the section.
        units (list[Unit]): Its units.
        breaks (set[int]): Indexes of `units` to break after.
        min_chars (int): Minimum chunk size (soft).
        max_chars (int): Maximum chunk size.

    Returns:
        list[Chunk]: Chunks in order.
    """
    chunks: list[Chunk] = []
    current = Chunk(path)
    for index, unit in enumerate(units):
        for piece in split_oversized(unit, max_chars):
            if current.units and len(join_units(current.units + [piece])) > max_chars:
                chunks.append(current)
                current = Chunk(path)
            current.units.append(piece)
        # A meaning break only ends the chunk once it's big enough.
        if index in breaks and current.units and len(current.body) >= min_chars:
            chunks.append(current)
            current = Chunk(path)
    if current.units:
        chunks.append(current)

    merged: list[Chunk] = []
    for chunk in chunks:
        if merged and (len(chunk.body) < min_chars or len(merged[-1].body) < min_chars) \
                and len(join_units(merged[-1].units + chunk.units)) <= max_chars:
            merged[-1].units.extend(chunk.units)
        else:
            merged.append(chunk)
    return merged


class FlowsdoneSemanticSplitter(Component):
    display_name = "Semantic Text Splitter (Flowsdone)"
    description = (
        "Trocea Markdown por secciones y por significado, con tamaño mínimo y máximo, sin partir "
        "tablas ni frases, y con el título de la sección al inicio de cada fragmento."
    )
    icon = "scissors-line-dashed"
    name = "FlowsdoneSemanticSplitter"

    inputs = [
        HandleInput(
            name="data_inputs",
            display_name="Documentos",
            input_types=["Data", "DataFrame"],
            is_list=True,
            required=True,
            info="Documentos en Markdown (salida de 'Convertir a Markdown') o texto.",
        ),
        HandleInput(
            name="embeddings",
            display_name="Embeddings",
            input_types=["Embeddings"],
            required=False,
            info="Para cortar por significado las secciones largas. Sin él, se trocea solo por secciones y tamaño.",
        ),
        IntInput(
            name="max_chunk_chars",
            display_name="Tamaño máximo (caracteres)",
            value=1500,
            info="Ningún fragmento lo supera (salvo una sola fila de tabla o palabra más larga).",
        ),
        IntInput(
            name="min_chunk_chars",
            display_name="Tamaño mínimo (caracteres)",
            value=200,
            info="Los fragmentos más cortos se unen a un vecino de la misma sección si caben.",
        ),
        DropdownInput(
            name="breakpoint_threshold_type",
            display_name="Tipo de umbral",
            options=THRESHOLD_TYPES,
            value="percentile",
            advanced=True,
            info=(
                "Cómo se decide que el significado cambia. percentile: corta en las distancias por encima "
                "de ese percentil (90 = el 10 % más alto). standard_deviation / interquartile: media + N."
            ),
        ),
        FloatInput(
            name="breakpoint_threshold_amount",
            display_name="Umbral",
            value=90.0,
            range_spec=RangeSpec(min=0, max=100, step=0.5),
            advanced=True,
            info="percentile/gradient: 0-100 (recomendado 85-95). standard_deviation/interquartile: 0.5-3.",
        ),
        IntInput(
            name="buffer_size",
            display_name="Frases de contexto",
            value=1,
            advanced=True,
            info="Frases vecinas que se incluyen al comparar significado; hace los cortes más estables.",
        ),
        IntInput(
            name="heading_levels",
            display_name="Niveles de título",
            value=3,
            advanced=True,
            info="Títulos que abren sección: 3 = '#', '##' y '###'.",
        ),
        BoolInput(
            name="add_context_header",
            display_name="Título de sección en cada fragmento",
            value=True,
            advanced=True,
            info="Empieza cada fragmento con su ruta de títulos (ej. 'Planes y precios > Pro').",
        ),
    ]

    outputs = [Output(display_name="Chunks", name="chunks", method="split")]

    def _documents(self) -> list[Data]:
        """Flatten the inputs (Data, lists, DataFrames) into Data objects."""
        documents: list[Data] = []
        inputs = self.data_inputs if isinstance(self.data_inputs, list) else [self.data_inputs]
        for item in inputs:
            if isinstance(item, Data):
                documents.append(item)
            elif isinstance(item, list):
                documents.extend(d for d in item if isinstance(d, Data))
            elif hasattr(item, "to_data_list"):  # DataFrame
                documents.extend(item.to_data_list())
        return documents

    def _semantic_breaks(self, units: list[Unit]) -> list[float]:
        """Cosine distances between consecutive units, with `buffer_size` context."""
        buffer = max(0, int(self.buffer_size or 0))
        windows = [
            " ".join(u.text for u in units[max(0, i - buffer): i + buffer + 1]) for i in range(len(units))
        ]
        vectors = self.embeddings.embed_documents(windows)
        return [cosine_distance(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]

    def _chunk_document(self, text: str, title: str) -> tuple[list[Chunk], int]:
        """Chunk one document; returns its chunks and the embedding calls made."""
        max_chars = max(100, int(self.max_chunk_chars or 1500))
        min_chars = max(0, min(int(self.min_chunk_chars or 0), max_chars // 2))
        sections = split_sections(text, int(self.heading_levels or 3))
        plans: list[tuple[Section, list[Unit], list[float] | None]] = []
        embedded = 0
        for section in sections:
            units = split_units(section.body)
            if not units:
                continue
            distances = None
            if getattr(self, "embeddings", None) and len(section.body) > max_chars and len(units) > 2:
                distances = self._semantic_breaks(units)
                embedded += len(units)
            plans.append((section, units, distances))

        # One threshold per document, from all its long sections' distances.
        all_distances = [d for _, _, ds in plans if ds for d in ds]
        amount = float(self.breakpoint_threshold_amount if self.breakpoint_threshold_amount is not None else 90)
        threshold_type = self.breakpoint_threshold_type or "percentile"
        chunks: list[Chunk] = []
        offset = 0
        global_breaks = breakpoints(all_distances, threshold_type, amount)
        for section, units, distances in plans:
            breaks = set()
            if distances:
                breaks = {i - offset for i in global_breaks if offset <= i < offset + len(distances)}
                offset += len(distances)
            path = section.path or ([title] if title else [])
            chunks.extend(pack(path, units, breaks, min_chars, max_chars))
        return chunks, embedded

    def split(self) -> list[Data]:
        """Chunk every input document."""
        documents = self._documents()
        result: list[Data] = []
        embedded = 0
        for document in documents:
            values = dict(document.data)
            text_key = getattr(document, "text_key", "text") or "text"
            text = str(values.pop(text_key, "") or "")
            if not text.strip():
                continue
            chunks, calls = self._chunk_document(text, str(values.get("title") or ""))
            embedded += calls
            for index, chunk in enumerate(chunks):
                section = " > ".join(chunk.path)
                body = chunk.body
                chunk_text = f"{section}\n\n{body}" if self.add_context_header and section else body
                result.append(Data(data={
                    **values,
                    "text": chunk_text,
                    "section": section,
                    "chunk_index": index,
                    "chunk_chars": len(body),
                }))
        sizes = [r.data["chunk_chars"] for r in result] or [0]
        self.status = (
            f"{len(result)} fragmentos de {len(documents)} documentos; tamaño medio {sum(sizes) // len(sizes)} "
            f"caracteres (mín. {min(sizes)}, máx. {max(sizes)}); {embedded} frases comparadas por significado"
        )
        return result
