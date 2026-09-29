"""Guardar contacto (Flowsdone): lets an Agent write down who it is talking to.

The console's Conversaciones shows each conversation's contact by the
identifier its channel gives (a phone number, "client:demo-...", a visitor
id). When the customer tells the Agent their name, email or phone, this
tool stores it on the contact's card, so staff see "Ana Pérez" instead.

The conversation is not an argument the model could get wrong: the gateway
runs every flow with the conversation's id as Langflow's session id, so the
component reads it from the running graph. Runs without a registered
conversation (the Langflow playground, "Probar en webchat") have no card to
fill and are answered without calling the gateway.

The gateway only fills fields the card doesn't have yet, so a name staff
typed is never replaced by a (maybe misheard) one, and ignores empty ones.
It is called with the admin API key from the container's environment
(GATEWAY_INTERNAL_URL, GATEWAY_ADMIN_API_KEY), never typed into the flow.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from langflow.custom import Component
from langflow.io import IntInput, Output, StrInput
from langflow.schema import Data

# Tool-mode inputs and their defaults; see `_reset_tool_arguments`.
_TOOL_ARGUMENT_DEFAULTS = {"contact_name": "", "contact_email": "", "contact_phone": ""}


class ContactError(ValueError):
    """A save that can't be done; its message is meant for the Agent."""


class SaveContactComponent(Component):
    display_name = "Guardar contacto (Flowsdone)"
    description = (
        "Guarda el nombre, email o teléfono que el cliente te ha dado, para que el equipo sepa "
        "con quién hablaste. Úsalo en cuanto el cliente te diga alguno de esos datos. Envía solo "
        "los datos que el cliente ha dicho; deja vacíos los demás."
    )
    name = "SaveContact"
    icon = "UserPen"

    inputs = [
        StrInput(
            name="gateway_url",
            display_name="URL del gateway",
            advanced=True,
            info="Vacío = la variable de entorno GATEWAY_INTERNAL_URL del contenedor.",
        ),
        IntInput(name="timeout", display_name="Timeout (s)", value=10, advanced=True),
        StrInput(
            name="contact_name",
            display_name="Nombre",
            tool_mode=True,
            info="Nombre y apellidos del cliente, tal como los dijo. Vacío si no lo sabes.",
        ),
        StrInput(
            name="contact_email",
            display_name="Email",
            tool_mode=True,
            info="Email del cliente. Vacío si no lo sabes.",
        ),
        StrInput(
            name="contact_phone",
            display_name="Teléfono",
            tool_mode=True,
            info="Teléfono del cliente, con prefijo si lo dio. Vacío si no lo sabes.",
        ),
    ]

    outputs = [
        Output(display_name="Resultado", name="result", method="save_contact"),
    ]

    async def save_contact(self) -> Data:
        """Stores what the Agent learned on the conversation's contact card.

        Returns:
            Data: `success` plus, on success, `saved` (the fields sent) and
            `contact` (the card as stored); otherwise `error` or `skipped`.
        """
        try:
            result = await self._save()
        except ContactError as exc:
            result = {"success": False, "error": str(exc)}
        finally:
            self._reset_tool_arguments()
        self.status = result
        return Data(data=result)

    def _reset_tool_arguments(self) -> None:
        """Puts the tool-mode inputs back to their defaults after a call.

        Langflow reuses this component instance for every call of the tool and
        only sets the arguments the Agent sent, so a value from a previous
        call would otherwise leak into the next one.
        """
        self.set(**_TOOL_ARGUMENT_DEFAULTS)

    async def _save(self) -> dict[str, Any]:
        """Validates the arguments and posts them to the gateway.

        Returns:
            dict[str, Any]: The result payload returned by `save_contact`.

        Raises:
            ContactError: If nothing was given, the gateway isn't configured
                or it rejected the values.
        """
        fields = {
            "name": " ".join((self.contact_name or "").split()),
            "email": (self.contact_email or "").strip(),
            "phone": " ".join((self.contact_phone or "").split()),
        }
        fields = {key: value for key, value in fields.items() if value}
        if not fields:
            msg = "No hay datos que guardar: indica al menos el nombre, el email o el teléfono."
            raise ContactError(msg)

        conversation_id = self._conversation_id()
        if conversation_id is None:
            # Playground / "Probar en webchat": nothing is recorded, so there is
            # no card; the Agent can carry on as if it was saved.
            return {"success": True, "skipped": "Esta conversación de prueba no se registra.", "saved": fields}

        base_url = (self.gateway_url or os.environ.get("GATEWAY_INTERNAL_URL", "")).strip().rstrip("/")
        api_key = os.environ.get("GATEWAY_ADMIN_API_KEY", "")
        if not base_url or not api_key:
            msg = "El componente no está configurado (faltan GATEWAY_INTERNAL_URL o GATEWAY_ADMIN_API_KEY)."
            raise ContactError(msg)

        url = f"{base_url}/internal/admin/conversations/{conversation_id}/contact/capture"
        try:
            async with httpx.AsyncClient(timeout=self.timeout or 10) as client:
                response = await client.post(url, json=fields, headers={"X-Admin-Api-Key": api_key})
        except httpx.RequestError as exc:
            msg = f"No se pudo conectar con el gateway: {exc}"
            raise ContactError(msg) from exc
        if response.status_code == 404:
            return {"success": True, "skipped": "Esta conversación no está registrada.", "saved": fields}
        if response.status_code == 422:
            msg = f"Algún dato no es válido: {self._detail(response)}. Pide al cliente que lo repita."
            raise ContactError(msg)
        if response.status_code >= 300:
            msg = f"El gateway respondió con error HTTP {response.status_code}: {self._detail(response)}"
            raise ContactError(msg)
        return {"success": True, "saved": fields, "contact": response.json()}

    def _conversation_id(self) -> str | None:
        """The conversation this run belongs to.

        Returns:
            str | None: The graph's session id when it is a conversation id
            (a UUID, as the gateway sets it), else None.
        """
        graph = getattr(self, "graph", None)
        session_id = str(getattr(graph, "session_id", "") or "")
        try:
            return str(uuid.UUID(session_id))
        except ValueError:
            return None

    @staticmethod
    def _detail(response: Any) -> str:
        """The gateway's error message.

        Args:
            response (Any): The httpx response.

        Returns:
            str: Its `detail`, or the start of the body.
        """
        try:
            detail = response.json().get("detail", "")
        except ValueError:
            detail = response.text[:200]
        return str(detail)
