"""CallbackSenderPort over HTTP, guarded against SSRF and signed.

A caller of the generic webhook can ask to be told the agent's answer at
`payload.callback_url`. That URL comes from outside the gateway, so before
POSTing to it:

- Only `https` is accepted, or `http` to a host explicitly allowed
  (`CALLBACK_ALLOWED_HOSTS`, e.g. an internal `n8n`).
- With an allow-list, the host must be on it. Without one, every address
  the host resolves to must be public: private, loopback, link-local,
  reserved, multicast and unspecified addresses are refused, so a callback
  can't reach services inside the network.
- Redirects are not followed (a public URL could redirect inside).
- The body is signed with HMAC-SHA256 (`CALLBACK_HMAC_SECRET`) in the
  `X-Flowsdone-Signature` header, so the receiver can verify it.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
from typing import Any, Collection, Dict, List, Optional
from urllib.parse import urlsplit

import httpx

from app.application.services.hmac_signing import sign
from app.domain.ports.outbound import CallbackSenderPort

logger = logging.getLogger("callbacks.http")

SIGNATURE_HEADER = "X-Flowsdone-Signature"
_RETRYABLE = {429, 500, 502, 503, 504}


class CallbackRefusedError(ValueError):
    """The callback URL is not an allowed destination."""


def _is_public(address: str) -> bool:
    """Whether an IP address is on the public internet.

    Args:
        address (str): An IPv4 or IPv6 address.

    Returns:
        bool: False for private, loopback, link-local, reserved, multicast
        and unspecified addresses (and IPv4-mapped forms of them).
    """
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
    )


class HttpCallbackSender(CallbackSenderPort):
    """Signed, SSRF-guarded HTTP callbacks."""

    def __init__(
        self,
        *,
        secret: str,
        allowed_hosts: Collection[str] = (),
        timeout_seconds: float = 10.0,
        max_retries: int = 3,
        backoff_seconds: float = 2.0,
    ) -> None:
        """Build the sender.

        Args:
            secret (str): HMAC secret the body is signed with.
            allowed_hosts (Collection[str]): Hosts a callback may go to
                (case-insensitive). Empty = any host that resolves only to
                public addresses, over https.
            timeout_seconds (float): Timeout of each attempt.
            max_retries (int): Attempts on network errors and 429/5xx.
            backoff_seconds (float): Base wait between attempts (doubles).
        """
        self._secret = secret
        self._allowed = {h.strip().lower() for h in allowed_hosts if h.strip()}
        self._timeout = timeout_seconds
        self._max_retries = max(1, max_retries)
        self._backoff = backoff_seconds

    async def send(self, url: str, body: Dict[str, Any]) -> bool:
        """POST the signed body to `url` if it's an allowed destination.

        Args:
            url (str): The callback URL.
            body (Dict[str, Any]): JSON body.

        Returns:
            bool: True on a 2xx answer; False if refused or failed.
        """
        try:
            await self._check(url)
        except CallbackRefusedError as exc:
            logger.warning("callbacks.refused", extra={"url": url, "reason": str(exc)})
            return False
        raw = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json", SIGNATURE_HEADER: sign(raw, self._secret)}
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=False) as client:
            for attempt in range(1, self._max_retries + 1):
                try:
                    response = await client.post(url, content=raw, headers=headers)
                except httpx.HTTPError as exc:
                    logger.warning("callbacks.error", extra={"url": url, "attempt": attempt, "error": str(exc)})
                else:
                    if response.status_code < 300:
                        return True
                    logger.warning(
                        "callbacks.rejected", extra={"url": url, "attempt": attempt, "status_code": response.status_code}
                    )
                    if response.status_code not in _RETRYABLE:
                        return False
                if attempt < self._max_retries:
                    await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
        return False

    async def _check(self, url: str) -> None:
        """Refuse destinations that aren't allowed.

        Args:
            url (str): The callback URL.

        Raises:
            CallbackRefusedError: If the scheme, host or its addresses
                aren't allowed.
        """
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if not host:
            raise CallbackRefusedError("no host")
        if parts.username or parts.password:
            raise CallbackRefusedError("credentials in the URL")
        if self._allowed:
            if host not in self._allowed:
                raise CallbackRefusedError(f"host {host!r} not allowed")
            if parts.scheme not in ("https", "http"):
                raise CallbackRefusedError(f"scheme {parts.scheme!r} not allowed")
            return
        if parts.scheme != "https":
            raise CallbackRefusedError("only https callbacks are allowed")
        for address in await self._resolve(host, parts.port or 443):
            if not _is_public(address):
                raise CallbackRefusedError(f"{host!r} resolves to a non-public address")

    @staticmethod
    async def _resolve(host: str, port: int) -> List[str]:
        """Every address a host resolves to.

        Args:
            host (str): Host name or IP literal.
            port (int): Port (needed by the resolver).

        Returns:
            List[str]: The addresses.

        Raises:
            CallbackRefusedError: If it doesn't resolve.
        """
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError) as exc:
            raise CallbackRefusedError(f"cannot resolve {host!r}") from exc
        return sorted({info[4][0] for info in infos})


def parse_allowed_hosts(value: Optional[str]) -> List[str]:
    """`CALLBACK_ALLOWED_HOSTS` ("n8n, hooks.example.com") as a list.

    Args:
        value (Optional[str]): Comma-separated hosts.

    Returns:
        List[str]: The hosts, trimmed; empty if none.
    """
    return [h.strip() for h in (value or "").split(",") if h.strip()]


def build_callback_sender(settings: Any) -> HttpCallbackSender:
    """The callback sender configured from the gateway settings.

    Args:
        settings (Any): `app.core.config.settings`.

    Returns:
        HttpCallbackSender: Signed with CALLBACK_HMAC_SECRET, limited to
        CALLBACK_ALLOWED_HOSTS (or public https hosts), with the configured
        retries.
    """
    return HttpCallbackSender(
        secret=settings.CALLBACK_HMAC_SECRET,
        allowed_hosts=parse_allowed_hosts(settings.CALLBACK_ALLOWED_HOSTS),
        max_retries=settings.CALLBACK_MAX_RETRIES,
        backoff_seconds=settings.CALLBACK_BACKOFF_SECONDS,
    )
