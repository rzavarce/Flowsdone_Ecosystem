from typing import Protocol
from api_gateway.app.domain.models.message import Message

class IngestMessagePort(Protocol):
    async def ingest(self, message: Message) -> None: ...