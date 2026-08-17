"""Legacy inbound port module, superseded by the inbound/ package.

Since domain/ports/inbound/ exists as a package with an __init__.py,
Python resolves `from ...domain.ports.inbound import X` to that
package, not to this file. This module is unreachable and kept only
for historical reference; new inbound ports belong in the inbound/
package.
"""

from typing import Protocol

from api_gateway.app.domain.models.message import Message


class IngestMessagePort(Protocol):
    """Contract for ingesting a canonical Message into the application."""

    async def ingest(self, message: Message) -> None:
        """Ingest a message.

        Args:
            message (Message): The canonical Message to ingest.
        """
        ...
