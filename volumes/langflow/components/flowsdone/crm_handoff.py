"""Langflow tool: hand the current conversation over to a human in the
client's CRM (Flowsdone CRM handoff).

The Agent calls it when the contact asks for a person or the bot cannot
help. The gateway then stops sending this conversation to the flow: the
contact's next messages go to the CRM, and the bot takes over again when
the agent closes the ticket (or the conversation expires).
"""

from __future__ import annotations

import os

import httpx
from langflow.custom import Component
from langflow.io import IntInput, MessageTextInput, Output, StrInput
from langflow.schema import Data


class CrmHandoffComponent(Component):
    display_name = "Traspasar a CRM (Flowsdone)"
    description = (
        "Pasa la conversación a una persona del equipo del cliente, en su CRM. Úsalo cuando el "
        "cliente pida hablar con una persona o no puedas resolver su caso. Después de usarlo, "
        "despídete diciendo que una persona continuará la conversación; no sigas respondiendo."
    )
    name = "CrmHandoff"
    icon = "UserRoundCheck"

    inputs = [
        MessageTextInput(
            name="reason",
            display_name="Motivo",
            tool_mode=True,
            info="Por qué se pasa a una persona (lo verá el agente en el CRM), breve.",
        ),
        StrInput(
            name="gateway_url",
            display_name="URL del gateway",
            advanced=True,
            info="Vacío = variable de entorno GATEWAY_INTERNAL_URL del contenedor.",
        ),
        IntInput(name="timeout", display_name="Timeout (s)", value=10, advanced=True),
    ]

    outputs = [
        Output(display_name="Resultado", name="result", method="hand_over"),
    ]

    async def hand_over(self) -> Data:
        """Ask the gateway to hand this conversation over to the CRM.

        Returns:
            Data: `success`, and `error` when it could not be done (no CRM
            set up for the project, conversation not found...).
        """
        result = await self._hand_over()
        self.status = result
        return Data(data=result)

    async def _hand_over(self) -> dict:
        """Call POST /internal/admin/crm-handoffs with this flow's session.

        Returns:
            dict: The outcome for the Agent.
        """
        base_url = (self.gateway_url or os.environ.get("GATEWAY_INTERNAL_URL") or "").rstrip("/")
        api_key = os.environ.get("GATEWAY_ADMIN_API_KEY")
        session_id = getattr(getattr(self, "graph", None), "session_id", None)
        if not base_url or not api_key:
            return {"success": False, "error": "El traspaso no está configurado (GATEWAY_INTERNAL_URL / GATEWAY_ADMIN_API_KEY)."}
        if not session_id:
            return {"success": False, "error": "No hay conversación activa que traspasar."}

        try:
            async with httpx.AsyncClient(timeout=self.timeout or 10) as client:
                response = await client.post(
                    f"{base_url}/internal/admin/crm-handoffs",
                    headers={"X-Admin-Api-Key": api_key},
                    json={"conversation_id": str(session_id), "reason": (self.reason or "").strip()[:500] or None},
                )
        except httpx.HTTPError as exc:
            return {"success": False, "error": f"No se pudo contactar con el gateway: {exc}"}

        if response.status_code == 201:
            return {"success": True, "message": "Conversación traspasada: una persona continuará."}
        if response.status_code == 409:
            return {"success": False, "error": "Este proyecto no tiene un CRM configurado para traspasar conversaciones."}
        return {"success": False, "error": f"El gateway respondió {response.status_code}."}
