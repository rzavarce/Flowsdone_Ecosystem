"""Data to TOON: encodes Data as Token-Oriented Object Notation text.

TOON trims JSON's key-repetition overhead for the case that matters most
in LLM prompts: an array of uniform objects (e.g. RAG-retrieved chunks
shaped like {text, source, score}). Instead of repeating the keys once
per item, it declares them a single time in a header and lists each item
as a plain comma-separated row.

Encoding itself is delegated to the `python-toon` package (already
installed in the Langflow image, see dockers/Dockerfile.langflow) rather
than reimplemented here - it's the reference implementation of the
format, so this component is just a thin Data-unwrapping wrapper around
`toon.encode`.
"""

from __future__ import annotations

import toon
from langflow.custom import Component
from langflow.io import HandleInput, Output
from langflow.schema import Data
from langflow.schema.message import Message


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
        text = toon.encode(payload)
        self.status = text
        return Message(text=text)
