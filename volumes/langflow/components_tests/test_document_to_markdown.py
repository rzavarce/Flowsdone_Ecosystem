"""Tests for document_to_markdown.py (Convertir a Markdown (Flowsdone)).

`langflow.*` and `markitdown` are stubbed (the real conversion is checked
against the Langflow image, see the PR); these tests cover what the
component adds: HTML cleaning, page-furniture removal, source names and how
files and content from other nodes become documents.

Run directly with:
    pytest volumes/langflow/components_tests/test_document_to_markdown.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
import types
from pathlib import Path


def _install_stubs() -> None:
    """Register minimal stand-ins for Langflow and MarkItDown."""

    class Component:
        pass

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

    class Message:
        def __init__(self, text=""):
            self.text = text

    langflow = types.ModuleType("langflow")
    custom = types.ModuleType("langflow.custom")
    custom.Component = Component
    io = types.ModuleType("langflow.io")
    for name in ("BoolInput", "FileInput", "HandleInput", "Output", "StrInput"):
        setattr(io, name, type(name, (_InputBase,), {}))
    schema = types.ModuleType("langflow.schema")
    schema.Data = Data
    schema.Message = Message
    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = custom
    sys.modules["langflow.io"] = io
    sys.modules["langflow.schema"] = schema

    class Result:
        def __init__(self, text, title=None):
            self.text_content = text
            self.title = title

    class MarkItDown:
        """Stand-in: returns canned Markdown per extension; HTML is 'converted' naively."""

        outputs: dict = {}
        streams: list = []

        def convert(self, path):
            return Result(*type(self).outputs[Path(path).suffix])

        def convert_stream(self, stream, stream_info=None, **kwargs):
            html = stream.read().decode("utf-8")
            type(self).streams.append(html)
            markdown = re.sub(r"<[^>]+>", "", html.replace("<h1>", "# ").replace("</h1>", "\n\n"))
            return Result(markdown, "Título web")

    class StreamInfo:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    markitdown = types.ModuleType("markitdown")
    markitdown.MarkItDown = MarkItDown
    markitdown.StreamInfo = StreamInfo
    sys.modules["markitdown"] = markitdown


_install_stubs()
_PATH = Path(__file__).parent.parent / "components" / "flowsdone" / "document_to_markdown.py"
_spec = importlib.util.spec_from_file_location("document_to_markdown", _PATH)
converter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(converter)
Data = sys.modules["langflow.schema"].Data
Message = sys.modules["langflow.schema"].Message
MarkItDown = sys.modules["markitdown"].MarkItDown


def _component(**overrides):
    component = converter.DocumentToMarkdown()
    component.files = []
    component.data_inputs = []
    component.source_name = ""
    component.clean = True
    for key, value in overrides.items():
        setattr(component, key, value)
    return component


PDF_TEXT = "\n".join(
    [
        "Índice",
        "Planes y precios . . . . . . . . . . . 12",
        "Canales ........................ 14",
    ]
    + [f"Manual comercial de Flowsdone\nflowsdone.com\nTexto de la página {n}.\n{n}" for n in range(1, 8)]
    + ["| Plan | Incluye |", "|---|---|", "| Pro | Sí |", "| Business | Sí |"]
)


# --- Pure functions -----------------------------------------------------------

def test_clean_html_drops_navigation_forms_scripts_and_hidden_elements():
    html = (
        "<html><body><nav>Menú</nav><header>Cabecera</header><main><h1>Planes</h1>"
        "<p>Pro 99 €</p><span aria-hidden='true'>icono</span><form>Email</form></main>"
        "<footer>© 2026</footer><script>x()</script></body></html>"
    )

    cleaned = converter.clean_html(html)

    assert "Planes" in cleaned and "Pro 99 €" in cleaned
    for noise in ("Menú", "Cabecera", "icono", "Email", "© 2026", "x()"):
        assert noise not in cleaned


def test_looks_like_html():
    assert converter.looks_like_html("<!DOCTYPE html><html><body>x</body></html>")
    assert converter.looks_like_html("<div><p>a</p><p>b</p><ul><li>c</li><li>d</li></ul></div>")
    assert not converter.looks_like_html("# Título\n\nTexto con <b>una</b> etiqueta suelta.")


def test_pdf_cleaning_removes_toc_page_furniture_and_page_numbers_but_keeps_tables():
    cleaned = converter.clean_markdown(PDF_TEXT, "pdf")

    assert ". . . ." not in cleaned and "......" not in cleaned
    assert "Manual comercial de Flowsdone" not in cleaned
    assert "flowsdone.com" not in cleaned
    assert "\n3\n" not in f"\n{cleaned}\n"
    assert "Texto de la página 3." in cleaned
    assert "| Pro | Sí |" in cleaned and "| Business | Sí |" in cleaned


def test_repeated_lines_are_only_dropped_in_paged_documents():
    text = "\n".join(["Aviso legal importante"] * 5 + ["Contenido"])

    assert "Aviso legal importante" in converter.clean_markdown(text, "docx")
    assert "Aviso legal importante" not in converter.clean_markdown(text, "pdf")


def test_source_from_path_drops_langflow_upload_timestamp():
    assert converter.source_from_path("/data/u1/2026-09-28_10-51-48_manual-comercial.pdf") == "manual-comercial.pdf"
    assert converter.source_from_path("/data/u1/tarifas_2026.xlsx") == "tarifas_2026.xlsx"


# --- Component ------------------------------------------------------------------

def test_files_become_markdown_documents_with_source_title_and_type():
    MarkItDown.outputs = {".pdf": (PDF_TEXT, None), ".docx": ("# Tarifas\n\nTexto de las tarifas.", "Tarifas 2026")}
    component = _component(files=["/s/2026-09-28_10-00-00_manual.pdf", "/s/tarifas.docx"])

    documents = component.convert()

    pdf, docx = (d.data for d in documents)
    assert pdf["source"] == "manual.pdf" and pdf["file_type"] == "pdf"
    assert pdf["title"] == "manual.pdf"  # no title nor heading: the file name
    assert "Manual comercial de Flowsdone" not in pdf["text"]
    assert docx == {"text": "# Tarifas\n\nTexto de las tarifas.", "source": "tarifas.docx", "title": "Tarifas 2026", "file_type": "docx"}
    assert "manual.pdf (pdf)" in component.status


def test_fixed_source_name_applies_to_uploaded_files():
    MarkItDown.outputs = {".md": ("# Manual\n\nContenido del manual.", None)}
    component = _component(files=["/s/2026-09-28_10-00-00_manual-v2.md"], source_name=" manual-comercial ")

    document = component.convert()[0].data

    assert document["source"] == "manual-comercial"
    assert document["title"] == "Manual"


def test_a_file_without_text_is_reported_not_loaded():
    MarkItDown.outputs = {".pdf": ("  \n ", None)}
    component = _component(files=["/s/escaneado.pdf"])

    assert component.convert() == []
    assert "escaneado.pdf: sin texto (¿PDF escaneado?" in component.status


def test_html_content_from_the_url_node_is_cleaned_and_keeps_its_metadata():
    MarkItDown.streams = []
    page = Data(data={
        "text": "<html><body><nav>Menú</nav><h1>Planes</h1><p>Pro 99 €/mes para varios canales.</p></body></html>",
        "source": "https://flowsdone.com",
        "language": "es",
    })
    component = _component(data_inputs=[[page]])

    document = component.convert()[0].data

    assert "Menú" not in MarkItDown.streams[0]
    assert document["text"].startswith("# Planes")
    assert document["source"] == "https://flowsdone.com"
    assert document["language"] == "es" and document["file_type"] == "html"
    assert document["title"] == "Título web"


def test_plain_text_content_and_messages_pass_through_as_markdown():
    component = _component(data_inputs=[Message(text="# Nota\n\nTexto que viene de otro nodo.")])

    document = component.convert()[0].data

    assert document == {
        "text": "# Nota\n\nTexto que viene de otro nodo.",
        "source": "contenido",
        "title": "Nota",
        "file_type": "md",
    }


def test_front_matter_becomes_metadata():
    meta, body = converter.split_front_matter('---\ntitle: "Manual comercial"\nversion: 1.0\n---\n\n# Uno\n\nTexto')

    assert meta == {"title": "Manual comercial", "version": "1.0"}
    assert body == "# Uno\n\nTexto"
    assert converter.split_front_matter("# Sin cabecera") == ({}, "# Sin cabecera")


def test_markup_noise_drops_html_comments_and_in_page_anchor_links():
    text = "<!-- Slide number: 1 -->\n# Plan Pro\n[Saltar al contenido](#main)\n* [Ver servicios](#servicios)\nVer [la web](https://flowsdone.com)."

    assert converter.remove_markup_noise(text) == "\n# Plan Pro\nVer [la web](https://flowsdone.com)."


def test_toc_block_after_an_index_title_is_dropped_keeping_the_first_chapter_title():
    text = "\n".join([
        "Manual", "", "Índice", "", "1. Cómo usar este manual", "", "Misión", "", "2. Planes",
        "", "Cómo usar este manual", "Este documento reúne todo lo que necesita un vendedor para presentar la empresa.",
    ])

    cleaned = converter.remove_toc_block(text)

    assert "Índice" not in cleaned and "Misión" not in cleaned and "2. Planes" not in cleaned
    assert cleaned.startswith("Manual\n")
    assert "Cómo usar este manual\nEste documento reúne" in cleaned


def test_toc_block_is_only_removed_in_paged_documents_and_docx():
    text = "Índice\n\nUno\n\nDos\n\nEste es el cuerpo del documento, con una frase completa."

    assert "Uno" in converter.clean_markdown(text, "md")
    assert "Uno" not in converter.clean_markdown(text, "pdf")


def test_front_matter_title_is_used_for_files_and_content():
    MarkItDown.outputs = {".md": ('---\ntitle: "Manual comercial"\n---\n\n# Cómo usar este manual\n\nTexto del manual.', None)}
    component = _component(
        files=["/s/manual.md"],
        data_inputs=[Message(text='---\ntitle: Nota interna\n---\nTexto que viene de otro nodo.')],
    )

    file_doc, content_doc = (d.data for d in component.convert())

    assert file_doc["title"] == "Manual comercial" and file_doc["text"].startswith("# Cómo usar")
    assert content_doc["title"] == "Nota interna" and content_doc["text"] == "Texto que viene de otro nodo."


def test_pdf_lines_broken_mid_sentence_are_rejoined():
    text = (
        "Este documento reúne todo lo que necesita,\n\nresolver dudas y elegir el plan\n\ncon el cliente.\n\n"
        "Reglas de uso:\n\nLos precios son sin IVA.\n\n| a | b |\n| c | d |"
    )

    joined = converter.join_broken_lines(text)

    assert "Este documento reúne todo lo que necesita, resolver dudas y elegir el plan con el cliente." in joined
    assert "Reglas de uso:\n\nLos precios son sin IVA." in joined
    assert "| a | b |\n| c | d |" in joined
