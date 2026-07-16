from typing import Protocol
from api_gateway.app.domain.ports.outbound.response_publisher import OutboundResponse

class HandleOutboundResponsePort(Protocol):
    async def handle(self, event: OutboundResponse) -> None: ...