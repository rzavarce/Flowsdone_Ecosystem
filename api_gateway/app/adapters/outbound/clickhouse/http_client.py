"""Minimal async client for ClickHouse's HTTP interface (plain httpx -
no extra client library), shared by the ClickHouse adapters.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import httpx

logger = logging.getLogger("clickhouse.http")


class ClickHouseError(Exception):
    """Raised when ClickHouse answers a query with an error."""


class ClickHouseHttpClient:
    """Runs inserts and parameterized selects against one database.

    Query values are always sent as ClickHouse query parameters
    (`{name:Type}` placeholders + `param_name=`), never interpolated into
    the SQL text.
    """

    def __init__(
        self,
        *,
        base_url: str,
        database: str,
        user: str,
        password: Optional[str],
        timeout_seconds: float = 10.0,
    ) -> None:
        """Build the client.

        Args:
            base_url (str): ClickHouse HTTP endpoint (e.g. http://clickhouse:8123).
            database (str): Database the tables live in.
            user (str): ClickHouse user.
            password (Optional[str]): Password of that user.
            timeout_seconds (float): HTTP timeout per request.
        """
        headers = {"X-ClickHouse-User": user}
        if password:
            headers["X-ClickHouse-Key"] = password
        self.database = database
        self._client = httpx.AsyncClient(
            base_url=base_url, headers=headers, timeout=httpx.Timeout(timeout_seconds)
        )

    async def insert_rows(self, table: str, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
        """Insert rows (JSONEachRow) into `<database>.<table>` in one request.

        Args:
            table (str): Table name.
            columns (Sequence[str]): Columns being inserted.
            rows (Iterable[Mapping[str, Any]]): Rows, keyed by column.

        Raises:
            ClickHouseError: If ClickHouse rejects the insert.
        """
        body = "\n".join(json.dumps(row) for row in rows)
        if not body:
            return
        query = f"INSERT INTO {self.database}.{table} ({', '.join(columns)}) FORMAT JSONEachRow"
        await self._post(
            {"query": query, "date_time_input_format": "best_effort"}, content=body.encode("utf-8")
        )

    async def select(self, sql: str, params: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
        """Run a SELECT and return its rows.

        Args:
            sql (str): Query using `{name:Type}` placeholders; `{db}` is
                replaced with the database name. Must not end in FORMAT.
            params (Optional[Mapping[str, Any]]): Placeholder values.

        Returns:
            List[Dict[str, Any]]: One dict per row.

        Raises:
            ClickHouseError: If the query fails.
        """
        query_params = {f"param_{k}": str(v) for k, v in (params or {}).items()}
        # Selects alias columns to their own name (`toString(x) AS x`) to
        # get JSON-friendly values; filters must still see the column.
        query_params["prefer_column_name_to_alias"] = "1"
        text = await self._post(
            query_params,
            content=(sql.replace("{db}", self.database) + "\nFORMAT JSONEachRow").encode("utf-8"),
        )
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def _post(self, params: Mapping[str, str], *, content: bytes) -> str:
        """POST to the HTTP interface.

        Args:
            params (Mapping[str, str]): URL query parameters.
            content (bytes): Request body.

        Returns:
            str: Response body.

        Raises:
            ClickHouseError: On an error status.
        """
        response = await self._client.post("/", params=dict(params), content=content)
        if response.status_code >= 400:
            logger.error(
                "clickhouse.request_failed",
                extra={"status_code": response.status_code, "response_text": response.text[:500]},
            )
            raise ClickHouseError(f"ClickHouse error ({response.status_code}): {response.text[:500]}")
        return response.text
