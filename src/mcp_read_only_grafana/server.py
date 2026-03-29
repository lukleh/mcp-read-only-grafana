#!/usr/bin/env python3
"""
MCP Read-Only Grafana Server
Provides secure read-only access to Grafana instances via MCP protocol.
"""

import argparse
import asyncio
import logging
import sys
from importlib.resources import files
from pathlib import Path
from textwrap import dedent
from typing import Callable, Dict

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
SAMPLE_CONNECTIONS_SCHEMA_JSON = (
    files("mcp_read_only_grafana")
    .joinpath("connections.schema.json")
    .read_text(encoding="utf-8")
)
SAMPLE_CONNECTIONS_YAML = dedent(
    """
    # yaml-language-server: $schema=./connections.schema.json
    # MCP Read-Only Grafana Server - Connection Configuration Sample
    # Edit this file to configure your Grafana connections.
    # Default runtime location: ~/.config/lukleh/mcp-read-only-grafana/connections.yaml

    # Basic Grafana connection
    - connection_name: production_grafana
      url: https://grafana.example.com
      description: Production Grafana instance
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
    # - Credentials are read from environment variables:
    #     - Session cookie: GRAFANA_SESSION_<CONNECTION_NAME>
    #     - API key (Bearer): GRAFANA_API_KEY_<CONNECTION_NAME>
    #   If both are set, API key takes precedence.
    # - Connection names should use only letters, numbers, underscores, and hyphens
    # - URLs should not include trailing slashes
    # - Credentials are reloaded from the runtime environment and persisted session state before each request to support token rotation
    # - If both sources contain a session cookie, the persisted session state wins until you update or remove it
    """
).lstrip()
SUBCOMMAND_HANDLERS: dict[str, Callable[[], None]] = {
    "test-connection": test_connection_command.main,
    "validate-config": validate_config_command.main,
}


class ReadOnlyGrafanaServer:
    """MCP Read-Only Grafana Server using FastMCP."""

    def __init__(self, runtime_paths: RuntimePaths, allow_admin: bool = False):
        self.runtime_paths = runtime_paths
        self.allow_admin = allow_admin
        self.connections: Dict[str, GrafanaConnection] = {}
        self.connectors: Dict[str, GrafanaConnector] = {}

        self.mcp = FastMCP("mcp-read-only-grafana")

        self._load_connections()
        self._register_tools()

    def _load_connections(self) -> None:
        parser = ConfigParser(
            self.runtime_paths.connections_file,
            state_path=self.runtime_paths.state_file,
        )

        try:
            connections = parser.load_config()
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

        for connection in connections:
            self.connections[connection.connection_name] = connection
            self.connectors[connection.connection_name] = GrafanaConnector(connection)
            logger.info(
                "Loaded connection: %s (%s)",
                connection.connection_name,
                connection.url,
            )

    def _register_tools(self) -> None:
        register_core_tools(self.mcp, self.connectors, self.connections)
        register_dashboard_tools(self.mcp, self.connectors)
        register_datasource_tools(self.mcp, self.connectors)
        register_alert_tools(self.mcp, self.connectors)
        register_user_tools(self.mcp, self.connectors)

        if self.allow_admin:
            logger.info("Admin endpoints enabled (--allow-admin)")
            register_admin_tools(self.mcp, self.connectors)
        else:
            logger.info("Admin endpoints disabled (use --allow-admin to enable)")

    async def cleanup(self) -> None:
        for connector in self.connectors.values():
            await connector.close()

    def run(self) -> None:
        if not self.connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info("Loaded %s Grafana connection(s)", len(self.connections))

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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-read-only-grafana",
        description=(
            "MCP Read-Only Grafana Server - Secure read-only access to Grafana instances"
        )
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
        "--allow-admin",
        action="store_true",
        help="Enable admin-only endpoints (Provisioning API). Requires Grafana admin permissions.",
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


def _dispatch_subcommand(args: argparse.Namespace) -> None:
    """Execute a management subcommand through the public root CLI."""
    forwarded_args = _forward_shared_runtime_args(args)
    command_argv = [
        f"mcp-read-only-grafana {args.command}",
        *forwarded_args,
        *args.command_args,
    ]

    original_argv = sys.argv
    try:
        sys.argv = command_argv
        SUBCOMMAND_HANDLERS[args.command]()
    finally:
        sys.argv = original_argv


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.command and (args.write_sample_config or args.overwrite):
        parser.error(
            "--write-sample-config and --overwrite can only be used without a subcommand"
        )

    if args.command and args.allow_admin:
        parser.error("--allow-admin can only be used when starting the MCP server")

    if args.command:
        _dispatch_subcommand(args)
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
        allow_admin=args.allow_admin,
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


if __name__ == "__main__":
    main()
