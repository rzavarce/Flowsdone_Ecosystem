"""Port for reacting to a published outbound response event."""

from typing import Protocol

from api_gateway.app.domain.ports.outbound.response_publisher import OutboundResponse


class HandleOutboundResponsePort(Protocol):
    """Contract for handling an OutboundResponse event."""

    async def handle(self, event: OutboundResponse) -> None:
        """Handle an outbound response event.

        Args:
            event (OutboundResponse): The event to process.
        """
        ...
