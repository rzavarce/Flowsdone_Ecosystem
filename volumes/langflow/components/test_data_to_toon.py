"""Tests for the pure `to_toon` encoder in data_to_toon.py.

This file lives outside the api_gateway package (it's a Langflow custom
component, loaded by Langflow's own runtime, not by the api_gateway app),
so it isn't picked up by api_gateway's pytest config and doesn't import
the real `langflow` package (not installed in that venv). Before loading
the module under test, minimal stand-ins for the langflow symbols it
imports are injected into sys.modules, so only the pure `to_toon` logic -
the part with real behavior to verify - is exercised.

Run directly with:
    pytest volumes/langflow/components/test_data_to_toon.py
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _install_langflow_stubs() -> None:
    """Register minimal stand-ins for the langflow symbols this module imports."""

    class Component:
        pass

    class HandleInput:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Output:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

    class Message:
        def __init__(self, text=""):
            self.text = text

    langflow = types.ModuleType("langflow")
    langflow_custom = types.ModuleType("langflow.custom")
    langflow_custom.Component = Component
    langflow_io = types.ModuleType("langflow.io")
    langflow_io.HandleInput = HandleInput
    langflow_io.Output = Output
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data
    langflow_schema_message = types.ModuleType("langflow.schema.message")
    langflow_schema_message.Message = Message

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["langflow.schema.message"] = langflow_schema_message


_install_langflow_stubs()

_MODULE_PATH = Path(__file__).parent / "data_to_toon.py"
_spec = importlib.util.spec_from_file_location("data_to_toon", _MODULE_PATH)
data_to_toon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(data_to_toon)

to_toon = data_to_toon.to_toon
Data = sys.modules["langflow.schema"].Data
DataToToonComponent = data_to_toon.DataToToonComponent


def test_encodes_flat_dict_as_key_value_lines():
    result = to_toon({"nombre": "Ana", "edad": 30})

    assert result == "nombre: Ana\nedad: 30"


def test_encodes_nested_dict_with_indentation():
    result = to_toon({"datos_contacto": {"nombre": "Ana", "email": "a@x.com"}})

    assert result == "datos_contacto:\n  nombre: Ana\n  email: a@x.com"


def test_encodes_uniform_list_of_dicts_as_a_single_header_and_rows():
    chunks = [
        {"text": "hola", "source": "faq.pdf", "score": 0.91},
        {"text": "mundo", "source": "kit.pdf", "score": 0.85},
    ]

    result = to_toon({"chunks": chunks})

    assert result == (
        "chunks[2]{text,source,score}:\n"
        "  hola,faq.pdf,0.91\n"
        "  mundo,kit.pdf,0.85"
    )


def test_encodes_non_uniform_list_of_dicts_as_separate_blocks():
    items = [{"a": 1}, {"b": 2, "c": 3}]

    result = to_toon({"items": items})

    assert result == "items[2]:\n  a: 1\n  b: 2\n  c: 3"


def test_encodes_list_of_scalars_inline():
    result = to_toon({"tags": ["alto", "vendedor", "urgente"]})

    assert result == "tags[3]: alto,vendedor,urgente"


def test_encodes_empty_list():
    result = to_toon({"items": []})

    assert result == "items[0]:"


def test_quotes_values_containing_commas_colons_or_newlines():
    result = to_toon({"nota": "hola, mundo: dos lineas\nsegunda"})

    assert result == 'nota: "hola, mundo: dos lineas\nsegunda"'


def test_escapes_embedded_double_quotes():
    result = to_toon({"cita": 'dijo "hola"'})

    assert result == 'cita: "dijo \\"hola\\""'


def test_encodes_booleans_and_none():
    result = to_toon({"activo": True, "inactivo": False, "vacio": None})

    assert result == "activo: true\ninactivo: false\nvacio: null"


def test_component_build_toon_unwraps_data_objects_before_encoding():
    component = DataToToonComponent()
    component.data = [
        Data(data={"text": "hola", "source": "faq.pdf"}),
        Data(data={"text": "mundo", "source": "kit.pdf"}),
    ]

    message = component.build_toon()

    assert message.text == (
        "[2]{text,source}:\n"
        "  hola,faq.pdf\n"
        "  mundo,kit.pdf"
    )


def test_component_build_toon_wraps_a_single_data_object_in_a_list():
    component = DataToToonComponent()
    component.data = Data(data={"text": "hola"})

    message = component.build_toon()

    assert message.text == "[1]{text}:\n  hola"
