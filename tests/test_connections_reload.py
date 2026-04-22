"""Tests for runtime reloading of Grafana connections.yaml."""

import asyncio
import json
import logging
from pathlib import Path

import pytest
import yaml
from mcp.server.fastmcp.exceptions import ToolError

import mcp_read_only_grafana.server as server_module
from mcp_read_only_grafana.runtime_paths import RuntimePaths
from mcp_read_only_grafana.server import ReadOnlyGrafanaServer


class ReloadTestConnector:
    """Connector stub that exposes the loaded config through tool responses."""

    def __init__(self, connection):
        self.connection = connection
        self.closed = False

    async def close(self):
        self.closed = True

    async def get_health(self):
        return {
            "name": self.connection.connection_name,
            "url": str(self.connection.url),
            "description": self.connection.description,
            "timeout": self.connection.timeout,
            "verify_ssl": self.connection.verify_ssl,
            "api_key": self.connection.api_key,
        }

    async def get_current_org(self):
        return {"org": self.connection.connection_name}


class FailingReloadTestConnector(ReloadTestConnector):
    """Connector stub that can fail connector construction for selected names."""

    def __init__(self, connection):
        if connection.connection_name == "boom":
            raise RuntimeError("boom during connector construction")
        super().__init__(connection)


def make_runtime_paths(tmp_path: Path) -> RuntimePaths:
    """Create isolated runtime paths for reload tests."""
    runtime_paths = RuntimePaths(
        config_dir=tmp_path / "config",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    runtime_paths.ensure_directories()
    return runtime_paths


def write_connections_file(path: Path, connections: list[dict[str, object]]) -> None:
    """Write a YAML connections file for a reload scenario."""
    path.write_text(
        yaml.safe_dump(connections, sort_keys=False),
        encoding="utf-8",
    )


async def call_tool(
    server: ReadOnlyGrafanaServer,
    tool_name: str,
    arguments: dict[str, object] | None = None,
):
    """Call a FastMCP tool directly on the in-process server."""
    return await server.mcp._tool_manager.call_tool(
        tool_name,
        arguments or {},
        convert_result=False,
    )


async def list_connections(server: ReadOnlyGrafanaServer) -> list[dict[str, object]]:
    """Call list_connections and parse the JSON result."""
    result = await call_tool(server, "list_connections")
    assert isinstance(result, str)
    return json.loads(result)


def count_load_config_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Wrap config loading so tests can assert whether reloads happened."""
    real_load_config = server_module.ConfigParser.load_config_from_text
    call_counter = {"count": 0}

    def wrapped_load_config(self, yaml_text: str):
        call_counter["count"] += 1
        return real_load_config(self, yaml_text)

    monkeypatch.setattr(
        server_module.ConfigParser,
        "load_config_from_text",
        wrapped_load_config,
    )
    return call_counter


@pytest.mark.asyncio
async def test_tools_reload_connections_after_config_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "GrafanaConnector", ReloadTestConnector)
    runtime_paths = make_runtime_paths(tmp_path)
    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha",
                "api_key": "alpha-key",
            },
            {
                "connection_name": "beta",
                "url": "https://beta.example.com",
                "description": "Beta",
                "timeout": 45,
                "api_key": "beta-key",
            },
        ],
    )
    server = ReadOnlyGrafanaServer(runtime_paths)

    initial_connections = await list_connections(server)
    assert [row["name"] for row in initial_connections] == ["alpha", "beta"]

    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "beta",
                "url": "https://beta-v2.example.com",
                "description": "Beta Reloaded",
                "timeout": 60,
                "verify_ssl": False,
                "api_key": "beta-key-v2",
            },
            {
                "connection_name": "gamma",
                "url": "https://gamma.example.com",
                "description": "Gamma",
                "api_key": "gamma-key",
            },
        ],
    )

    reloaded_connections = await list_connections(server)
    assert [row["name"] for row in reloaded_connections] == ["beta", "gamma"]
    reloaded_map = {row["name"]: row for row in reloaded_connections}
    assert reloaded_map["beta"]["url"] == "https://beta-v2.example.com"
    assert reloaded_map["beta"]["timeout"] == 60
    assert reloaded_map["beta"]["verify_ssl"] is False

    with pytest.raises(ToolError, match="Connection 'alpha' not found"):
        await call_tool(server, "get_health", {"connection_name": "alpha"})

    beta_health = await call_tool(server, "get_health", {"connection_name": "beta"})
    assert json.loads(beta_health) == {
        "name": "beta",
        "url": "https://beta-v2.example.com",
        "description": "Beta Reloaded",
        "timeout": 60,
        "verify_ssl": False,
        "api_key": "beta-key-v2",
    }

    await server.cleanup()


@pytest.mark.asyncio
async def test_reload_skips_unchanged_config(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "GrafanaConnector", ReloadTestConnector)
    load_calls = count_load_config_calls(monkeypatch)
    runtime_paths = make_runtime_paths(tmp_path)
    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha",
                "api_key": "alpha-key",
            }
        ],
    )
    server = ReadOnlyGrafanaServer(runtime_paths)

    assert load_calls["count"] == 1

    await list_connections(server)
    await list_connections(server)
    await call_tool(server, "get_health", {"connection_name": "alpha"})

    assert load_calls["count"] == 1

    await server.cleanup()


@pytest.mark.asyncio
async def test_invalid_reload_keeps_last_good_connections_until_file_changes(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(server_module, "GrafanaConnector", ReloadTestConnector)
    runtime_paths = make_runtime_paths(tmp_path)
    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha",
                "api_key": "alpha-key",
            }
        ],
    )
    server = ReadOnlyGrafanaServer(runtime_paths)
    caplog.set_level(logging.WARNING)

    runtime_paths.connections_file.write_text(
        "- connection_name: broken\n  url: https://broken.example.com\n",
        encoding="utf-8",
    )

    preserved_connections = await list_connections(server)
    assert [row["name"] for row in preserved_connections] == ["alpha"]

    alpha_health = await call_tool(server, "get_health", {"connection_name": "alpha"})
    assert json.loads(alpha_health)["url"] == "https://alpha.example.com"
    assert "keeping 1 previously loaded connection(s)" in caplog.text

    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "beta",
                "url": "https://beta.example.com",
                "description": "Beta",
                "api_key": "beta-key",
            }
        ],
    )

    recovered_connections = await list_connections(server)
    assert [row["name"] for row in recovered_connections] == ["beta"]

    beta_health = await call_tool(server, "get_health", {"connection_name": "beta"})
    assert json.loads(beta_health)["url"] == "https://beta.example.com"

    await server.cleanup()


@pytest.mark.asyncio
async def test_failed_reload_does_not_partially_mutate_reused_connectors(
    tmp_path, monkeypatch, caplog
):
    monkeypatch.setattr(server_module, "GrafanaConnector", FailingReloadTestConnector)
    runtime_paths = make_runtime_paths(tmp_path)
    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha",
                "api_key": "alpha-key",
            }
        ],
    )
    server = ReadOnlyGrafanaServer(runtime_paths)
    caplog.set_level(logging.WARNING)

    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha Reloaded",
                "api_key": "alpha-key-reloaded",
            },
            {
                "connection_name": "boom",
                "url": "https://boom.example.com",
                "description": "Boom",
                "api_key": "boom-key",
            },
        ],
    )

    preserved_connections = await list_connections(server)
    assert preserved_connections == [
        {
            "name": "alpha",
            "url": "https://alpha.example.com",
            "description": "Alpha",
            "timeout": 30,
            "verify_ssl": True,
        }
    ]

    alpha_health = await call_tool(server, "get_health", {"connection_name": "alpha"})
    assert json.loads(alpha_health) == {
        "name": "alpha",
        "url": "https://alpha.example.com",
        "description": "Alpha",
        "timeout": 30,
        "verify_ssl": True,
        "api_key": "alpha-key",
    }
    assert "keeping 1 previously loaded connection(s)" in caplog.text

    await server.cleanup()


@pytest.mark.asyncio
async def test_second_reload_closes_previous_retired_connectors(tmp_path, monkeypatch):
    monkeypatch.setattr(server_module, "GrafanaConnector", ReloadTestConnector)
    runtime_paths = make_runtime_paths(tmp_path)
    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "alpha",
                "url": "https://alpha.example.com",
                "description": "Alpha",
                "api_key": "alpha-key",
            }
        ],
    )
    server = ReadOnlyGrafanaServer(runtime_paths)
    alpha_connector = server._connectors["alpha"]

    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "beta",
                "url": "https://beta.example.com",
                "description": "Beta",
                "api_key": "beta-key",
            }
        ],
    )
    await list_connections(server)
    assert alpha_connector.closed is False

    write_connections_file(
        runtime_paths.connections_file,
        [
            {
                "connection_name": "gamma",
                "url": "https://gamma.example.com",
                "description": "Gamma",
                "api_key": "gamma-key",
            }
        ],
    )
    await list_connections(server)
    await asyncio.sleep(0)

    assert alpha_connector.closed is True

    await server.cleanup()
