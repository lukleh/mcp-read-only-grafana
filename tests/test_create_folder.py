"""Tests for Grafana create folder endpoint"""

import httpx
import pytest

from mcp_read_only_grafana.config import GrafanaConnection
from mcp_read_only_grafana.grafana_connector import GrafanaConnector


@pytest.mark.asyncio
async def test_create_folder_basic(monkeypatch):
    """Ensure create folder endpoint is wired correctly with just title"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    captured: dict[str, any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": 123,
                "uid": "generated-uid",
                "title": "My Folder",
                "url": "/dashboards/f/generated-uid/my-folder",
                "hasAcl": False,
                "canSave": True,
                "canEdit": True,
                "canAdmin": True,
                "createdBy": "admin",
                "created": "2024-01-01T00:00:00Z",
                "updatedBy": "admin",
                "updated": "2024-01-01T00:00:00Z",
                "version": 1,
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

    folder = await connector.create_folder("My Folder")

    await connector.client.aclose()

    assert folder["uid"] == "generated-uid"
    assert folder["title"] == "My Folder"
    assert captured["method"] == "POST"
    assert "/api/folders" in captured["url"]
    assert '"title":"My Folder"' in captured["body"]


@pytest.mark.asyncio
async def test_create_folder_with_uid(monkeypatch):
    """Ensure create folder passes custom uid"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    captured: dict[str, any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": 123,
                "uid": "custom-uid",
                "title": "My Folder",
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

    folder = await connector.create_folder("My Folder", uid="custom-uid")

    await connector.client.aclose()

    assert folder["uid"] == "custom-uid"
    assert '"uid":"custom-uid"' in captured["body"]


@pytest.mark.asyncio
async def test_create_folder_with_parent(monkeypatch):
    """Ensure create folder passes parent_uid for nested folders"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    captured: dict[str, any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        return httpx.Response(
            200,
            json={
                "id": 124,
                "uid": "child-folder",
                "title": "Child Folder",
                "parentUid": "parent-folder",
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

    folder = await connector.create_folder(
        "Child Folder", uid="child-folder", parent_uid="parent-folder"
    )

    await connector.client.aclose()

    assert folder["uid"] == "child-folder"
    assert '"parentUid":"parent-folder"' in captured["body"]
