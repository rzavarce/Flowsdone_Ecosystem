"""Langflow admin client: provisions per-tenant users/folders and logs them in.

Uses the gateway's Langflow API key (a superuser's) to create and activate
users, and each tenant user's own login token to create their folders.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.domain.ports.outbound import (
    LangflowAdminPort,
    LangflowFlowSummary,
    LangflowSessionError,
    LangflowTokens,
)


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
        if created.status_code == 201:
            user_id = self._json(created, "create user")["id"]
        else:
            # Already there (an earlier attempt died half-way): find it and
            # bring its password back in line with the stored one.
            listing = await self._request("GET", "/api/v1/users/", params={"limit": 1000}, headers=headers)
            if listing.status_code != 200:
                raise LangflowSessionError(f"langflow rejected create user (HTTP {created.status_code})")
            found = [u for u in self._json(listing, "list users").get("users", []) if u.get("username") == username]
            if not found:
                raise LangflowSessionError(f"langflow rejected create user (HTTP {created.status_code})")
            user_id = found[0]["id"]
            reset = await self._request(
                "PATCH", f"/api/v1/users/{user_id}/reset-password", json={"password": password}, headers=headers
            )
            if reset.status_code != 200:
                raise LangflowSessionError(f"langflow rejected reset password (HTTP {reset.status_code})")
        # New users start inactive (LANGFLOW_NEW_USER_IS_ACTIVE=false).
        activated = await self._request(
            "PATCH", f"/api/v1/users/{user_id}", json={"is_active": True}, headers=headers
        )
        if activated.status_code != 200:
            raise LangflowSessionError(f"langflow rejected activate user (HTTP {activated.status_code})")
        return str(user_id)

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

