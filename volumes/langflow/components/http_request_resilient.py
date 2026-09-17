"""HTTP Request (Resilient): async httpx client with an explicit retry/failure policy.

The native "API Request" component (langflow/components/data/api_request.py)
makes HTTP calls with httpx but has no notion of retries or which failures
are transient vs. definitive - a 404 and a 503 are handled identically.
This component adds that policy layer on top of httpx.AsyncClient:

- Only 429/500/502/503/504 (configurable) and network-level errors
  (httpx.RequestError - timeouts, connection refused, DNS failures) are
  retried, with exponential backoff (respecting a server's Retry-After
  header when present). Any other 4xx (400/401/403/404/409/422/...) fails
  immediately - retrying a "forbidden" or "not found" wastes time and can
  look like hammering the external API.
- By default (`raise_on_failure=False`) a failure - retries exhausted or a
  non-retryable status - never raises. It comes back as a plain
  `{"success": false, ...}` Data, the same shape as a success but with
  `success` flipped, so the rest of the flow can branch on it explicitly
  instead of the flow's execution just stopping. This matters most for an
  Agent tool call mid-conversation (a raised exception there can kill the
  whole turn), less so for a batch flow, where downstream nodes still need
  an explicit `success` check before acting on `data` - this component
  only guarantees a clean signal, not that callers use it.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from langflow.custom import Component
from langflow.io import BoolInput, DropdownInput, FloatInput, IntInput, Output, SecretStrInput, StrInput
from langflow.schema import Data

_DEFAULT_RETRYABLE_STATUS_CODES = "429,500,502,503,504"
_HTTP_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


class ResilientHTTPRequestComponent(Component):
    display_name = "HTTP Request (Resilient)"
    description = (
        "Request HTTP asíncrono (httpx) con política de reintentos explícita: reintenta "
        "solo códigos transitorios (429/5xx) y errores de red, con backoff exponencial; "
        "cualquier otro 4xx falla de una. Nunca revienta el flow por default - devuelve "
        "éxito/fallo en el mismo formato."
    )
    name = "ResilientHTTPRequest"
    icon = "Globe"

    inputs = [
        StrInput(name="url", display_name="URL", required=True, tool_mode=True),
        DropdownInput(name="method", display_name="Método", options=_HTTP_METHODS, value="GET"),
        StrInput(
            name="headers_json",
            display_name="Headers (JSON)",
            advanced=True,
            info='Objeto JSON, ej. \'{"Accept": "application/json"}\'.',
        ),
        StrInput(
            name="query_params_json",
            display_name="Query params (JSON)",
            advanced=True,
            info='Objeto JSON, ej. \'{"page": 1}\'.',
        ),
        StrInput(
            name="body_json",
            display_name="Body (JSON)",
            advanced=True,
            tool_mode=True,
            info="Objeto JSON para POST/PUT/PATCH. Vacío = sin body.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=False,
            info=(
                "Si se completa, se agrega a los headers en 'Header de autenticación' con el "
                "prefijo de 'Esquema'. Guardala como Global Variable (Credential) en vez de "
                "tipearla directo - así no queda en texto plano en el flow."
            ),
        ),
        StrInput(
            name="api_key_header",
            display_name="Header de autenticación",
            value="Authorization",
            advanced=True,
            info="Nombre del header HTTP que lleva la API key (ej. 'Authorization' o 'x-api-key').",
        ),
        StrInput(
            name="api_key_scheme",
            display_name="Esquema (prefijo)",
            value="Bearer",
            advanced=True,
            info="Prefijo antes de la key en el header (ej. 'Bearer'). Vacío para headers tipo x-api-key, que llevan la key sin prefijo.",
        ),
        FloatInput(name="timeout", display_name="Timeout (segundos)", value=10, advanced=True),
        IntInput(name="max_retries", display_name="Reintentos máximos", value=3, advanced=True),
        FloatInput(name="retry_backoff_base", display_name="Backoff base (segundos)", value=0.5, advanced=True),
        FloatInput(name="retry_backoff_max", display_name="Backoff máximo (segundos)", value=8.0, advanced=True),
        StrInput(
            name="retryable_status_codes",
            display_name="Códigos reintentables",
            value=_DEFAULT_RETRYABLE_STATUS_CODES,
            advanced=True,
            info="CSV de códigos HTTP considerados transitorios (se reintentan). Cualquier otro 4xx falla de una.",
        ),
        BoolInput(
            name="retry_on_network_error",
            display_name="Reintentar errores de red",
            value=True,
            advanced=True,
            info="Timeouts de conexión/lectura, DNS, connection refused - también se consideran transitorios.",
        ),
        BoolInput(
            name="respect_retry_after",
            display_name="Respetar header Retry-After",
            value=True,
            advanced=True,
        ),
        BoolInput(
            name="raise_on_failure",
            display_name="Lanzar excepción en fallo",
            value=False,
            advanced=True,
            info=(
                "Default false: nunca revienta el flow, devuelve {success: false, ...}. "
                "Activar solo donde realmente convenga detener el flow en seco."
            ),
        ),
    ]

    outputs = [
        Output(display_name="Respuesta", name="response", method="make_request"),
    ]

    def _parse_json_object_field(self, value: str, field_label: str) -> dict:
        """Parses a JSON-object input field, allowing it to be empty.

        Args:
            value (str): Raw field content.
            field_label (str): Display name, used in error messages.

        Returns:
            dict: The parsed object, or `{}` if `value` is empty or whitespace-only.

        Raises:
            ValueError: If `value` is set but isn't valid JSON, or isn't a JSON object.
        """
        if not value or not value.strip():
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            msg = f"'{field_label}' no es JSON válido: {exc}"
            raise ValueError(msg) from exc
        if not isinstance(parsed, dict):
            msg = f"'{field_label}' debe ser un objeto JSON."
            raise ValueError(msg)
        return parsed

    def _parse_retryable_codes(self) -> set[int]:
        """Parses `retryable_status_codes` into a set of ints.

        Returns:
            set[int]: The configured retryable status codes.

        Raises:
            ValueError: If any comma-separated entry isn't a valid integer.
        """
        codes = set()
        for part in (self.retryable_status_codes or "").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                codes.add(int(part))
            except ValueError as exc:
                msg = f"'{part}' no es un código HTTP válido en 'Códigos reintentables'."
                raise ValueError(msg) from exc
        return codes

    def _compute_backoff(self, attempt: int) -> float:
        """Computes the exponential backoff delay for a given attempt number.

        Args:
            attempt (int): 1-indexed attempt number that just failed.

        Returns:
            float: Delay in seconds before the next attempt, capped at `retry_backoff_max`.
        """
        delay = self.retry_backoff_base * (2 ** (attempt - 1))
        return min(delay, self.retry_backoff_max)

    def _succeed(self, response: httpx.Response, attempts: int) -> Data:
        """Builds the success envelope from a 2xx/3xx response.

        Args:
            response (httpx.Response): The successful response.
            attempts (int): Total attempts made, including this one.

        Returns:
            Data: `{success: true, status_code, data, error: null, attempts, url}`.
        """
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text
        result = {
            "success": True,
            "status_code": response.status_code,
            "data": payload,
            "error": None,
            "attempts": attempts,
            "url": str(response.url),
        }
        self.status = result
        return Data(data=result)

    def _fail(self, error: str, status_code: int | None, attempts: int, body: str | None = None) -> Data:
        """Builds the failure envelope, or raises if `raise_on_failure` is set.

        Args:
            error (str): Human-readable failure reason.
            status_code (int | None): HTTP status code, or None for network-level failures.
            attempts (int): Total attempts made.
            body (str | None): Raw response body, if any was received.

        Returns:
            Data: `{success: false, status_code, data: null, error, attempts, url}`.

        Raises:
            ValueError: If `raise_on_failure` is True.
        """
        result = {
            "success": False,
            "status_code": status_code,
            "data": None,
            "error": error,
            "attempts": attempts,
            "url": self.url,
            "raw_body": body,
        }
        self.status = result
        if self.raise_on_failure:
            msg = f"HTTP request a '{self.url}' falló tras {attempts} intento(s): {error}"
            raise ValueError(msg)
        return Data(data=result)

    async def make_request(self) -> Data:
        """Runs the configured request, retrying transient failures per the policy above.

        Returns:
            Data: The success or failure envelope (see `_succeed`/`_fail`).
        """
        retryable_codes = self._parse_retryable_codes()
        headers = self._parse_json_object_field(self.headers_json, "Headers (JSON)")
        if self.api_key:
            value = f"{self.api_key_scheme} {self.api_key}".strip() if self.api_key_scheme else self.api_key
            headers = {**headers, self.api_key_header: value}
        params = self._parse_json_object_field(self.query_params_json, "Query params (JSON)")
        json_body = self._parse_json_object_field(self.body_json, "Body (JSON)")

        last_error = "unknown error"
        attempts = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 2):
                attempts = attempt
                try:
                    response = await client.request(
                        method=self.method,
                        url=self.url,
                        headers=headers or None,
                        params=params or None,
                        json=json_body or None,
                    )
                except httpx.RequestError as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    if self.retry_on_network_error and attempt <= self.max_retries:
                        await asyncio.sleep(self._compute_backoff(attempt))
                        continue
                    return self._fail(last_error, status_code=None, attempts=attempts)

                if response.status_code < 400:
                    return self._succeed(response, attempts)

                last_error = f"HTTP {response.status_code}"
                if response.status_code in retryable_codes and attempt <= self.max_retries:
                    delay = self._compute_backoff(attempt)
                    if self.respect_retry_after:
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = max(delay, float(retry_after))
                            except ValueError:
                                pass
                    await asyncio.sleep(delay)
                    continue

                return self._fail(last_error, status_code=response.status_code, attempts=attempts, body=response.text)

        return self._fail(last_error, status_code=None, attempts=attempts)
