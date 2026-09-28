"""Convertir a Markdown (Flowsdone): any document or web page to clean Markdown.

Chunking for search works best on text that keeps its structure (headings,
lists, tables in rows) and carries no layout noise. A PDF only says where to
draw each letter: extracted as plain text it loses its headings, its tables
come out one cell per line, and every page repeats its header and footer.
This component turns every source into Markdown first, so one splitter
("Semantic Text Splitter (Flowsdone)") works the same for all of them:

- Files: md, txt, html, pdf, docx, pptx, xlsx, csv, json - converted with
  MarkItDown (Microsoft, MIT). PDFs come out as text in reading order but
  without headings (a PDF doesn't record them); scanned PDFs (no text layer)
  and images are not supported and are reported instead of loaded empty.
- Content from other nodes (e.g. the URL component in "HTML" format, or any
  text): HTML is converted without its navigation, header, footer, forms and
  scripts; anything else is taken as Markdown/text.

Cleaning (on by default): drops tables of contents (dot-leader lines, and in
PDF/DOCX/PPTX the block after an "Índice"/"Contents" title), lines repeated
on every page (headers, footers, page numbers - PDF and PPTX only), HTML
comments, in-page anchor links ("Saltar al contenido") and extra blank
lines. A YAML front matter block becomes metadata (its `title` is used).

Each document keeps `source` (page URL or file name, without the timestamp
Langflow adds to uploads), `title` and `file_type`.
"""

from __future__ import annotations

import io
import os
import re
from collections import Counter
from typing import Any

from bs4 import BeautifulSoup
from langflow.custom import Component
from langflow.io import BoolInput, FileInput, HandleInput, Output, StrInput
from langflow.schema import Data

FILE_TYPES = ["md", "markdown", "txt", "html", "htm", "pdf", "docx", "pptx", "xlsx", "csv", "json"]
# Page furniture repeats on every page; body text almost never does.
PAGED_TYPES = {"pdf", "pptx"}
_NOISE_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "button", "iframe", "template"]
_UPLOAD_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_")
_DOT_LEADER = re.compile(r"(?:\.\s*){4,}\d*\s*$|(?:\.\s){4,}")
_PAGE_NUMBER = re.compile(r"^\s*(?:p[áa]g(?:ina)?\.?\s*)?\d{1,4}(?:\s*/\s*\d{1,4})?\s*$", re.IGNORECASE)
_MIN_TEXT_CHARS = 20
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# A line that is only a link to an anchor of the same page ("Saltar al contenido").
_ANCHOR_LINK_LINE = re.compile(r"^\s*(?:[*-]\s*)?\[[^\]]*\]\(#[^)]*\)\s*$")
_TOC_TITLE = re.compile(
    r"^\s*#*\s*(?:índice|indice|contenido|contenidos|tabla de contenidos?|sumario|table of contents|contents)\s*:?\s*$",
    re.IGNORECASE,
)
_TOC_ENTRY_MAX_CHARS = 80


def clean_html(html: str) -> str:
    """Remove navigation, header, footer, forms, scripts and hidden elements.

    Args:
        html (str): A web page.

    Returns:
        str: The HTML of its readable content.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    for tag in soup.select('[aria-hidden="true"], [hidden]'):
        tag.decompose()
    return str(soup)


def looks_like_html(text: str) -> bool:
    """Whether a text is an HTML page or fragment rather than Markdown/text.

    Args:
        text (str): The text.

    Returns:
        bool: True if it starts like HTML or is mostly tags.
    """
    head = text.lstrip()[:500].lower()
    if head.startswith(("<!doctype html", "<html")) or "<body" in head:
        return True
    return len(re.findall(r"</?(?:div|p|h[1-6]|ul|li|section|span|a|table)\b", text[:5000], re.IGNORECASE)) >= 5


def split_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Separate a YAML front matter block (flat "key: value" lines) from the text.

    Args:
        text (str): Markdown that may start with "---".

    Returns:
        tuple[dict[str, str], str]: The metadata (quotes stripped) and the rest.
    """
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() and not key.startswith((" ", "\t")):
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("-").lstrip("\n")


def remove_markup_noise(text: str) -> str:
    """Drop HTML comments and lines that are only in-page anchor links.

    Args:
        text (str): Markdown.

    Returns:
        str: Without that noise.
    """
    text = _HTML_COMMENT.sub("", text)
    return "\n".join(line for line in text.splitlines() if not _ANCHOR_LINK_LINE.match(line))


def remove_toc_block(text: str) -> str:
    """Drop a table of contents: the short lines after an "Índice"/"Contents" title.

    Converted PDFs lose the dot leaders, so the entries arrive as plain short
    lines. The block ends at the first line that reads like body text (long,
    or ending in a sentence mark).

    Args:
        text (str): Markdown of a document.

    Returns:
        str: Without its table of contents.
    """
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if not _TOC_TITLE.match(line):
            continue
        end = start + 1
        while end < len(lines):
            stripped = lines[end].strip()
            if stripped and (len(stripped) > _TOC_ENTRY_MAX_CHARS or stripped.endswith((".", ":", ";", "?", "!"))):
                break
            end += 1
        # Keep the last short line before the body: it is usually the first chapter's title.
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        return "\n".join(lines[:start] + lines[end - 1:])
    return text


def remove_toc_lines(text: str) -> str:
    """Drop table-of-contents lines ("Planes y precios . . . . . 12").

    Args:
        text (str): Markdown.

    Returns:
        str: Without dot-leader lines.
    """
    return "\n".join(line for line in text.splitlines() if not _DOT_LEADER.search(line))


def remove_repeated_lines(text: str, min_repeats: int = 4, min_chars: int = 4) -> str:
    """Drop page furniture: lines repeated many times, and bare page numbers.

    Table rows and headings are never dropped, nor lines shorter than
    `min_chars` (a table cell like "Sí" may legitimately repeat).

    Args:
        text (str): Markdown of a paged document (PDF, PPTX).
        min_repeats (int): Occurrences from which a line is furniture.
        min_chars (int): Shorter lines are always kept.

    Returns:
        str: The text without those lines.
    """
    lines = text.splitlines()
    counts = Counter(line.strip() for line in lines if line.strip())
    kept = []
    for line in lines:
        stripped = line.strip()
        furniture = (
            counts[stripped] >= min_repeats
            and len(stripped) >= min_chars
            and not stripped.startswith(("|", "#"))
        )
        if furniture or (stripped and _PAGE_NUMBER.match(stripped)):
            continue
        kept.append(line)
    return "\n".join(kept)


def join_broken_lines(text: str) -> str:
    """Rejoin sentences a PDF broke at the end of each printed line.

    PDF text comes one printed line at a time, often with a blank line in
    between. A line that doesn't end a sentence is joined with the next one
    when that one continues it (starts lowercase or with a digit or
    punctuation). Headings, list items and table rows are left alone.

    Args:
        text (str): Markdown converted from a PDF.

    Returns:
        str: The text with its paragraphs rejoined.
    """
    lines = text.splitlines()
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        while True:
            stripped = line.rstrip()
            j = i + 1
            while j < len(lines) and not lines[j].strip() and j - i <= 2:
                j += 1
            if j >= len(lines) or not stripped or stripped.endswith((".", ":", ";", "!", "?", "…")) \
                    or stripped.lstrip().startswith(("#", "|", "- ", "* ")):
                break
            following = lines[j].strip()
            if not following or not (following[0].islower() or following[0].isdigit() or following[0] in ",;)(«\"'"):
                break
            if following.startswith(("|", "#", "- ", "* ")):
                break
            line = f"{stripped} {following}"
            i = j
        result.append(line)
        i += 1
    return "\n".join(result)


def collapse_blank_lines(text: str) -> str:
    """Trim trailing spaces and leave at most one blank line in a row.

    Args:
        text (str): Text.

    Returns:
        str: The tidied text.
    """
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_markdown(text: str, file_type: str) -> str:
    """Apply the cleaning steps that fit a document type.

    Args:
        text (str): Converted Markdown.
        file_type (str): Extension without dot ("pdf", "html"...).

    Returns:
        str: Clean Markdown.
    """
    text = remove_markup_noise(remove_toc_lines(text))
    if file_type in PAGED_TYPES:
        text = remove_repeated_lines(text)
    if file_type in PAGED_TYPES | {"docx"}:
        text = remove_toc_block(text)
    if file_type == "pdf":
        text = join_broken_lines(text)
    return collapse_blank_lines(text)


def source_from_path(path: str) -> str:
    """A file's source name: its base name without Langflow's upload timestamp.

    Args:
        path (str): Stored file path.

    Returns:
        str: E.g. "manual-comercial.pdf".
    """
    return _UPLOAD_PREFIX.sub("", os.path.basename(path))


def first_heading(markdown: str) -> str:
    """The first heading of a Markdown text, if any.

    Args:
        markdown (str): Markdown.

    Returns:
        str: Heading text, or "".
    """
    match = re.search(r"^#{1,6}\s+(.+?)\s*#*\s*$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else ""


class DocumentToMarkdown(Component):
    display_name = "Convertir a Markdown (Flowsdone)"
    description = (
        "Convierte archivos (pdf, docx, pptx, xlsx, html, md, txt…) o páginas web a Markdown limpio, "
        "conservando títulos, listas y tablas, para trocearlos después."
    )
    icon = "file-text"
    name = "DocumentToMarkdown"

    inputs = [
        FileInput(
            name="files",
            display_name="Archivos",
            file_types=FILE_TYPES,
            list=True,
            required=False,
            info="pdf (con texto, no escaneados), docx, pptx, xlsx, csv, html, md, txt, json.",
        ),
        HandleInput(
            name="data_inputs",
            display_name="Contenido",
            input_types=["Data", "Message"],
            is_list=True,
            required=False,
            info="Contenido de otros nodos, p. ej. el nodo URL en formato HTML. El HTML se convierte sin menú ni pie.",
        ),
        StrInput(
            name="source_name",
            display_name="Nombre de la fuente (archivos)",
            required=False,
            info=(
                "Opcional. Fuente con la que se guardan los documentos de los archivos subidos. Fijo, "
                "para que al subir una versión nueva se reemplace la anterior. Vacío = nombre del archivo."
            ),
        ),
        BoolInput(
            name="clean",
            display_name="Limpiar",
            value=True,
            advanced=True,
            info="Quita índices con puntos de relleno, cabeceras y pies repetidos y líneas en blanco sobrantes.",
        ),
    ]

    outputs = [Output(display_name="Documentos", name="documents", method="convert")]

    def _converter(self) -> Any:
        """A MarkItDown instance (imported here so the error names what's missing)."""
        try:
            from markitdown import MarkItDown
        except ImportError as exc:  # pragma: no cover - depends on the image
            msg = "Falta la librería 'markitdown' en la imagen de Langflow (dockers/Dockerfile.langflow)."
            raise ImportError(msg) from exc
        return MarkItDown()

    @staticmethod
    def _convert_html(converter: Any, html: str) -> tuple[str, str]:
        """Convert an HTML page to Markdown; returns (markdown, title)."""
        stream = io.BytesIO(clean_html(html).encode("utf-8"))
        try:
            from markitdown import StreamInfo

            result = converter.convert_stream(stream, stream_info=StreamInfo(extension=".html", charset="utf-8"))
        except ImportError:  # markitdown < 0.1
            result = converter.convert_stream(stream, file_extension=".html")
        return result.text_content, (result.title or "")

    def _file_paths(self) -> list[str]:
        """Stored paths of the uploaded files."""
        files = self.files if isinstance(self.files, list) else [self.files]
        paths = []
        for item in files:
            if not item:
                continue
            path = str(item)
            if hasattr(self, "resolve_path"):
                path = self.resolve_path(path)
            paths.append(path)
        return paths

    def _from_file(self, converter: Any, path: str) -> tuple[Data | None, str]:
        """Convert one uploaded file; returns the document (or None) and a status line."""
        source = self.source_name.strip() if self.source_name else source_from_path(path)
        file_type = os.path.splitext(path)[1].lstrip(".").lower()
        if file_type in {"html", "htm"}:
            with open(path, encoding="utf-8", errors="replace") as handle:
                markdown, title = self._convert_html(converter, handle.read())
        else:
            result = converter.convert(path)
            markdown, title = result.text_content, (result.title or "")
        meta, markdown = split_front_matter(markdown)
        title = title or meta.get("title", "")
        if self.clean:
            markdown = clean_markdown(markdown, file_type)
        if len(markdown.strip()) < _MIN_TEXT_CHARS:
            hint = " (¿PDF escaneado? No tiene capa de texto)" if file_type == "pdf" else ""
            return None, f"{source_from_path(path)}: sin texto{hint}, no se carga"
        title = title or first_heading(markdown) or source_from_path(path)
        document = Data(data={"text": markdown, "source": source, "title": title, "file_type": file_type})
        return document, f"{source_from_path(path)} ({file_type}): {len(markdown)} caracteres"

    def _from_content(self, converter: Any, item: Any) -> tuple[Data | None, str]:
        """Convert content from another node; returns the document (or None) and a status line."""
        values = dict(item.data) if isinstance(item, Data) else {"text": getattr(item, "text", str(item))}
        text = str(values.pop("text", "") or "")
        source = str(values.get("source") or values.get("url") or "contenido")
        if looks_like_html(text):
            markdown, title = self._convert_html(converter, text)
            file_type = "html"
        else:
            meta, markdown = split_front_matter(text)
            title, file_type = meta.get("title", ""), "md"
        if self.clean:
            markdown = clean_markdown(markdown, file_type)
        if len(markdown.strip()) < _MIN_TEXT_CHARS:
            return None, f"{source}: sin texto, no se carga"
        values.update(
            text=markdown,
            source=source,
            title=str(values.get("title") or title or first_heading(markdown) or source),
            file_type=file_type,
        )
        return Data(data=values), f"{source} ({file_type}): {len(markdown)} caracteres"

    def convert(self) -> list[Data]:
        """Convert every file and content item to a Markdown document."""
        converter = self._converter()
        documents: list[Data] = []
        lines: list[str] = []
        for path in self._file_paths():
            document, line = self._from_file(converter, path)
            lines.append(line)
            if document:
                documents.append(document)
        contents = self.data_inputs if isinstance(self.data_inputs, list) else [self.data_inputs]
        for entry in contents:
            for item in entry if isinstance(entry, list) else [entry]:
                if item is None or item == "":
                    continue
                document, line = self._from_content(converter, item)
                lines.append(line)
                if document:
                    documents.append(document)
        self.status = "\n".join(lines) or "Sin archivos ni contenido."
        return documents
