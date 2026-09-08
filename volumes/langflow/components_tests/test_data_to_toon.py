"""Tests for the DataToToonComponent wrapper in data_to_toon.py.

The actual TOON encoding is delegated to the `toon` package
(python-toon, already installed in the Langflow image - see
dockers/Dockerfile.langflow) rather than reimplemented here, so these
tests only cover this module's own responsibility: unwrapping Data
objects into plain payloads before handing them to `toon.encode`, and
wrapping the result as a Message. `toon.encode` itself is stubbed with a
deterministic fake - verifying its actual encoding behavior is
python-toon's own test suite's job, not this component's.

This file lives outside the api_gateway package (it's a Langflow custom
component, loaded by Langflow's own runtime, not by the api_gateway
app), so it isn't picked up by api_gateway's pytest config and doesn't
import the real `langflow`/`toon` packages (not installed in that venv).
Minimal stand-ins are injected into sys.modules before loading the
module under test.

Run directly with:
    pytest volumes/langflow/components/test_data_to_toon.py
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

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

    def fake_encode(value, options=None):
        # Deterministic stand-in for toon.encode: real encoding behavior
        # is python-toon's own responsibility, not this wrapper's.
        return f"TOON({value!r})"

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
    toon_module = types.ModuleType("toon")
    toon_module.encode = fake_encode

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["langflow.schema.message"] = langflow_schema_message
    sys.modules["toon"] = toon_module


_install_stubs()

_MODULE_PATH = Path(__file__).parent / "data_to_toon.py"
_spec = importlib.util.spec_from_file_location("data_to_toon", _MODULE_PATH)
data_to_toon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(data_to_toon)

Data = sys.modules["langflow.schema"].Data
DataToToonComponent = data_to_toon.DataToToonComponent


def test_build_toon_unwraps_a_list_of_data_objects_before_encoding():
    component = DataToToonComponent()
    component.data = [
        Data(data={"text": "hola", "source": "faq.pdf"}),
        Data(data={"text": "mundo", "source": "kit.pdf"}),
    ]

    message = component.build_toon()

    assert message.text == (
        "TOON([{'text': 'hola', 'source': 'faq.pdf'}, "
        "{'text': 'mundo', 'source': 'kit.pdf'}])"
    )


def test_build_toon_wraps_a_single_data_object_in_a_list():
    component = DataToToonComponent()
    component.data = Data(data={"text": "hola"})

    message = component.build_toon()

    assert message.text == "TOON([{'text': 'hola'}])"


def test_build_toon_passes_through_non_data_items_unchanged():
    component = DataToToonComponent()
    component.data = [{"text": "ya es un dict plano"}]

    message = component.build_toon()

    assert message.text == "TOON([{'text': 'ya es un dict plano'}])"


def test_build_toon_sets_status_to_the_encoded_text():
    component = DataToToonComponent()
    component.data = Data(data={"text": "hola"})

    component.build_toon()

    assert component.status == "TOON([{'text': 'hola'}])"
