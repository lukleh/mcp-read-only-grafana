"""Tests for the Grafana Explore /api/ds/query integration"""

import json

import httpx
import pytest

from src.config import GrafanaConnection
from src.grafana_connector import GrafanaConnector


@pytest.mark.asyncio
async def test_explore_query_builds_payload(monkeypatch):
    """Verify payload construction and POST execution for Explore queries"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    captured: dict[str, dict] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"results": {"A": {}}})

    connector = GrafanaConnector(connection)
    connector.client = httpx.AsyncClient(
        base_url=str(connection.url),
        cookies={"grafana_session": connection.session_token or ""},
        timeout=connection.timeout,
        verify=connection.verify_ssl,
        follow_redirects=True,
        transport=httpx.MockTransport(handler),
    )

    result = await connector.explore_query(
        queries=[
            {
                "refId": "A",
                "datasource": {"uid": "prometheus_uid", "type": "prometheus"},
                "expr": "rate(http_requests_total[5m])",
            }
        ],
        range_from="now-1h",
        range_to="now",
        max_data_points=500,
        interval_ms=1000,
        additional_options={"requestId": "1", "timezone": "utc"},
    )

    await connector.client.aclose()

    assert result == {"results": {"A": {}}}
    assert captured["json"]["from"] == "now-1h"
    assert captured["json"]["to"] == "now"
    assert captured["json"]["maxDataPoints"] == 500
    assert captured["json"]["intervalMs"] == 1000
    assert captured["json"]["requestId"] == "1"
    assert captured["json"]["timezone"] == "utc"
    query_payload = captured["json"]["queries"][0]
    assert query_payload["refId"] == "A"
    assert query_payload["expr"] == "rate(http_requests_total[5m])"


@pytest.mark.asyncio
async def test_explore_query_rejects_conflicting_option(monkeypatch):
    """Ensure conflicting additional options raise a ValueError"""

    monkeypatch.setenv("GRAFANA_SESSION_TEST", "test_token")

    connection = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="test_token",
    )

    connector = GrafanaConnector(connection)

    with pytest.raises(ValueError):
        await connector.explore_query(
            queries=[{"refId": "A", "datasource": {"uid": "x", "type": "prometheus"}}],
            additional_options={"queries": []},
        )

    await connector.client.aclose()
