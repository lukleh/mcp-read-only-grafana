"""Tests for Grafana provisioning alert rules endpoint"""

import httpx
import pytest

from mcp_read_only_grafana.config import GrafanaConnection
from mcp_read_only_grafana.grafana_connector import GrafanaConnector


@pytest.mark.asyncio
async def test_list_provisioned_alert_rules(monkeypatch):
    """Ensure provisioning alert rules endpoint is wired correctly"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=[
                {
                    "uid": "rule-1",
                    "title": "Example rule",
                    "folderUid": "folder",
                    "condition": "A",
                }
            ],
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

    rules = await connector.list_provisioned_alert_rules()

    await connector.client.aclose()

    assert rules[0]["uid"] == "rule-1"
    assert "/api/v1/provisioning/alert-rules" in captured["url"]
