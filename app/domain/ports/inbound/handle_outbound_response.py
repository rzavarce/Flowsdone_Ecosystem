from typing import Protocol
from app.domain.ports.outbound.response_publisher import OutboundResponse

class HandleOutboundResponsePort(Protocol):
    async def handle(self, event: OutboundResponse) -> None: ...