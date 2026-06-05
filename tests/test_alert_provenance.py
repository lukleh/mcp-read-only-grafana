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


@pytest.mark.parametrize(
    ("invoke", "method", "path"),
    [
        pytest.param(
            lambda connector: connector.create_alert_rule({"title": "Example rule"}),
            "POST",
            "/api/v1/provisioning/alert-rules",
            id="create-alert-rule",
        ),
        pytest.param(
            lambda connector: connector.update_alert_rule(
                "rule-uid", {"title": "Example rule"}
            ),
            "PUT",
            "/api/v1/provisioning/alert-rules/rule-uid",
            id="update-alert-rule",
        ),
        pytest.param(
            lambda connector: connector.delete_alert_rule("rule-uid"),
            "DELETE",
            "/api/v1/provisioning/alert-rules/rule-uid",
            id="delete-alert-rule",
        ),
        pytest.param(
            lambda connector: connector.update_rule_group_interval(
                "folder-uid", "group-name", {"interval": "1m", "rules": []}
            ),
            "PUT",
            "/api/v1/provisioning/folder/folder-uid/rule-groups/group-name",
            id="update-rule-group",
        ),
        pytest.param(
            lambda connector: connector.create_contact_point(
                {"name": "cp", "type": "slack", "settings": {}}
            ),
            "POST",
            "/api/v1/provisioning/contact-points",
            id="create-contact-point",
        ),
        pytest.param(
            lambda connector: connector.update_contact_point(
                "contact-uid", {"name": "cp", "type": "slack", "settings": {}}
            ),
            "PUT",
            "/api/v1/provisioning/contact-points/contact-uid",
            id="update-contact-point",
        ),
        pytest.param(
            lambda connector: connector.delete_contact_point("contact-uid"),
            "DELETE",
            "/api/v1/provisioning/contact-points/contact-uid",
            id="delete-contact-point",
        ),
        pytest.param(
            lambda connector: connector.set_notification_policies(
                {"receiver": "default", "routes": []}
            ),
            "PUT",
            "/api/v1/provisioning/policies",
            id="set-notification-policies",
        ),
        pytest.param(
            lambda connector: connector.delete_notification_policies(),
            "DELETE",
            "/api/v1/provisioning/policies",
            id="delete-notification-policies",
        ),
        pytest.param(
            lambda connector: connector.set_notification_template(
                "template-name", {"template": '{{ define "x" }}ok{{ end }}'}
            ),
            "PUT",
            "/api/v1/provisioning/templates/template-name",
            id="set-notification-template",
        ),
        pytest.param(
            lambda connector: connector.delete_notification_template("template-name"),
            "DELETE",
            "/api/v1/provisioning/templates/template-name",
            id="delete-notification-template",
        ),
        pytest.param(
            lambda connector: connector.create_mute_timing(
                {"name": "mute", "time_intervals": []}
            ),
            "POST",
            "/api/v1/provisioning/mute-timings",
            id="create-mute-timing",
        ),
        pytest.param(
            lambda connector: connector.update_mute_timing(
                "mute-name", {"name": "mute-name", "time_intervals": []}
            ),
            "PUT",
            "/api/v1/provisioning/mute-timings/mute-name",
            id="update-mute-timing",
        ),
        pytest.param(
            lambda connector: connector.delete_mute_timing("mute-name"),
            "DELETE",
            "/api/v1/provisioning/mute-timings/mute-name",
            id="delete-mute-timing",
        ),
    ],
)
@pytest.mark.asyncio
async def test_alerting_provisioning_writes_disable_provenance_by_default(
    api_key_connection,
    invoke,
    method,
    path,
):
    """Provisioning writes should keep Grafana resources editable by default."""
    captured: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["header"] = request.headers.get("x-disable-provenance")
        return httpx.Response(200, json={"ok": True})

    connector = create_connector(api_key_connection, handler)
    await invoke(connector)
    await connector.client.aclose()

    assert captured == {
        "method": method,
        "path": path,
        "header": "true",
    }


@pytest.mark.asyncio
async def test_non_provisioning_write_does_not_disable_provenance(
    api_key_connection,
):
    """Non-provisioning writes should not receive Grafana's provisioning header."""
    captured: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["header"] = request.headers.get("x-disable-provenance")
        return httpx.Response(200, json={"id": 1})

    connector = create_connector(api_key_connection, handler)
    await connector._post("/folders", json_payload={"title": "Folder"})
    await connector.client.aclose()

    assert captured == {
        "path": "/api/folders",
        "header": None,
    }


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
    assert (
        "/api/v1/provisioning/folder/folder-uid/rule-groups/group-name"
        in captured["url"]
    )
    assert captured["header"] is None


@pytest.mark.asyncio
async def test_notification_template_can_opt_out_of_disable_provenance(
    api_key_connection,
):
    """Non-rule provisioning writes should support explicit provisioned behavior."""
    captured: dict[str, str | None] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["header"] = request.headers.get("x-disable-provenance")
        return httpx.Response(200, json={"name": "template-name"})

    connector = create_connector(api_key_connection, handler)
    result = await connector.set_notification_template(
        "template-name",
        {"template": '{{ define "x" }}ok{{ end }}'},
        disable_provenance=False,
    )
    await connector.client.aclose()

    assert result["name"] == "template-name"
    assert "/api/v1/provisioning/templates/template-name" in captured["url"]
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


class FakeTemplateConnector:
    """Minimal admin connector stub for template tool wiring tests."""

    def __init__(self):
        self.calls: list[dict[str, object]] = []

    async def set_notification_template(
        self,
        name: str,
        template: dict[str, object],
        disable_provenance: bool = True,
    ) -> dict[str, object]:
        self.calls.append(
            {
                "name": name,
                "template": template,
                "disable_provenance": disable_provenance,
            }
        )
        return {"name": name}


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
async def test_notification_template_tool_can_opt_out_of_editable_in_ui():
    """The MCP tool should let callers keep Grafana's provisioned behavior."""
    connector = FakeTemplateConnector()
    mcp = FastMCP("test-admin-tools")
    register_admin_tools(mcp, {"test": connector})

    result = await mcp._tool_manager.call_tool(
        "set_notification_template",
        {
            "connection_name": "test",
            "name": "template-name",
            "template": {"template": '{{ define "x" }}ok{{ end }}'},
            "editable_in_ui": False,
        },
        convert_result=False,
    )

    assert json.loads(result) == {"name": "template-name"}
    assert connector.calls == [
        {
            "name": "template-name",
            "template": {"template": '{{ define "x" }}ok{{ end }}'},
            "disable_provenance": False,
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
