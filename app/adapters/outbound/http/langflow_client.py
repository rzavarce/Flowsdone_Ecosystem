import httpx
from app.core.config import settings

class LangflowClient:
    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url=settings.langflow_base_url,
            headers={"Authorization": f"Bearer {settings.langflow_api_key}"}
        )

    async def run_flow(self, flow_id: str, payload: dict):
        response = await self.client.post(
            f"/api/v1/run/{flow_id}",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()