"""Tests for HTTP method helpers in GrafanaConnector."""

import httpx
import pytest

from src.config import GrafanaConnection
from src.exceptions import (
    AuthenticationError,
    GrafanaAPIError,
    GrafanaTimeoutError,
    PermissionDeniedError,
)
from src.grafana_connector import GrafanaConnector


@pytest.fixture
def session_connection(monkeypatch):
    """Create a connection using session token auth."""
    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_session_token")
    return GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_session_token",
    )


@pytest.fixture
def api_key_connection(monkeypatch):
    """Create a connection using API key auth."""
    monkeypatch.setenv("GRAFANA_API_KEY_TEST", "test_api_key")
    return GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        api_key="test_api_key",
    )


def create_mock_connector(connection, handler):
    """Create a connector with a mock transport."""
    connector = GrafanaConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        headers={"Authorization": f"Bearer {connection.api_key}"}
        if connection.api_key
        else None,
        cookies={"grafana_session": connection.session_token}
        if connection.session_token
        else None,
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )
    return connector


# =============================================================================
# PUT Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_put_success(session_connection):
    """Test successful PUT request."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"status": "ok", "id": 123})

    connector = create_mock_connector(session_connection, handler)
    result = await connector._put("/test/endpoint", json_payload={"key": "value"})
    await connector.client.aclose()

    assert captured["method"] == "PUT"
    assert "/api/test/endpoint" in captured["url"]
    assert '"key":"value"' in captured["body"]
    assert result == {"status": "ok", "id": 123}


@pytest.mark.asyncio
async def test_put_empty_response(session_connection):
    """Test PUT request with empty response body."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    connector = create_mock_connector(session_connection, handler)
    result = await connector._put("/test/endpoint")
    await connector.client.aclose()

    assert result == {}


@pytest.mark.asyncio
async def test_put_401_raises_authentication_error(session_connection):
    """Test PUT returns AuthenticationError on 401."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(AuthenticationError) as exc_info:
        await connector._put("/test/endpoint")

    await connector.client.aclose()
    assert "test" in str(exc_info.value)


@pytest.mark.asyncio
async def test_put_403_raises_permission_denied_error(session_connection):
    """Test PUT returns PermissionDeniedError on 403."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(PermissionDeniedError) as exc_info:
        await connector._put("/test/endpoint")

    await connector.client.aclose()
    assert "write" in str(exc_info.value)


@pytest.mark.asyncio
async def test_put_500_raises_grafana_api_error(session_connection):
    """Test PUT returns GrafanaAPIError on 500."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(GrafanaAPIError) as exc_info:
        await connector._put("/test/endpoint")

    await connector.client.aclose()
    assert exc_info.value.status_code == 500


# =============================================================================
# DELETE Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_delete_success(session_connection):
    """Test successful DELETE request."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return httpx.Response(200, json={"message": "deleted"})

    connector = create_mock_connector(session_connection, handler)
    result = await connector._delete("/test/resource/123")
    await connector.client.aclose()

    assert captured["method"] == "DELETE"
    assert "/api/test/resource/123" in captured["url"]
    assert result == {"message": "deleted"}


@pytest.mark.asyncio
async def test_delete_empty_response(session_connection):
    """Test DELETE request with empty response body (204 No Content)."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204, content=b"")

    connector = create_mock_connector(session_connection, handler)
    result = await connector._delete("/test/resource/123")
    await connector.client.aclose()

    assert result == {}


@pytest.mark.asyncio
async def test_delete_401_raises_authentication_error(session_connection):
    """Test DELETE returns AuthenticationError on 401."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized"})

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(AuthenticationError):
        await connector._delete("/test/resource/123")

    await connector.client.aclose()


@pytest.mark.asyncio
async def test_delete_403_raises_permission_denied_error(session_connection):
    """Test DELETE returns PermissionDeniedError on 403."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Forbidden"})

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(PermissionDeniedError) as exc_info:
        await connector._delete("/test/resource/123")

    await connector.client.aclose()
    assert "delete" in str(exc_info.value)


@pytest.mark.asyncio
async def test_delete_500_raises_grafana_api_error(session_connection):
    """Test DELETE returns GrafanaAPIError on 500."""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    connector = create_mock_connector(session_connection, handler)

    with pytest.raises(GrafanaAPIError) as exc_info:
        await connector._delete("/test/resource/123")

    await connector.client.aclose()
    assert exc_info.value.status_code == 500


# =============================================================================
# Credential Refresh Tests
# =============================================================================


@pytest.mark.asyncio
async def test_put_with_api_key_auth(api_key_connection):
    """Test PUT request uses API key authentication."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth_header"] = request.headers.get("authorization")
        return httpx.Response(200, json={"status": "ok"})

    connector = create_mock_connector(api_key_connection, handler)
    await connector._put("/test/endpoint")
    await connector.client.aclose()

    assert captured["auth_header"] == "Bearer test_api_key"


@pytest.mark.asyncio
async def test_delete_with_api_key_auth(api_key_connection):
    """Test DELETE request uses API key authentication."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth_header"] = request.headers.get("authorization")
        return httpx.Response(200, json={"status": "ok"})

    connector = create_mock_connector(api_key_connection, handler)
    await connector._delete("/test/resource/123")
    await connector.client.aclose()

    assert captured["auth_header"] == "Bearer test_api_key"


@pytest.mark.asyncio
async def test_put_with_session_cookie_auth(session_connection):
    """Test PUT request uses session cookie authentication."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["cookie_header"] = request.headers.get("cookie")
        return httpx.Response(200, json={"status": "ok"})

    connector = create_mock_connector(session_connection, handler)
    await connector._put("/test/endpoint")
    await connector.client.aclose()

    assert "grafana_session" in captured["cookie_header"]


@pytest.mark.asyncio
async def test_delete_with_session_cookie_auth(session_connection):
    """Test DELETE request uses session cookie authentication."""
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["cookie_header"] = request.headers.get("cookie")
        return httpx.Response(200, json={"status": "ok"})

    connector = create_mock_connector(session_connection, handler)
    await connector._delete("/test/resource/123")
    await connector.client.aclose()

    assert "grafana_session" in captured["cookie_header"]


# =============================================================================
# Helper Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_handle_http_error_401(session_connection):
    """Test _handle_http_error raises AuthenticationError for 401."""
    connector = GrafanaConnector(session_connection)

    mock_response = httpx.Response(401, text="Unauthorized")
    error = httpx.HTTPStatusError(
        "401 Unauthorized", request=httpx.Request("GET", "http://test"), response=mock_response
    )

    with pytest.raises(AuthenticationError):
        connector._handle_http_error(error, "test")

    await connector.close()


@pytest.mark.asyncio
async def test_handle_http_error_403(session_connection):
    """Test _handle_http_error raises PermissionDeniedError for 403."""
    connector = GrafanaConnector(session_connection)

    mock_response = httpx.Response(403, text="Forbidden")
    error = httpx.HTTPStatusError(
        "403 Forbidden", request=httpx.Request("GET", "http://test"), response=mock_response
    )

    with pytest.raises(PermissionDeniedError) as exc_info:
        connector._handle_http_error(error, "custom_operation")

    await connector.close()
    assert "custom_operation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_handle_http_error_other(session_connection):
    """Test _handle_http_error raises GrafanaAPIError for other status codes."""
    connector = GrafanaConnector(session_connection)

    mock_response = httpx.Response(503, text="Service Unavailable")
    error = httpx.HTTPStatusError(
        "503 Service Unavailable",
        request=httpx.Request("GET", "http://test"),
        response=mock_response,
    )

    with pytest.raises(GrafanaAPIError) as exc_info:
        connector._handle_http_error(error, "test")

    await connector.close()
    assert exc_info.value.status_code == 503
    assert "Service Unavailable" in exc_info.value.message
