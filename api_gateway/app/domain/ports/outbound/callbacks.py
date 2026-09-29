"""Port for result callbacks: telling an internal caller that asked for it
(via `payload.callback_url`) what the agent answered."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class CallbackSenderPort(Protocol):
    """Delivers a workflow result to the caller's callback URL."""

    async def send(self, url: str, body: Dict[str, Any]) -> bool:
        """POST the result to `url`, best-effort. Never raises.

        Implementations must refuse destinations that aren't allowed
        (unsafe scheme, internal address, host not in the allow-list) and
        sign the body, so the receiver can tell it comes from Flowsdone.

        Args:
            url (str): The callback URL given by the caller.
            body (Dict[str, Any]): JSON body to send.

        Returns:
            bool: True if it was delivered (2xx), False if it was refused
            or failed.
        """
        ...
