"""Tests for pagination and field filtering helpers"""

import httpx
import pytest

from src.config import GrafanaConnection
from src.grafana_connector import GrafanaConnector


@pytest.mark.asyncio
async def test_search_dashboards_supports_pagination_and_fields(monkeypatch):
    """search_dashboards forwards pagination params and filters fields."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    captured: dict[str, dict] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "uid": "u1",
                    "title": "Dash 1",
                    "url": "/d/u1",
                    "type": "dash-db",
                    "tags": ["a"],
                    "folderTitle": "Ops",
                    "folderUid": "ops",
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

    dashboards = await connector.search_dashboards(
        query="error",
        limit=10,
        page=2,
        fields=["uid", "title"],
    )
    await connector.client.aclose()

    assert captured["params"]["limit"] == "10"
    assert captured["params"]["page"] == "2"
    assert dashboards == [{"uid": "u1", "title": "Dash 1"}]


@pytest.mark.asyncio
async def test_list_users_supports_pagination_and_field_projection(monkeypatch):
    """list_users forwards pagination params and reduces payload."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    captured: dict[str, dict] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json=[
                {
                    "userId": 1,
                    "email": "ops@example.com",
                    "name": "Ops",
                    "login": "ops",
                    "role": "Viewer",
                    "lastSeenAt": "2024-01-01T00:00:00Z",
                    "lastSeenAtAge": "30d",
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

    users = await connector.list_users(page=3, per_page=20, fields=["userId", "email"])
    await connector.client.aclose()

    assert captured["params"]["page"] == "3"
    assert captured["params"]["perpage"] == "20"
    assert users == [{"userId": 1, "email": "ops@example.com"}]


def test_field_filtering_rejects_invalid_keys():
    """Ensures requesting unsupported fields raises a ValueError."""

    with pytest.raises(ValueError):
        GrafanaConnector._filter_fields(
            {"uid": "u1", "title": "Dash"},
            requested_fields=["not-real"],
            allowed_fields=["uid", "title"],
        )
