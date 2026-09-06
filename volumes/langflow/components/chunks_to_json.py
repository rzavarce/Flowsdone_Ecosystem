import json

from langflow.custom import Component
from langflow.io import HandleInput, Output
from langflow.schema.message import Message


class ChunksToJsonComponent(Component):
    display_name = "Chunks to JSON"
    description = (
        "Serializes a list of Data chunks (e.g. from a Text Splitter) into a single JSON Message, "
        "so it can be returned as plain text via the Langflow Run API and parsed by external callers (n8n)."
    )
    icon = "braces"
    name = "ChunksToJson"

    inputs = [
        HandleInput(
            name="chunks",
            display_name="Chunks",
            info="The Data chunks to serialize as a JSON array.",
            input_types=["Data"],
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="JSON Message", name="message", method="to_json_message"),
    ]

    def to_json_message(self) -> Message:
        items = self.chunks if isinstance(self.chunks, list) else [self.chunks]
        payload = [
            {
                "text": item.data.get("text", ""),
                "metadata": {k: v for k, v in item.data.items() if k != "text"},
            }
            for item in items
        ]
        text = json.dumps(payload, ensure_ascii=False, default=str)
        self.status = text
        return Message(text=text)
