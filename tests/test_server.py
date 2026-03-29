"""Tests for MCP Read-Only Grafana server bootstrap behavior."""

from importlib.metadata import version
from pathlib import Path

import pytest


def test_package_version_matches_distribution_metadata():
    """The module should expose the installed distribution version."""
    from mcp_read_only_grafana import __version__

    assert __version__ == version("mcp-read-only-grafana")


def test_write_sample_config_creates_runtime_dirs_and_file(tmp_path, monkeypatch):
    """Sample config bootstrap should create package runtime directories."""
    from mcp_read_only_grafana.runtime_paths import resolve_runtime_paths
    from mcp_read_only_grafana.server import (
        SAMPLE_CONNECTIONS_YAML,
        write_sample_config,
    )

    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_CACHE_DIR", str(cache_dir))

    runtime_paths = resolve_runtime_paths()
    written_path = write_sample_config(runtime_paths)

    assert written_path == runtime_paths.connections_file
    assert runtime_paths.config_dir.is_dir()
    assert runtime_paths.state_dir.is_dir()
    assert runtime_paths.cache_dir.is_dir()
    assert written_path.read_text(encoding="utf-8") == SAMPLE_CONNECTIONS_YAML


def test_sample_config_matches_example_file():
    """The embedded sample config should stay in sync with connections.yaml.sample."""
    from mcp_read_only_grafana.server import SAMPLE_CONNECTIONS_YAML

    example_path = Path(__file__).resolve().parents[1] / "connections.yaml.sample"

    assert SAMPLE_CONNECTIONS_YAML == example_path.read_text(encoding="utf-8")


def test_write_sample_config_requires_overwrite_to_replace(tmp_path):
    """Existing config files should be preserved unless overwrite is requested."""
    from mcp_read_only_grafana.runtime_paths import RuntimePaths
    from mcp_read_only_grafana.server import write_sample_config

    runtime_paths = RuntimePaths(
        config_dir=tmp_path / "config",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    runtime_paths.ensure_directories()
    runtime_paths.connections_file.write_text(
        "- connection_name: existing\n", encoding="utf-8"
    )

    with pytest.raises(FileExistsError, match="already exists"):
        write_sample_config(runtime_paths)


def test_write_sample_config_overwrite_replaces_existing_file(tmp_path):
    """Overwrite mode should replace an existing file with the sample config."""
    from mcp_read_only_grafana.runtime_paths import RuntimePaths
    from mcp_read_only_grafana.server import (
        SAMPLE_CONNECTIONS_YAML,
        write_sample_config,
    )

    runtime_paths = RuntimePaths(
        config_dir=tmp_path / "config",
        state_dir=tmp_path / "state",
        cache_dir=tmp_path / "cache",
    )
    runtime_paths.ensure_directories()
    runtime_paths.connections_file.write_text(
        "- connection_name: existing\n", encoding="utf-8"
    )

    write_sample_config(runtime_paths, overwrite=True)

    assert (
        runtime_paths.connections_file.read_text(encoding="utf-8")
        == SAMPLE_CONNECTIONS_YAML
    )


def test_main_write_sample_config_and_print_paths_together(
    monkeypatch, tmp_path, capsys
):
    """The CLI should support bootstrapping config and printing paths in one run."""
    import sys

    from mcp_read_only_grafana import server

    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp-read-only-grafana",
            "--config-dir",
            str(config_dir),
            "--state-dir",
            str(state_dir),
            "--cache-dir",
            str(cache_dir),
            "--write-sample-config",
            "--print-paths",
        ],
    )
    monkeypatch.setattr(
        server.ReadOnlyGrafanaServer,
        "__init__",
        lambda *args, **kwargs: pytest.fail(
            "ReadOnlyGrafanaServer should not be constructed when only printing setup info"
        ),
    )

    server.main()

    output = capsys.readouterr().out

    assert f"Wrote sample config to {config_dir / 'connections.yaml'}" in output
    assert f"config_dir={config_dir}" in output
    assert f"state_dir={state_dir}" in output
    assert f"cache_dir={cache_dir}" in output
    assert f"connections_file={config_dir / 'connections.yaml'}" in output


def test_main_rejects_overwrite_without_write_sample_config(monkeypatch):
    """Overwrite should only be accepted together with sample-config bootstrap."""
    import sys

    from mcp_read_only_grafana import server

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp-read-only-grafana",
            "--overwrite",
        ],
    )

    with pytest.raises(SystemExit):
        server.main()


def test_main_passes_allow_admin_to_server(monkeypatch, tmp_path):
    """The CLI should pass through the admin-mode flag when constructing the server."""
    import sys

    from mcp_read_only_grafana import server

    captured: dict[str, object] = {}

    def fake_init(self, runtime_paths, allow_admin=False):
        captured["runtime_paths"] = runtime_paths
        captured["allow_admin"] = allow_admin

    async def fake_cleanup(self):
        return None

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp-read-only-grafana",
            "--config-dir",
            str(tmp_path / "config"),
            "--state-dir",
            str(tmp_path / "state"),
            "--cache-dir",
            str(tmp_path / "cache"),
            "--allow-admin",
        ],
    )
    monkeypatch.setattr(server.ReadOnlyGrafanaServer, "__init__", fake_init)
    monkeypatch.setattr(server.ReadOnlyGrafanaServer, "run", lambda self: None)
    monkeypatch.setattr(server.ReadOnlyGrafanaServer, "cleanup", fake_cleanup)

    server.main()

    assert captured["allow_admin"] is True
