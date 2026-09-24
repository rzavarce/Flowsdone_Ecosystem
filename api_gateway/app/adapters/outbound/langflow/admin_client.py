"""Langflow admin client: provisions per-tenant users/folders and logs them in.

Uses the gateway's Langflow API key (a superuser's) to create and activate
users, and each tenant user's own login token to create their folders.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.domain.ports.outbound import (
    AlreadyExistsError,
    LangflowAdminPort,
    LangflowFlowSummary,
    LangflowSessionError,
    LangflowTokens,
)


# Langflow 1.4's "Memory Chatbot" starter project (without its notes): chat
# input -> memory -> prompt -> OpenAI -> chat output. Kept in the repo so what
# gets created does not depend on which starter projects a Langflow ships.
# Langflow's per-user default folder (DEFAULT_FOLDER_NAME in Langflow 1.4);
# its editor labels it "Starter Project".
DEFAULT_FOLDER_NAME = "My Projects"

_BASE_AGENT_TEMPLATE = Path(__file__).parent / "templates" / "base_agent.json"
# Conversation turns fed back to the model: enough context for a chat,
# bounded so a long conversation does not grow the LLM cost per message.
_BASE_AGENT_MEMORY_MESSAGES = 20
_BASE_AGENT_TEMPERATURE = 0.3


def _handle_id(handle: Dict[str, Any]) -> str:
    """Serialize an edge handle exactly like Langflow's editor does.

    The editor rebuilds every edge's handle string from the nodes when it
    opens a flow and DROPS any edge whose stored string differs character
    for character: JSON with sorted keys and no spaces, `"` replaced by `œ`
    (its `scapedJSONStringfy`). Handles serialized any other way (e.g. with
    the `", "`/`": "` separators the starter-projects API returns) make the
    flow open with no connections.

    Args:
        handle (Dict[str, Any]): The handle (edge `data.sourceHandle` or
            `data.targetHandle`).

    Returns:
        str: The handle string.
    """
    return json.dumps(handle, sort_keys=True, separators=(",", ":"), ensure_ascii=False).replace('"', "œ")


def build_base_agent_flow(name: str, system_prompt: str) -> Dict[str, Any]:
    """The request body that creates a base agent flow.

    The OpenAI component is left WITHOUT an API key (no value, no global
    variable): each client's key is set by hand in the editor, and the
    onboarding checklist flags the agent until it is.

    Args:
        name (str): Flow name.
        system_prompt (str): The agent's instructions (no template variables).

    Returns:
        Dict[str, Any]: Flow payload for `POST /api/v1/flows/`.
    """
    template = json.loads(_BASE_AGENT_TEMPLATE.read_text(encoding="utf-8"))
    flow = copy.deepcopy(template)
    for node in flow["data"]["nodes"]:
        kind = node["data"].get("type")
        fields = node["data"]["node"]["template"]
        if kind == "Prompt":
            fields["template"]["value"] = f"{system_prompt}\n\nHistorial de la conversación:\n{{memory}}\n"
        elif kind == "Memory":
            fields["n_messages"]["value"] = _BASE_AGENT_MEMORY_MESSAGES
        elif kind == "OpenAIModel":
            fields["temperature"]["value"] = _BASE_AGENT_TEMPERATURE
            fields["api_key"]["value"] = ""
            fields["api_key"]["load_from_db"] = False
    for edge in flow["data"]["edges"]:
        source = _handle_id(edge["data"]["sourceHandle"])
        target = _handle_id(edge["data"]["targetHandle"])
        edge["sourceHandle"], edge["targetHandle"] = source, target
        edge["id"] = f"reactflow__edge-{edge['source']}{source}-{edge['target']}{target}"
    flow["name"] = name
    flow["description"] = "Agente base creado por el alta de cliente de Flowsdone."
    flow["endpoint_name"] = None
    return flow


class LangflowAdminClient(LangflowAdminPort):
    """httpx implementation of LangflowAdminPort against the Langflow REST API."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None) -> None:
        """Build the client.

        Args:
            client (Optional[httpx.AsyncClient]): HTTP client to use; one
                pointing at `LANGFLOW_BASE_URL` is created when omitted.
        """
        self._client = client or httpx.AsyncClient(
            base_url=settings.LANGFLOW_BASE_URL, timeout=httpx.Timeout(20.0)
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @staticmethod
    def _key_headers() -> Dict[str, str]:
        """Headers carrying the gateway's Langflow API key."""
        if not settings.LANGFLOW_API_KEY:
            raise LangflowSessionError("LANGFLOW_API_KEY is not configured")
        return {"x-api-key": settings.LANGFLOW_API_KEY}

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send a request, turning network failures into `LangflowSessionError`.

        Args:
            method (str): HTTP method.
            path (str): Path under the Langflow base URL.
            **kwargs (Any): Passed to httpx.

        Returns:
            httpx.Response: The response (any status).

        Raises:
            LangflowSessionError: If Langflow cannot be reached.
        """
        try:
            return await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise LangflowSessionError(f"langflow unreachable: {exc.__class__.__name__}") from exc

    @staticmethod
    def _json(response: httpx.Response, what: str) -> Any:
        """Parse a JSON body, failing clearly when Langflow answers with something else.

        Args:
            response (httpx.Response): The response to parse.
            what (str): What was being done, for the error message.

        Returns:
            Any: The decoded body.

        Raises:
            LangflowSessionError: If the body is not JSON.
        """
        try:
            return response.json()
        except ValueError as exc:
            raise LangflowSessionError(f"langflow returned a non-JSON body for {what}") from exc

    async def ensure_user(self, username: str, password: str) -> str:
        """Create the user (active), or reset the password of the existing one.

        Args:
            username (str): Langflow login name.
            password (str): Password the user must end up with.

        Returns:
            str: The user's id inside Langflow.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        headers = self._key_headers()
        created = await self._request(
            "POST", "/api/v1/users/", json={"username": username, "password": password}, headers=headers
        )
        # New users start inactive (LANGFLOW_NEW_USER_IS_ACTIVE=false).
        update: Dict[str, Any] = {"is_active": True}
        if created.status_code == 201:
            user_id = self._json(created, "create user")["id"]
        else:
            # Already there (an earlier attempt died half-way, or the tenant
            # was deleted and created again with the same slug - deleting a
            # tenant does not delete its Langflow user): find it and bring its
            # password back in line with the stored one. Through
            # `PATCH /users/{id}`, the only way a superuser may set another
            # user's password: `/reset-password` only lets users change their
            # own and answers 400 ("You can't change another user's password").
            listing = await self._request("GET", "/api/v1/users/", params={"limit": 1000}, headers=headers)
            if listing.status_code != 200:
                raise LangflowSessionError(f"langflow rejected create user (HTTP {created.status_code})")
            found = [u for u in self._json(listing, "list users").get("users", []) if u.get("username") == username]
            if not found:
                raise LangflowSessionError(f"langflow rejected create user (HTTP {created.status_code})")
            user_id = found[0]["id"]
            update["password"] = password
        updated = await self._request("PATCH", f"/api/v1/users/{user_id}", json=update, headers=headers)
        if updated.status_code != 200:
            raise LangflowSessionError(f"langflow rejected update user (HTTP {updated.status_code})")
        return str(user_id)

    async def delete_user(self, langflow_user_id: str) -> None:
        """Delete a Langflow user; Langflow deletes its folders and flows too.

        Args:
            langflow_user_id (str): Id of the user inside Langflow. One that
                no longer exists is not an error.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "DELETE", f"/api/v1/users/{langflow_user_id}", headers=self._key_headers()
        )
        if response.status_code not in (200, 204, 404):
            raise LangflowSessionError(f"langflow rejected delete user (HTTP {response.status_code})")

    async def login(self, username: str, password: str) -> LangflowTokens:
        """Log a user in.

        Args:
            username (str): Langflow login name.
            password (str): The user's password.

        Returns:
            LangflowTokens: The tokens Langflow issued.

        Raises:
            LangflowSessionError: If the login is refused or Langflow is unreachable.
        """
        response = await self._request("POST", "/api/v1/login", data={"username": username, "password": password})
        if response.status_code != 200:
            raise LangflowSessionError(f"langflow login refused (HTTP {response.status_code})")
        body = self._json(response, "login")
        return LangflowTokens(access_token=body["access_token"], refresh_token=body.get("refresh_token", ""))

    async def list_projects(self, access_token: str) -> Dict[str, str]:
        """Projects (folders) of the logged-in user.

        Args:
            access_token (str): The user's access token.

        Returns:
            Dict[str, str]: Folder id -> name.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "GET", "/api/v1/projects/", headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise LangflowSessionError(f"langflow rejected list projects (HTTP {response.status_code})")
        return {str(p["id"]): p["name"] for p in self._json(response, "list projects")}

    async def create_project(self, access_token: str, name: str) -> str:
        """Create a project (folder) for the logged-in user.

        Args:
            access_token (str): The user's access token.
            name (str): Folder name.

        Returns:
            str: The new folder id.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "POST",
            "/api/v1/projects/",
            json={"name": name, "description": "", "components_list": [], "flows_list": []},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 201:
            raise LangflowSessionError(f"langflow rejected create project (HTTP {response.status_code})")
        return str(self._json(response, "create project")["id"])

    async def default_folder(self, access_token: str) -> str:
        """Id of the logged-in user's default folder.

        Langflow creates it for every user on login, named "My Projects"
        (its editor shows it as "Starter Project"). If it is missing anyway
        (deleted by hand), it is created again.

        Args:
            access_token (str): The user's access token.

        Returns:
            str: The folder id.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        folders = await self.list_projects(access_token)
        found = next((folder_id for folder_id, name in folders.items() if name == DEFAULT_FOLDER_NAME), None)
        return found or await self.create_project(access_token, DEFAULT_FOLDER_NAME)

    async def delete_project(self, access_token: str, folder_id: str) -> None:
        """Delete one of the logged-in user's projects (folders); Langflow
        deletes the flows inside it too.

        Args:
            access_token (str): The user's access token.
            folder_id (str): The folder. One that no longer exists (e.g.
                deleted by hand in the editor) is not an error.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "DELETE", f"/api/v1/projects/{folder_id}", headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code not in (204, 404):
            raise LangflowSessionError(f"langflow rejected delete project (HTTP {response.status_code})")

    async def list_flows(self, access_token: str, folder_id: str) -> List[LangflowFlowSummary]:
        """Flows (not components) in one of the logged-in user's folders.

        Uses `header_flows=true` so Langflow answers without each flow's
        graph (which can be large).

        Args:
            access_token (str): The user's access token.
            folder_id (str): The folder.

        Returns:
            List[LangflowFlowSummary]: The flows, by name.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "GET",
            "/api/v1/flows/",
            params={"folder_id": folder_id, "get_all": "true", "header_flows": "true", "remove_example_flows": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 200:
            raise LangflowSessionError(f"langflow rejected list flows (HTTP {response.status_code})")
        body = self._json(response, "list flows")
        items = body.get("items", []) if isinstance(body, dict) else body
        flows = [
            LangflowFlowSummary(
                id=str(f["id"]),
                name=f.get("name") or "",
                description=f.get("description"),
                updated_at=f.get("updated_at"),
            )
            for f in items
            # folder_id is also checked here: never list another folder's flows.
            if not f.get("is_component") and str(f.get("folder_id")) == folder_id
        ]
        return sorted(flows, key=lambda f: f.name.lower())

    async def create_base_flow(self, access_token: str, folder_id: str, *, name: str, system_prompt: str) -> str:
        """Create the base chat agent flow in a folder.

        Args:
            access_token (str): The user's access token.
            folder_id (str): Folder to create it in.
            name (str): Flow name.
            system_prompt (str): The agent's instructions.

        Returns:
            str: The new flow's id.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "POST",
            "/api/v1/flows/",
            json={**build_base_agent_flow(name, system_prompt), "folder_id": folder_id},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code != 201:
            raise LangflowSessionError(f"langflow rejected create flow (HTTP {response.status_code})")
        return str(self._json(response, "create flow")["id"])

    async def llm_key_configured(self, access_token: str, flow_id: str) -> Optional[bool]:
        """Whether a flow's LLM components have an API key set (a value or
        a global variable name) - never reads the key itself.

        Args:
            access_token (str): The owner's access token.
            flow_id (str): The flow.

        Returns:
            Optional[bool]: True if every component with an `api_key` field
            has one, False if any is empty, None if the flow has none.

        Raises:
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "GET", f"/api/v1/flows/{flow_id}", headers={"Authorization": f"Bearer {access_token}"}
        )
        if response.status_code != 200:
            raise LangflowSessionError(f"langflow rejected get flow (HTTP {response.status_code})")
        nodes = ((self._json(response, "get flow").get("data") or {}).get("nodes")) or []
        keys = [
            node["data"]["node"]["template"]["api_key"].get("value")
            for node in nodes
            if "api_key" in ((node.get("data") or {}).get("node") or {}).get("template", {})
        ]
        if not keys:
            return None
        return all(isinstance(k, str) and k.strip() for k in keys)

    async def rename_flow(self, access_token: str, flow_id: str, name: str) -> None:
        """Rename a flow.

        Flow names are unique per Langflow user (so per tenant, across its
        project folders). Langflow reports a clash as a 400 on SQLite and as
        a 500 carrying the database error on Postgres; both mention "unique".

        Args:
            access_token (str): The owner's access token.
            flow_id (str): The flow.
            name (str): Its new name.

        Raises:
            AlreadyExistsError: If the owner already has a flow with that name.
            LangflowSessionError: If Langflow rejects the request.
        """
        response = await self._request(
            "PATCH",
            f"/api/v1/flows/{flow_id}",
            json={"name": name},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if response.status_code == 200:
            return
        if response.status_code in (400, 500) and "unique" in response.text.lower():
            raise AlreadyExistsError(f"langflow flow name taken: {name}")
        raise LangflowSessionError(f"langflow rejected rename flow (HTTP {response.status_code})")

