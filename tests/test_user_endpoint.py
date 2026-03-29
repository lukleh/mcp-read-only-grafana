"""Tests for the /api/user endpoint integration"""

import httpx
import pytest

from mcp_read_only_grafana.config import GrafanaConnection
from mcp_read_only_grafana.grafana_connector import GrafanaConnector


@pytest.mark.asyncio
async def test_get_current_user(monkeypatch):
    """Verify get_current_user hits /api/user and returns raw payload."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    called = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["path"] = request.url.path
        return httpx.Response(
            200,
            json={
                "id": 42,
                "login": "viewer",
                "email": "viewer@example.com",
                "role": "Viewer",
            },
        )

    connector = GrafanaConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        cookies={"grafana_session": connection.session_token or ""},
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )

    user = await connector.get_current_user()
    await connector.client.aclose()

    assert called["path"].endswith("/api/user")
    assert user["login"] == "viewer"
