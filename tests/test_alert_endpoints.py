"""Focused tests for Grafana alert-related connector behavior."""

import httpx
import pytest

from src.config import GrafanaConnection
from src.grafana_connector import GrafanaConnector
from src.exceptions import GrafanaAPIError


def create_mock_connector(connection, handler):
    connector = GrafanaConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        cookies={"grafana_session": connection.session_token or ""},
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    return connector


@pytest.fixture
def session_connection(monkeypatch):
    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_session_token")
    return GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_session_token",
    )


@pytest.mark.asyncio
async def test_get_alert_rule_by_uid_searches_ruler_payload(session_connection):
    """Alert-rule lookup should scan the Ruler payload instead of treating the UID as a namespace."""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ruler/grafana/api/v1/rules"
        return httpx.Response(
            200,
            json={
                "Operations": [
                    {
                        "name": "cpu",
                        "interval": "1m",
                        "rules": [
                            {
                                "grafana_alert": {
                                    "uid": "rule-123",
                                    "title": "High CPU",
                                }
                            }
                        ],
                    }
                ]
            },
        )

    connector = create_mock_connector(session_connection, handler)
    result = await connector.get_alert_rule_by_uid("rule-123")
    await connector.client.aclose()

    assert result["grafana_alert"]["title"] == "High CPU"
    assert result["namespace"] == "Operations"
    assert result["group"] == "cpu"
    assert result["group_interval"] == "1m"


@pytest.mark.asyncio
async def test_get_alert_rule_by_uid_raises_not_found(session_connection):
    """Missing alert rules should surface as GrafanaAPIError."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Operations": []})

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(GrafanaAPIError) as exc_info:
        await connector.get_alert_rule_by_uid("missing")

    await connector.client.aclose()
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_list_alerts_filters_by_folder_uid_or_title(session_connection):
    """Folder filters should match the exact folder title/uid instead of a prefix."""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/folders/folder-1":
            return httpx.Response(200, json={"uid": "folder-1", "title": "Operations"})
        if request.url.path == "/api/ruler/grafana/api/v1/rules":
            return httpx.Response(
                200,
                json={
                    "Operations": [
                        {
                            "name": "ops-group",
                            "interval": "1m",
                            "rules": [{"grafana_alert": {"uid": "ops-1", "title": "Ops"}}],
                        }
                    ],
                    "ops-staging": [
                        {
                            "name": "staging-group",
                            "interval": "1m",
                            "rules": [{"grafana_alert": {"uid": "staging-1", "title": "Staging"}}],
                        }
                    ],
                },
            )
        raise AssertionError(f"Unexpected request: {request.url}")

    connector = create_mock_connector(session_connection, handler)
    result = await connector.list_alerts(folder_uid="folder-1")
    await connector.client.aclose()

    assert [alert["uid"] for alert in result] == ["ops-1"]


@pytest.mark.asyncio
async def test_list_annotations_preserves_dashboard_zero(session_connection):
    """dashboard_id=0 should still be forwarded to the Grafana API."""
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["query"] = request.url.query.decode()
        return httpx.Response(200, json=[])

    connector = create_mock_connector(session_connection, handler)
    result = await connector.list_annotations(dashboard_id=0)
    await connector.client.aclose()

    assert result == []
    assert "dashboardId=0" in captured["query"]
