"""Tests for Grafana dashboard save endpoint."""

import json

import httpx
import pytest

from mcp_read_only_grafana.config import GrafanaConnection
from mcp_read_only_grafana.grafana_connector import GrafanaConnector


def create_mock_connector(connection, handler):
    """Create a connector with a mock transport."""
    connector = GrafanaConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        headers=(
            {"Authorization": f"Bearer {connection.api_key}"}
            if connection.api_key
            else None
        ),
        cookies=(
            {"grafana_session": connection.session_token}
            if connection.session_token
            else None
        ),
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    return connector


@pytest.fixture
def session_connection(monkeypatch):
    """Create a connection using session token auth."""
    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_session_token")
    return GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_session_token",
    )


@pytest.mark.asyncio
async def test_save_dashboard_creates_new_dashboard(session_connection):
    """A new dashboard should be posted with the expected wrapper payload."""
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": 101,
                "uid": "new-dashboard",
                "url": "/d/new-dashboard/production-overview",
                "status": "success",
                "version": 1,
            },
        )

    connector = create_mock_connector(session_connection, handler)
    result = await connector.save_dashboard(
        dashboard={
            "id": None,
            "uid": None,
            "title": "Production Overview",
            "schemaVersion": 39,
            "panels": [],
        },
        folder_uid="ops-folder",
        message="Create production overview",
    )
    await connector.client.aclose()

    payload = json.loads(captured["body"])

    assert captured["method"] == "POST"
    assert "/api/dashboards/db" in captured["url"]
    assert payload["dashboard"]["title"] == "Production Overview"
    assert payload["folderUid"] == "ops-folder"
    assert payload["message"] == "Create production overview"
    assert payload["overwrite"] is False
    assert result["uid"] == "new-dashboard"


@pytest.mark.asyncio
async def test_save_dashboard_syncs_live_metadata_and_preserves_folder(
    session_connection,
):
    """Existing dashboards should reuse live id/version and stay in their folder."""
    requests: list[tuple[str, str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        requests.append((request.method, str(request.url), body))

        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "dashboard": {
                        "id": 17,
                        "uid": "existing-dashboard",
                        "version": 9,
                    },
                    "meta": {
                        "folderId": 4,
                        "folderUid": "observability",
                    },
                },
            )

        return httpx.Response(
            200,
            json={
                "id": 17,
                "uid": "existing-dashboard",
                "url": "/d/existing-dashboard/production-overview",
                "status": "success",
                "version": 10,
            },
        )

    connector = create_mock_connector(session_connection, handler)
    result = await connector.save_dashboard(
        dashboard={
            "uid": "existing-dashboard",
            "version": 1,
            "title": "Production Overview Updated",
            "schemaVersion": 39,
            "panels": [],
        },
        message="Update dashboard",
    )
    await connector.client.aclose()

    assert [request[0] for request in requests] == ["GET", "POST"]

    payload = json.loads(requests[1][2])
    assert payload["dashboard"]["id"] == 17
    assert payload["dashboard"]["uid"] == "existing-dashboard"
    assert payload["dashboard"]["version"] == 9
    assert payload["folderUid"] == "observability"
    assert "folderId" not in payload
    assert payload["message"] == "Update dashboard"
    assert result["version"] == 10


@pytest.mark.asyncio
async def test_save_dashboard_continues_when_uid_is_not_found(session_connection):
    """Missing UIDs should fall back to a normal create request."""
    requests: list[tuple[str, str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        requests.append((request.method, str(request.url), body))

        if request.method == "GET":
            return httpx.Response(404, json={"message": "Dashboard not found"})

        return httpx.Response(
            200,
            json={
                "id": 202,
                "uid": "missing-dashboard",
                "url": "/d/missing-dashboard/new-dashboard",
                "status": "success",
                "version": 1,
            },
        )

    connector = create_mock_connector(session_connection, handler)
    result = await connector.save_dashboard(
        dashboard={
            "uid": "missing-dashboard",
            "title": "Imported Dashboard",
            "schemaVersion": 39,
            "panels": [],
        },
        overwrite=True,
    )
    await connector.client.aclose()

    assert [request[0] for request in requests] == ["GET", "POST"]

    payload = json.loads(requests[1][2])
    assert payload["dashboard"]["uid"] == "missing-dashboard"
    assert "id" not in payload["dashboard"]
    assert "version" not in payload["dashboard"]
    assert "folderUid" not in payload
    assert payload["overwrite"] is True
    assert result["id"] == 202
