"""Langfuse implementation of LlmUsageSourcePort, over Langfuse's public
REST API (`/api/public/observations`, `/api/public/traces/{id}`).
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.domain.ports.outbound import LlmGeneration, LlmUsageSourcePort

logger = logging.getLogger("langfuse.usage_source")

_PAGE_SIZE = 100
_SESSION_CACHE_SIZE = 5000


class LangfuseApiError(Exception):
    """Raised when the Langfuse API answers with an error."""


def _iso(value: datetime) -> str:
    """Format a datetime as the ISO-8601 UTC string Langfuse expects.

    Args:
        value (datetime): The datetime (naive values are taken as UTC).

    Returns:
        str: e.g. "2026-09-01T12:00:00.000Z".
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _token_counts(observation: Dict[str, Any]) -> tuple[int, int, int]:
    """Split a generation's usage into (input, output, cached input).

    Langfuse reports `usageDetails` as free-form keys per provider:
    "input"/"output" are always there, cache reads come under keys
    containing "cache" (e.g. "input_cached_tokens", "cache_read_input_tokens")
    and are NOT included in "input". "total" and other breakdowns
    (reasoning tokens are already part of "output") are ignored. Falls
    back to the legacy `usage` object when `usageDetails` is missing.

    Args:
        observation (Dict[str, Any]): A GENERATION observation.

    Returns:
        tuple[int, int, int]: Input, output and cached input tokens.
    """
    details = observation.get("usageDetails") or {}
    if not details:
        usage = observation.get("usage") or {}
        details = {"input": usage.get("input") or 0, "output": usage.get("output") or 0}
    cached = sum(int(v or 0) for k, v in details.items() if "cache" in k.lower())
    return int(details.get("input") or 0), int(details.get("output") or 0), cached


class LangfuseUsageSource(LlmUsageSourcePort):
    """Reads GENERATION observations and resolves each one's trace session.

    Sessions are fetched per trace and memoized (bounded LRU): the
    generations of one conversation turn share a trace.
    """

    def __init__(
        self, *, base_url: str, public_key: str, secret_key: str, timeout_seconds: float = 15.0
    ) -> None:
        """Build the source.

        Args:
            base_url (str): Langfuse base URL (e.g. http://langfuse-web:3000).
            public_key (str): Project public key.
            secret_key (str): Project secret key.
            timeout_seconds (float): HTTP timeout per request.
        """
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            auth=(public_key, secret_key),
            timeout=httpx.Timeout(timeout_seconds),
        )
        self._sessions: "OrderedDict[str, Optional[str]]" = OrderedDict()

    async def list_generations(self, *, start: datetime, end: datetime) -> List[LlmGeneration]:
        """LLM calls that started in [start, end), with their session.

        Args:
            start (datetime): Inclusive start.
            end (datetime): Exclusive end.

        Returns:
            List[LlmGeneration]: The calls (those without a model are skipped).

        Raises:
            LangfuseApiError: If Langfuse answers with an error.
        """
        generations: List[LlmGeneration] = []
        page = 1
        while True:
            body = await self._get(
                "/api/public/observations",
                params={
                    "type": "GENERATION",
                    "fromStartTime": _iso(start),
                    "toStartTime": _iso(end),
                    "page": page,
                    "limit": _PAGE_SIZE,
                },
            )
            for observation in body.get("data", []):
                if not observation.get("model"):
                    continue
                input_tokens, output_tokens, cached = _token_counts(observation)
                generations.append(
                    LlmGeneration(
                        id=observation["id"],
                        trace_id=observation["traceId"],
                        session_id=await self._session_of(observation["traceId"]),
                        model=observation["model"],
                        start_time=datetime.fromisoformat(observation["startTime"].replace("Z", "+00:00")),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cached_input_tokens=cached,
                    )
                )
            total_pages = (body.get("meta") or {}).get("totalPages") or 1
            if page >= total_pages:
                return generations
            page += 1

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _session_of(self, trace_id: str) -> Optional[str]:
        """Session id of a trace, memoized.

        Args:
            trace_id (str): Trace id.

        Returns:
            Optional[str]: The session id, or None if the trace has none
            or no longer exists.
        """
        if trace_id in self._sessions:
            self._sessions.move_to_end(trace_id)
            return self._sessions[trace_id]
        try:
            trace = await self._get(f"/api/public/traces/{trace_id}")
            session_id = trace.get("sessionId")
        except LangfuseApiError:
            logger.warning("langfuse.trace_unavailable", extra={"trace_id": trace_id})
            return None
        self._sessions[trace_id] = session_id
        if len(self._sessions) > _SESSION_CACHE_SIZE:
            self._sessions.popitem(last=False)
        return session_id

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET a Langfuse API path.

        Args:
            path (str): API path.
            params (Optional[Dict[str, Any]]): Query parameters.

        Returns:
            Dict[str, Any]: The decoded JSON body.

        Raises:
            LangfuseApiError: On an error status.
        """
        response = await self._client.get(path, params=params)
        if response.status_code >= 400:
            raise LangfuseApiError(f"Langfuse {path} failed ({response.status_code}): {response.text[:300]}")
        return response.json()
