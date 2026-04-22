"""Tests for Grafana alert provisioning provenance controls."""

import json

import httpx
import pytest
from mcp.server.fastmcp import FastMCP

from mcp_read_only_grafana.config import GrafanaConnection
from mcp_read_only_grafana.grafana_connector import GrafanaConnector
from mcp_read_only_grafana.tools.admin_tools import register_admin_tools


def create_connector(connection: GrafanaConnection, handler) -> GrafanaConnector:
    """Create a connector backed by a mock HTTP transport."""
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
def api_key_connection(monkeypatch):
    """Create an API-key-authenticated Grafana connection."""
    monkeypatch.setenv("GRAFANA_API_KEY_TEST", "test_api_key")
    return GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        api_key="test_api_key",
    )


@pytest.mark.asyncio
async def test_create_alert_rule_sends_disable_provenance_header_by_default(
    api_key_connection,
):
    """Alert creation should default to the editable-provenance header."""
    captured: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["header"] = request.headers.get("x-disable-provenance")
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(201, json={"uid": "rule-1"})

    connector = create_connector(api_key_connection, handler)
    result = await connector.create_alert_rule({"title": "Example rule"})
    await connector.client.aclose()

    assert result["uid"] == "rule-1"
    assert "/api/v1/provisioning/alert-rules" in captured["url"]
    assert captured["header"] == "true"
    assert captured["auth"] == "Bearer test_api_key"


@pytest.mark.asyncio
async def test_update_rule_group_can_opt_out_of_disable_provenance(
    api_key_connection,
):
    """Rule-group updates should skip the header only when explicitly disabled."""
    captured: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["header"] = request.headers.get("x-disable-provenance")
        return httpx.Response(200, json={"name": "group"})

    connector = create_connector(api_key_connection, handler)
    result = await connector.update_rule_group_interval(
        "folder-uid",
        "group-name",
        {"interval": "1m", "rules": []},
        disable_provenance=False,
    )
    await connector.client.aclose()

    assert result["name"] == "group"
    assert "/api/v1/provisioning/folder/folder-uid/rule-groups/group-name" in captured["url"]
    assert captured["header"] is None


class FakeAlertConnector:
    """Minimal admin connector stub for tool wiring tests."""

    def __init__(self):
        self.calls: list[dict[str, object]] = []

    async def create_alert_rule(
        self,
        rule: dict[str, object],
        disable_provenance: bool = True,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "rule": rule,
                "disable_provenance": disable_provenance,
            }
        )
        return {"uid": "rule-1"}


@pytest.mark.asyncio
async def test_create_alert_rule_tool_defaults_editable_in_ui_to_true():
    """The MCP tool should default to alerts staying editable in the UI."""
    connector = FakeAlertConnector()
    mcp = FastMCP("test-admin-tools")
    register_admin_tools(mcp, {"test": connector})

    result = await mcp._tool_manager.call_tool(
        "create_alert_rule",
        {
            "connection_name": "test",
            "rule": {"title": "Example rule"},
        },
        convert_result=False,
    )

    assert json.loads(result) == {"uid": "rule-1"}
    assert connector.calls == [
        {
            "rule": {"title": "Example rule"},
            "disable_provenance": True,
        }
    ]


@pytest.mark.asyncio
async def test_create_alert_rule_tool_can_opt_out_of_editable_in_ui():
    """The MCP tool should let callers keep Grafana's provisioned behavior."""
    connector = FakeAlertConnector()
    mcp = FastMCP("test-admin-tools")
    register_admin_tools(mcp, {"test": connector})

    result = await mcp._tool_manager.call_tool(
        "create_alert_rule",
        {
            "connection_name": "test",
            "rule": {"title": "Example rule"},
            "editable_in_ui": False,
        },
        convert_result=False,
    )

    assert json.loads(result) == {"uid": "rule-1"}
    assert connector.calls == [
        {
            "rule": {"title": "Example rule"},
            "disable_provenance": False,
        }
    ]
