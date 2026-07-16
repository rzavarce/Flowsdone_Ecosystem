from typing import Protocol
from ...domain.models.message import Message

class IngestMessagePort(Protocol):
    async def ingest(self, message: Message) -> None: ...
