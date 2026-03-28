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


@pytest.mark.asyncio
async def test_list_users_tolerates_missing_optional_fields(monkeypatch):
    """Optional fields should not fail projection when omitted by Grafana."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "userId": 1,
                    "name": "Alice",
                    "lastSeenAtAge": "1d",
                },
                {
                    "userId": 2,
                    "name": "Bob",
                },
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

    users = await connector.list_users(fields=["userId", "lastSeenAtAge"])
    await connector.client.aclose()

    assert users == [
        {"userId": 1, "lastSeenAtAge": "1d"},
        {"userId": 2},
    ]


@pytest.mark.asyncio
async def test_search_dashboards_tolerates_missing_optional_fields(monkeypatch):
    """Dashboard field projection should allow optional folder metadata."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "uid": "general",
                    "title": "General",
                    "url": "/d/general",
                    "type": "dash-db",
                    "tags": [],
                },
                {
                    "uid": "ops",
                    "title": "Ops",
                    "url": "/d/ops",
                    "type": "dash-db",
                    "tags": ["ops"],
                    "folderUid": "folder-1",
                    "folderTitle": "Ops Folder",
                },
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

    dashboards = await connector.search_dashboards(fields=["uid", "folderUid"])
    await connector.client.aclose()

    assert dashboards == [
        {"uid": "general"},
        {"uid": "ops", "folderUid": "folder-1"},
    ]


@pytest.mark.asyncio
async def test_search_dashboards_allows_additional_grafana_search_fields(monkeypatch):
    """Dashboard search projection should preserve broader Grafana response fields."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": 7,
                    "orgId": 1,
                    "uid": "ops",
                    "title": "Ops",
                    "uri": "db/ops",
                    "url": "/d/ops",
                    "slug": "ops",
                    "type": "dash-db",
                    "tags": ["ops"],
                    "isStarred": False,
                    "folderId": 10,
                    "folderUid": "folder-1",
                    "folderTitle": "Ops Folder",
                    "folderUrl": "/dashboards/f/folder-1/ops-folder",
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
        fields=["id", "folderUrl", "uri", "isStarred"]
    )
    await connector.client.aclose()

    assert dashboards == [
        {
            "id": 7,
            "folderUrl": "/dashboards/f/folder-1/ops-folder",
            "uri": "db/ops",
            "isStarred": False,
        }
    ]


@pytest.mark.asyncio
async def test_list_folder_dashboards_allows_additional_grafana_search_fields(
    monkeypatch,
):
    """Folder dashboard projection should accept the broader Grafana search schema."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["folderUids"] == "folder-1"
        return httpx.Response(
            200,
            json=[
                {
                    "id": 9,
                    "uid": "folder-dash",
                    "title": "Folder Dash",
                    "uri": "db/folder-dash",
                    "url": "/d/folder-dash",
                    "type": "dash-db",
                    "folderId": 10,
                    "folderUid": "folder-1",
                    "folderTitle": "Ops Folder",
                    "folderUrl": "/dashboards/f/folder-1/ops-folder",
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

    dashboards = await connector.list_folder_dashboards(
        "folder-1", fields=["id", "folderUrl", "folderId"]
    )
    await connector.client.aclose()

    assert dashboards == [
        {
            "id": 9,
            "folderUrl": "/dashboards/f/folder-1/ops-folder",
            "folderId": 10,
        }
    ]


@pytest.mark.asyncio
async def test_list_users_allows_additional_org_user_fields(monkeypatch):
    """Org user projection should preserve valid Grafana fields beyond the narrow core."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "orgId": 1,
                    "userId": 11,
                    "avatarUrl": "/avatar/11",
                    "email": "ops@example.com",
                    "name": "Ops",
                    "login": "ops",
                    "role": "Viewer",
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

    users = await connector.list_users(fields=["orgId", "avatarUrl"])
    await connector.client.aclose()

    assert users == [{"orgId": 1, "avatarUrl": "/avatar/11"}]


@pytest.mark.asyncio
async def test_list_teams_allows_additional_team_fields(monkeypatch):
    """Team projection should preserve valid Grafana fields beyond the narrow core."""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="token",
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "teams": [
                    {
                        "id": 3,
                        "orgId": 1,
                        "uid": "ops-team",
                        "name": "Ops",
                        "avatarUrl": "/avatar/team/3",
                        "email": "ops@example.com",
                        "memberCount": 4,
                    }
                ]
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

    teams = await connector.list_teams(fields=["orgId", "avatarUrl"])
    await connector.client.aclose()

    assert teams == [{"orgId": 1, "avatarUrl": "/avatar/team/3"}]


def test_field_filtering_rejects_invalid_keys():
    """Ensures requesting unsupported fields raises a ValueError."""

    with pytest.raises(ValueError):
        GrafanaConnector._filter_fields(
            {"uid": "u1", "title": "Dash"},
            requested_fields=["not-real"],
            allowed_fields=["uid", "title"],
        )


def test_field_filtering_allows_response_keys_outside_known_baseline():
    """Response-provided fields should remain projectable even if the baseline schema lags."""

    projected = GrafanaConnector._filter_fields(
        {"uid": "u1", "folderUrl": "/dashboards/f/ops"},
        requested_fields=["folderUrl"],
        allowed_fields=["uid"],
    )

    assert projected == {"folderUrl": "/dashboards/f/ops"}
