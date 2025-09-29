"""Tests for cookie refresh logic"""

import httpx
from src.grafana_connector import GrafanaConnector
from src.config import GrafanaConnection


def test_parse_set_cookie_header():
    """Test parsing Set-Cookie header for grafana_session"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="old_token_123"
    )
    connector = GrafanaConnector(conn)

    # Simulate response with Set-Cookie header
    mock_response = httpx.Response(
        status_code=200,
        headers={
            "set-cookie": "grafana_session=new_token_456; Path=/; HttpOnly; SameSite=Lax"
        },
        content=b'{"status": "ok"}'
    )

    # Call the method
    connector._check_and_update_session_cookie(mock_response)

    # Verify token was updated in memory
    assert connector.connection.session_token == "new_token_456"


def test_parse_url_encoded_cookie():
    """Test parsing URL-encoded Set-Cookie header"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="old_token"
    )
    connector = GrafanaConnector(conn)

    # URL-encoded cookie value
    mock_response = httpx.Response(
        status_code=200,
        headers={
            "set-cookie": "grafana_session=abc%2B123%3Dtest; Path=/"
        },
        content=b'{"status": "ok"}'
    )

    connector._check_and_update_session_cookie(mock_response)

    # Should be URL-decoded
    assert connector.connection.session_token == "abc+123=test"


def test_no_set_cookie_header():
    """Test that missing Set-Cookie header doesn't change token"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="original_token"
    )
    connector = GrafanaConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={},
        content=b'{"status": "ok"}'
    )

    connector._check_and_update_session_cookie(mock_response)

    # Token should remain unchanged
    assert connector.connection.session_token == "original_token"


def test_same_token_not_updated():
    """Test that same token doesn't trigger update"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="same_token_123"
    )
    connector = GrafanaConnector(conn)

    mock_response = httpx.Response(
        status_code=200,
        headers={
            "set-cookie": "grafana_session=same_token_123; Path=/"
        },
        content=b'{"status": "ok"}'
    )

    connector._check_and_update_session_cookie(mock_response)

    # Token should still be the same (no unnecessary writes)
    assert connector.connection.session_token == "same_token_123"


def test_multiple_set_cookie_headers():
    """Test handling multiple Set-Cookie headers (only grafana_session matters)"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="old_token"
    )
    connector = GrafanaConnector(conn)

    # Multiple cookies in response
    mock_response = httpx.Response(
        status_code=200,
        headers=httpx.Headers([
            ("set-cookie", "other_cookie=value1; Path=/"),
            ("set-cookie", "grafana_session=new_token_789; Path=/"),
            ("set-cookie", "grafana_session_expiry=1234567890; Path=/")
        ]),
        content=b'{"status": "ok"}'
    )

    connector._check_and_update_session_cookie(mock_response)

    # Should extract the grafana_session cookie
    assert connector.connection.session_token == "new_token_789"