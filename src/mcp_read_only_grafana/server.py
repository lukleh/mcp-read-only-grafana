#!/usr/bin/env python3
"""CLI bootstrap for the Grafana MCP server package."""

import argparse
import asyncio
import logging
import os
import sys
from collections.abc import Callable, Iterator, Mapping
from importlib.resources import files
from pathlib import Path
from textwrap import dedent
from typing import TypeVar

from mcp.server.fastmcp import FastMCP

from .config import ConfigParser, GrafanaConnection
from .grafana_connector import GrafanaConnector
from .runtime_paths import resolve_runtime_paths, RuntimePaths
from .tools import (
    register_admin_tools,
    register_alert_tools,
    register_core_tools,
    register_dashboard_tools,
    register_datasource_tools,
    register_user_tools,
)
from .tools import test_connection as test_connection_command
from .tools import validate_config as validate_config_command

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)
READ_ONLY_COMMAND = "mcp-read-only-grafana"
WRITE_COMMAND = "mcp-grafana-write"
SAMPLE_CONNECTIONS_SCHEMA_JSON = (
    files("mcp_read_only_grafana")
    .joinpath("connections.schema.json")
    .read_text(encoding="utf-8")
)
SAMPLE_CONNECTIONS_YAML = dedent("""
    # yaml-language-server: $schema=./connections.schema.json
    # MCP Read-Only Grafana Server - Connection Configuration Sample
    # Edit this file to configure your Grafana connections.
    # Live runtime location for the installed package:
    #   ~/.config/lukleh/mcp-read-only-grafana/connections.yaml
    # This checked-in sample file is only documentation/source material.
    # Use --write-sample-config to write it into the runtime config directory.
    # Prefer `api_key` for normal use.
    # `session_token` is deprecated and should only be used as a temporary fallback.

    # Basic Grafana connection
    - connection_name: production_grafana
      url: https://grafana.example.com
      description: Production Grafana instance
      # Preferred: store a static API key or service-account token directly in YAML
      # api_key: glsa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      # Deprecated fallback: store a session cookie only for short-lived local use
      # session_token: your_grafana_session_cookie
      # Optional: override default timeout (30 seconds)
      # timeout: 60

    # Another Grafana instance
    - connection_name: staging_grafana
      url: https://staging-grafana.example.com
      description: Staging environment Grafana
      # Optional settings:
      # timeout: 30
      # verify_ssl: true  # Set to false for self-signed certificates (not recommended)

    # Grafana Cloud instance
    - connection_name: grafana_cloud
      url: https://myorg.grafana.net
      description: Grafana Cloud instance

    # Local development Grafana
    - connection_name: local_grafana
      url: http://localhost:3000
      description: Local development Grafana
      # For local instances, you might want to disable SSL verification
      verify_ssl: false

    # Notes:
    # - Credentials can be stored directly in this file via:
    #     - api_key: Grafana API key / service-account token (preferred)
    #     - session_token: Grafana session cookie (deprecated fallback)
    # - You can still override credentials from the runtime environment:
    #     - API key (Bearer): GRAFANA_API_KEY_<CONNECTION_NAME>
    #     - Session cookie: GRAFANA_SESSION_<CONNECTION_NAME> (deprecated fallback)
    # - Precedence is:
    #     1. session_tokens.json (rotated session cookies)
    #     2. runtime environment variables
    #     3. connections.yaml credentials
    # - If both session and API key are available for a connection, API key takes precedence.
    # - Connection names should use only letters, numbers, underscores, and hyphens
    # - URLs should not include trailing slashes
    # - Session cookies rotate and expire quickly; prefer API keys for stable MCP access
    # - Credentials are reloaded before each request to support env overrides and token rotation
    """).lstrip()
SUBCOMMAND_HANDLERS: dict[str, Callable[[], None]] = {
    "test-connection": test_connection_command.main,
    "validate-config": validate_config_command.main,
}
ConfigMarker = tuple[int, int] | None
T = TypeVar("T")


class ReloadableMapping(Mapping[str, T]):
    """Mapping proxy that refreshes connection state before reads."""

    def __init__(
        self,
        refresh: Callable[[], None],
        backing_map: Callable[[], Mapping[str, T]],
    ):
        self._refresh = refresh
        self._backing_map = backing_map

    def _current(self) -> Mapping[str, T]:
        self._refresh()
        return self._backing_map()

    def __getitem__(self, key: str) -> T:
        return self._current()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._current())

    def __len__(self) -> int:
        return len(self._current())

    def __contains__(self, key: object) -> bool:
        return key in self._current()

    def items(self):
        return self._current().items()

    def keys(self):
        return self._current().keys()

    def values(self):
        return self._current().values()


class ReadOnlyGrafanaServer:
    """MCP Read-Only Grafana Server using FastMCP."""

    def __init__(
        self,
        runtime_paths: RuntimePaths,
        allow_writes: bool = False,
        server_name: str = READ_ONLY_COMMAND,
    ):
        self.runtime_paths = runtime_paths
        self.allow_writes = allow_writes
        self.server_name = server_name
        self._connections: dict[str, GrafanaConnection] = {}
        self._connectors: dict[str, GrafanaConnector] = {}
        self._connections_config_marker: ConfigMarker = None
        self._retired_connectors: list[GrafanaConnector] = []
        self.connections: Mapping[str, GrafanaConnection] = ReloadableMapping(
            self._reload_connections_if_needed,
            lambda: self._connections,
        )
        self.connectors: Mapping[str, GrafanaConnector] = ReloadableMapping(
            self._reload_connections_if_needed,
            lambda: self._connectors,
        )

        self.mcp = FastMCP(server_name)

        self._load_connections()
        self._register_tools()

    def _load_connections(self) -> None:
        try:
            connections, connectors, marker = self._build_connections()
        except FileNotFoundError:
            logger.warning(
                "Configuration file not found: %s",
                self.runtime_paths.connections_file,
            )
            logger.info("Expected Grafana config at %s", self.runtime_paths.config_dir)
            return
        except Exception as exc:
            logger.error("Failed to load configuration: %s", exc)
            raise

        self._replace_active_connections(connections, connectors, marker)

    def _read_connections_config_marker(self) -> ConfigMarker:
        """Return a lightweight marker for the current connections.yaml state."""
        try:
            stat_result = self.runtime_paths.connections_file.stat()
        except FileNotFoundError:
            return None
        return (stat_result.st_mtime_ns, stat_result.st_size)

    def _read_connections_config_snapshot(self) -> tuple[str, ConfigMarker]:
        """Read connections.yaml once and return its content with a matching marker."""
        config_path = self.runtime_paths.connections_file.expanduser()
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                yaml_text = handle.read()
                stat_result = os.fstat(handle.fileno())
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Configuration file not found: {self.runtime_paths.connections_file}"
            ) from exc
        return yaml_text, (stat_result.st_mtime_ns, stat_result.st_size)

    @staticmethod
    def _connector_settings_changed(
        existing: GrafanaConnection,
        updated: GrafanaConnection,
    ) -> bool:
        """Return True when a connection change requires a new HTTP client."""
        return (
            str(existing.url),
            existing.timeout,
            existing.verify_ssl,
        ) != (
            str(updated.url),
            updated.timeout,
            updated.verify_ssl,
        )

    def _build_connections(
        self,
    ) -> tuple[dict[str, GrafanaConnection], dict[str, GrafanaConnector], ConfigMarker]:
        """Build fresh connection and connector maps from one config snapshot."""
        yaml_text, marker = self._read_connections_config_snapshot()
        parser = ConfigParser(
            self.runtime_paths.connections_file,
            state_path=self.runtime_paths.state_file,
        )
        loaded_connections = parser.load_config_from_text(yaml_text)
        built_connections: dict[str, GrafanaConnection] = {}
        built_connectors: dict[str, GrafanaConnector] = {}

        for connection in loaded_connections:
            conn_name = connection.connection_name
            existing_connection = self._connections.get(conn_name)
            existing_connector = self._connectors.get(conn_name)

            if (
                existing_connection is not None
                and existing_connector is not None
                and not self._connector_settings_changed(
                    existing_connection, connection
                )
            ):
                connector = existing_connector
            else:
                connector = GrafanaConnector(connection)

            built_connections[conn_name] = connection
            built_connectors[conn_name] = connector
            logger.info("Loaded connection: %s (%s)", conn_name, connection.url)

        return built_connections, built_connectors, marker

    def _replace_active_connections(
        self,
        connections: dict[str, GrafanaConnection],
        connectors: dict[str, GrafanaConnector],
        marker: ConfigMarker,
    ) -> None:
        """Swap in freshly loaded connections while preserving in-flight clients."""
        previous_retired_connectors = self._retired_connectors
        retired_connectors = [
            connector
            for name, connector in self._connectors.items()
            if connectors.get(name) is not connector
        ]
        self._retired_connectors = retired_connectors
        self._connections = connections
        self._connectors = connectors
        self._connections_config_marker = marker

        # Update reused connectors only after the reload succeeded fully.
        for name, connector in self._connectors.items():
            connector.connection = self._connections[name]

        for connector in previous_retired_connectors:
            self._schedule_connector_close(connector)

    @staticmethod
    def _schedule_connector_close(connector: GrafanaConnector) -> None:
        """Close retired connectors in the background when an event loop is active."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(connector.close())

    def _reload_connections_if_needed(self) -> None:
        """Reload connections.yaml when it changes, keeping the last good config."""
        previous_marker = self._connections_config_marker
        current_marker = self._read_connections_config_marker()

        if current_marker == previous_marker:
            return

        logger.info(
            "Detected change in %s; reloading connections",
            self.runtime_paths.connections_file,
        )
        try:
            connections, connectors, marker = self._build_connections()
        except Exception as exc:
            logger.warning(
                "Failed to reload configuration from %s; keeping %s previously loaded connection(s): %s",
                self.runtime_paths.connections_file,
                len(self._connections),
                exc,
            )
            return

        self._replace_active_connections(connections, connectors, marker)
        logger.info(
            "Reloaded %s Grafana connection(s) from %s",
            len(self._connections),
            self.runtime_paths.connections_file,
        )

    def _register_tools(self) -> None:
        register_core_tools(self.mcp, self.connectors, self.connections)
        register_dashboard_tools(self.mcp, self.connectors)
        register_datasource_tools(self.mcp, self.connectors)
        register_alert_tools(self.mcp, self.connectors)
        register_user_tools(self.mcp, self.connectors)

        if self.allow_writes:
            logger.info("Write endpoints enabled for %s", self.server_name)
            register_admin_tools(self.mcp, self.connectors)
        else:
            logger.info("Write endpoints disabled for %s", self.server_name)

    async def cleanup(self) -> None:
        seen: set[int] = set()
        for connector in [*self._connectors.values(), *self._retired_connectors]:
            connector_id = id(connector)
            if connector_id in seen:
                continue
            seen.add(connector_id)
            await connector.close()

    def run(self) -> None:
        if not self._connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info("Loaded %s Grafana connection(s)", len(self._connections))

        self.mcp.run()


def write_sample_config(
    runtime_paths: RuntimePaths, *, overwrite: bool = False
) -> Path:
    """Write a sample connections.yaml for package-based installs."""
    runtime_paths.ensure_directories()

    config_path = runtime_paths.connections_file
    if config_path.exists() and not overwrite:
        raise FileExistsError(
            f"Config file already exists at {config_path}. Re-run with --overwrite to replace it."
        )

    config_path.write_text(SAMPLE_CONNECTIONS_YAML, encoding="utf-8")
    runtime_paths.schema_file.write_text(
        SAMPLE_CONNECTIONS_SCHEMA_JSON,
        encoding="utf-8",
    )
    return config_path


def _resolve_command_name(argv0: str | None = None) -> str:
    """Normalize the invoking command name to a supported public entrypoint."""
    candidate = Path(argv0 or (sys.argv[0] if sys.argv else "")).name
    if candidate == WRITE_COMMAND:
        return WRITE_COMMAND
    return READ_ONLY_COMMAND


def _build_cli_description(command_name: str) -> str:
    """Return a short description for the active public command."""
    if command_name == WRITE_COMMAND:
        return "MCP Grafana Write Server - Write-capable access to Grafana instances"
    return "MCP Read-Only Grafana Server - Read-only access to Grafana instances"


def build_arg_parser(command_name: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=command_name,
        description=_build_cli_description(command_name),
    )
    parser.add_argument(
        "--config-dir",
        help="Directory containing connections.yaml",
    )
    parser.add_argument(
        "--state-dir",
        help="Directory containing session_tokens.json",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory reserved for cache files",
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print resolved config/state/cache paths and exit",
    )
    parser.add_argument(
        "--write-sample-config",
        action="store_true",
        help="Write a sample connections.yaml to the resolved config path and exit",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace connections.yaml when used with --write-sample-config",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=sorted(SUBCOMMAND_HANDLERS),
        help="Optional management command to run instead of starting the MCP server",
    )
    parser.add_argument(
        "command_args",
        nargs=argparse.REMAINDER,
        help=argparse.SUPPRESS,
    )
    return parser


def _forward_shared_runtime_args(args: argparse.Namespace) -> list[str]:
    forwarded: list[str] = []
    if args.config_dir:
        forwarded.extend(["--config-dir", args.config_dir])
    if args.state_dir:
        forwarded.extend(["--state-dir", args.state_dir])
    if args.cache_dir:
        forwarded.extend(["--cache-dir", args.cache_dir])
    if args.print_paths:
        forwarded.append("--print-paths")
    return forwarded


def _dispatch_subcommand(args: argparse.Namespace, command_name: str) -> None:
    """Execute a management subcommand through the public root CLI."""
    forwarded_args = _forward_shared_runtime_args(args)
    command_argv = [
        f"{command_name} {args.command}",
        *forwarded_args,
        *args.command_args,
    ]

    original_argv = sys.argv
    try:
        sys.argv = command_argv
        SUBCOMMAND_HANDLERS[args.command]()
    finally:
        sys.argv = original_argv


def _main(command_name: str | None = None) -> None:
    command_name = _resolve_command_name(command_name)
    parser = build_arg_parser(command_name)
    args = parser.parse_args()

    if args.command and (args.write_sample_config or args.overwrite):
        parser.error(
            "--write-sample-config and --overwrite can only be used without a subcommand"
        )

    if args.command:
        _dispatch_subcommand(args, command_name)
        return

    if args.overwrite and not args.write_sample_config:
        parser.error("--overwrite can only be used with --write-sample-config")

    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.write_sample_config:
        try:
            config_path = write_sample_config(runtime_paths, overwrite=args.overwrite)
        except FileExistsError as exc:
            parser.error(str(exc))
        print(f"Wrote sample config to {config_path}")
        if not args.print_paths:
            return

    if args.print_paths:
        print(runtime_paths.render())
        return

    server = ReadOnlyGrafanaServer(
        runtime_paths=runtime_paths,
        allow_writes=command_name == WRITE_COMMAND,
        server_name=command_name,
    )
    exit_code = 0

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as exc:
        logger.error("Server error: %s", exc)
        exit_code = 1
    finally:
        try:
            asyncio.run(server.cleanup())
        except Exception as cleanup_exc:
            logger.warning("Error during shutdown cleanup: %s", cleanup_exc)

    if exit_code:
        sys.exit(exit_code)


def main() -> None:
    """Auto-detect the invoking entrypoint and launch the matching mode."""
    _main()


def main_read_only() -> None:
    """Launch the read-only public command."""
    _main(READ_ONLY_COMMAND)


def main_write() -> None:
    """Launch the write-capable public command."""
    _main(WRITE_COMMAND)


if __name__ == "__main__":
    main()
