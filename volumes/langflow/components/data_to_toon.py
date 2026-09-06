"""Data to TOON: encodes Data as Token-Oriented Object Notation text.

TOON trims JSON's key-repetition overhead for the case that matters most
in LLM prompts: an array of uniform objects (e.g. RAG-retrieved chunks
shaped like {text, source, score}). Instead of repeating the keys once
per item, it declares them a single time in a header and lists each item
as a plain comma-separated row - e.g.:

    chunks[2]{text,source,score}:
      "some text",faq.pdf,0.91
      "other text",kit.pdf,0.85

`to_toon` below is a pure function (no Langflow imports) so it can be
unit-tested directly; `DataToToonComponent` is the thin Langflow wrapper
around it.
"""

from __future__ import annotations

from typing import Any

from langflow.custom import Component
from langflow.io import HandleInput, Output
from langflow.schema import Data
from langflow.schema.message import Message

_INDENT = "  "
_NEEDS_QUOTING = (",", ":", "\n", '"')


def to_toon(data: Any, *, indent: int = 0) -> str:
    """Encode a Python value as a TOON string.

    Args:
        data (Any): The value to encode - a dict, a list (of dicts or
            scalars), or a scalar. Dict values and list items are encoded
            recursively.
        indent (int): Current indentation depth, in units of two spaces.
            Callers normally omit this; it is used internally for
            recursion into nested dicts/lists.

    Returns:
        str: The TOON-encoded representation of `data`.
    """
    if isinstance(data, dict):
        return _encode_object(data, indent)
    if isinstance(data, list):
        return _encode_array("", data, indent)
    return f"{_INDENT * indent}{_encode_scalar(data)}"


def _encode_object(obj: dict, indent: int) -> str:
    pad = _INDENT * indent
    lines: list[str] = []
    for key, value in obj.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            lines.append(_encode_object(value, indent + 1))
        elif isinstance(value, list):
            lines.append(_encode_array(key, value, indent))
        else:
            lines.append(f"{pad}{key}: {_encode_scalar(value)}")
    return "\n".join(lines)


def _encode_array(key: str, items: list, indent: int) -> str:
    pad = _INDENT * indent

    if not items:
        return f"{pad}{key}[0]:" if key else f"{pad}[0]:"

    if all(isinstance(item, dict) for item in items) and _same_keys(items):
        fields = list(items[0].keys())
        header = f"{pad}{key}[{len(items)}]{{{','.join(fields)}}}:"
        rows = [
            f"{pad}{_INDENT}{','.join(_encode_scalar(item[field]) for field in fields)}"
            for item in items
        ]
        return "\n".join([header, *rows])

    if all(not isinstance(item, (dict, list)) for item in items):
        values = ",".join(_encode_scalar(item) for item in items)
        return f"{pad}{key}[{len(items)}]: {values}"

    # Non-uniform or nested items: one indented TOON block per item.
    header = f"{pad}{key}[{len(items)}]:"
    blocks = [to_toon(item, indent=indent + 1) for item in items]
    return "\n".join([header, *blocks])


def _same_keys(items: list[dict]) -> bool:
    first_keys = list(items[0].keys())
    return all(list(item.keys()) == first_keys for item in items[1:])


def _encode_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)
    if text == "" or text != text.strip() or any(ch in text for ch in _NEEDS_QUOTING):
        return f'"{text.replace(chr(34), chr(92) + chr(34))}"'
    return text


class DataToToonComponent(Component):
    display_name = "Data to TOON"
    description = (
        "Encodes Data (e.g. RAG-retrieved chunks) as TOON "
        "(Token-Oriented Object Notation) text, trimming JSON's "
        "key-repetition overhead for arrays of uniform objects."
    )
    icon = "braces"
    name = "DataToToon"

    inputs = [
        HandleInput(
            name="data",
            display_name="Data",
            info="The Data object (or list of Data) to encode as TOON.",
            input_types=["Data"],
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="TOON", name="toon", method="build_toon"),
    ]

    def build_toon(self) -> Message:
        items = self.data if isinstance(self.data, list) else [self.data]
        payload = [item.data if isinstance(item, Data) else item for item in items]
        text = to_toon(payload)
        self.status = text
        return Message(text=text)
