"""Tests for semantic_splitter.py (Semantic Text Splitter (Flowsdone)).

Same isolation approach as the sibling test files: `langflow.*` is stubbed,
and embeddings are a deterministic fake, so no model is called.

Run directly with:
    pytest volumes/langflow/components_tests/test_semantic_splitter.py
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _install_stubs() -> None:
    """Register minimal stand-ins for the Langflow symbols the module imports."""

    class Component:
        pass

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs
            self.text_key = "text"

    class RangeSpec:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    langflow = types.ModuleType("langflow")
    custom = types.ModuleType("langflow.custom")
    custom.Component = Component
    io = types.ModuleType("langflow.io")
    for name in ("BoolInput", "DropdownInput", "FloatInput", "HandleInput", "IntInput", "Output"):
        setattr(io, name, type(name, (_InputBase,), {}))
    schema = types.ModuleType("langflow.schema")
    schema.Data = Data
    field_typing = types.ModuleType("langflow.field_typing")
    range_spec = types.ModuleType("langflow.field_typing.range_spec")
    range_spec.RangeSpec = RangeSpec
    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = custom
    sys.modules["langflow.io"] = io
    sys.modules["langflow.schema"] = schema
    sys.modules["langflow.field_typing"] = field_typing
    sys.modules["langflow.field_typing.range_spec"] = range_spec


_install_stubs()
_PATH = Path(__file__).parent.parent / "components" / "semantic_splitter.py"
_spec = importlib.util.spec_from_file_location("semantic_splitter", _PATH)
splitter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(splitter)
Data = sys.modules["langflow.schema"].Data


class TopicEmbeddings:
    """Fake embeddings: one axis per topic word, so topic changes are far apart."""

    TOPICS = ("whatsapp", "precio", "voz")

    def __init__(self):
        self.calls = 0

    def embed_documents(self, texts):
        self.calls += 1
        vectors = []
        for text in texts:
            lowered = text.lower()
            vector = [lowered.count(topic) for topic in self.TOPICS]
            vectors.append([v + 0.01 for v in vector])
        return vectors


def _component(**overrides):
    component = splitter.FlowsdoneSemanticSplitter()
    component.data_inputs = []
    component.embeddings = None
    component.max_chunk_chars = 1500
    component.min_chunk_chars = 200
    component.breakpoint_threshold_type = "percentile"
    component.breakpoint_threshold_amount = 90.0
    component.buffer_size = 1
    component.heading_levels = 3
    component.add_context_header = True
    for key, value in overrides.items():
        setattr(component, key, value)
    return component


MANUAL = """# Planes y precios

Cuota mensual con mensajes incluidos. Precios sin IVA.

## Comparativa

| | Starter | Pro |
|---|---|---|
| Precio | 29 €/mes | 99 €/mes |
| Mensajes | 1.000 | 5.000 |

## Pro — 99 €/mes

Para negocios con varios canales. Incluye voz.

- 5.000 mensajes de texto al mes.
- 300 turnos de voz al mes.

# Canales

## WhatsApp

El asistente responde desde el número de la empresa.
"""


# --- Pure functions -----------------------------------------------------------

def test_sections_follow_heading_paths():
    sections = splitter.split_sections(MANUAL)

    paths = [" > ".join(s.path) for s in sections if s.body]
    assert paths == [
        "Planes y precios",
        "Planes y precios > Comparativa",
        "Planes y precios > Pro — 99 €/mes",
        "Canales > WhatsApp",
    ]


def test_deeper_headings_and_headings_in_code_stay_as_content():
    text = "# A\n\n#### Detalle\n\ntexto\n\n```\n# no es título\n```\n"

    sections = splitter.split_sections(text, max_level=3)

    assert [s.path for s in sections] == [["A"]]
    assert "#### Detalle" in sections[0].body
    assert "# no es título" in sections[0].body


def test_sentences_respect_spanish_punctuation_abbreviations_and_numbers():
    paragraph = (
        "Hola, ¿tenéis cita? ¡Sí! Tenemos 1.000 mensajes, p. ej. para WhatsApp. "
        "Cuesta 0,02 € por mensaje. Sr. Pérez lo confirma."
    )

    assert splitter.split_sentences(paragraph) == [
        "Hola, ¿tenéis cita?",
        "¡Sí!",
        "Tenemos 1.000 mensajes, p. ej. para WhatsApp.",
        "Cuesta 0,02 € por mensaje.",
        "Sr. Pérez lo confirma.",
    ]


def test_units_keep_tables_whole_items_separate_and_join_broken_pdf_lines():
    body = "Esta frase se partió\nal final de la línea impresa. Otra frase.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- uno\n- dos"

    units = splitter.split_units(body)

    assert [(u.kind, u.text) for u in units] == [
        ("sentence", "Esta frase se partió al final de la línea impresa."),
        ("sentence", "Otra frase."),
        ("table", "| a | b |\n|---|---|\n| 1 | 2 |"),
        ("item", "- uno"),
        ("item", "- dos"),
    ]
    assert splitter.join_units(units[:2]) == "Esta frase se partió al final de la línea impresa. Otra frase."


def test_oversized_tables_are_split_by_rows_repeating_the_header():
    rows = "\n".join(f"| fila {i} | {'x' * 30} |" for i in range(20))
    table = splitter.Unit(f"| col | valor |\n|---|---|\n{rows}", "table", 0)

    pieces = splitter.split_oversized(table, 300)

    assert len(pieces) > 1
    for piece in pieces:
        assert piece.text.startswith("| col | valor |\n|---|---|")
        assert len(piece.text) <= 300
    assert sum(p.text.count("| fila") for p in pieces) == 20


def test_breakpoint_types():
    distances = [0.1, 0.1, 0.9, 0.1, 0.1, 0.8]

    assert splitter.breakpoints(distances, "percentile", 60) == {2, 5}
    assert splitter.breakpoints(distances, "standard_deviation", 1.0) == {2, 5}
    assert splitter.breakpoints([0.5, 0.9], "percentile", 50) == set()  # too few points


def test_pack_respects_max_and_merges_small_chunks():
    units = [splitter.Unit(f"Frase número {i} con algo de texto.", "sentence", 0) for i in range(30)]

    chunks = splitter.pack(["S"], units, breaks={2}, min_chars=200, max_chars=300)

    assert all(len(c.body) <= 300 for c in chunks)
    # The break after unit 2 would leave a tiny chunk: it is ignored.
    assert all(len(c.body) >= 200 for c in chunks[:-1])
    assert "".join(c.body for c in chunks).count("Frase número") == 30


# --- Component ------------------------------------------------------------------

def test_chunks_never_mix_sections_and_start_with_their_heading_path():
    component = _component(data_inputs=[Data(data={"text": MANUAL, "source": "manual.md", "title": "Manual"})])

    chunks = component.split()

    sections = [c.data["section"] for c in chunks]
    assert sections == [
        "Planes y precios",
        "Planes y precios > Comparativa",
        "Planes y precios > Pro — 99 €/mes",
        "Canales > WhatsApp",
    ]
    pro = chunks[2].data
    assert pro["text"].startswith("Planes y precios > Pro — 99 €/mes\n\n")
    assert "300 turnos de voz" in pro["text"]
    assert pro["source"] == "manual.md" and pro["title"] == "Manual"
    assert [c.data["chunk_index"] for c in chunks] == [0, 1, 2, 3]


def test_a_table_is_kept_in_one_chunk_with_its_rows():
    component = _component(data_inputs=[Data(data={"text": MANUAL})])

    comparativa = component.split()[1].data["text"]

    assert "| Precio | 29 €/mes | 99 €/mes |" in comparativa
    assert "| Mensajes | 1.000 | 5.000 |" in comparativa


def test_long_sections_are_cut_where_the_topic_changes():
    whatsapp = " ".join(f"WhatsApp se conecta con el número {i}." for i in range(12))
    precio = " ".join(f"El precio del plan {i} es cerrado." for i in range(12))
    voz = " ".join(f"La voz atiende la llamada {i}." for i in range(12))
    text = f"# Guía\n\n{whatsapp} {precio} {voz}"
    embeddings = TopicEmbeddings()
    component = _component(data_inputs=[Data(data={"text": text})], embeddings=embeddings,
                           max_chunk_chars=600, min_chunk_chars=100)

    chunks = [c.data["text"] for c in component.split()]

    assert embeddings.calls == 1
    for chunk in chunks:
        topics = {t for t in ("WhatsApp", "precio", "voz") if t in chunk}
        assert len(topics) == 1, chunk
    assert all(len(c.split("\n\n", 1)[1]) <= 600 for c in chunks)


def test_short_sections_need_no_embeddings():
    embeddings = TopicEmbeddings()
    component = _component(data_inputs=[Data(data={"text": MANUAL})], embeddings=embeddings)

    component.split()

    assert embeddings.calls == 0


def test_text_without_headings_uses_the_document_title_as_context():
    component = _component(data_inputs=[Data(data={"text": "Texto de una web sin títulos. " * 5, "title": "Inicio"})])

    chunk = component.split()[0].data

    assert chunk["section"] == "Inicio"
    assert chunk["text"].startswith("Inicio\n\n")


def test_context_header_can_be_turned_off_and_empty_documents_are_skipped():
    component = _component(
        data_inputs=[[Data(data={"text": MANUAL})], Data(data={"text": "   "})],
        add_context_header=False,
    )

    chunks = component.split()

    assert chunks[0].data["text"].startswith("Cuota mensual")
    assert "4 fragmentos de 2 documentos" in component.status
