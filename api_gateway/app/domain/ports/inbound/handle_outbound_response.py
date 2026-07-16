from typing import Protocol
from ....domain.ports.outbound.response_publisher import OutboundResponse

class HandleOutboundResponsePort(Protocol):
    async def handle(self, event: OutboundResponse) -> None: ...
