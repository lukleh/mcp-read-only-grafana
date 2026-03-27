#!/usr/bin/env python3
"""
MCP Read-Only Grafana Server
Provides secure read-only access to Grafana instances via MCP protocol.
"""

import argparse
import logging
import sys
from typing import Dict

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

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


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


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
        "--allow-admin",
        action="store_true",
        help="Enable admin-only endpoints (Provisioning API). Requires Grafana admin permissions.",
    )
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.print_paths:
        print(runtime_paths.render())
        return

    server = ReadOnlyGrafanaServer(
        runtime_paths=runtime_paths,
        allow_admin=args.allow_admin,
    )

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as exc:
        logger.error("Server error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
