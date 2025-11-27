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
    """MCP Read-Only Grafana Server using FastMCP"""

    def __init__(
        self, config_path: str = "connections.yaml", allow_admin: bool = False
    ):
        """Initialize the server with configuration

        Args:
            config_path: Path to the connections.yaml configuration file
            allow_admin: Enable admin-only endpoints (provisioning API). Requires admin permissions.
        """
        self.config_path = config_path
        self.allow_admin = allow_admin
        self.connections: Dict[str, GrafanaConnection] = {}
        self.connectors: Dict[str, GrafanaConnector] = {}

        # Initialize FastMCP server
        self.mcp = FastMCP("mcp-read-only-grafana")

        # Load connections
        self._load_connections()

        # Register tools from domain modules
        self._register_tools()

    def _load_connections(self):
        """Load all connections from config file"""
        parser = ConfigParser(self.config_path)

        try:
            connections = parser.load_config()
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info(
                "Please create a connections.yaml file from connections.yaml.sample"
            )
            return
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

        for conn in connections:
            self.connections[conn.connection_name] = conn
            self.connectors[conn.connection_name] = GrafanaConnector(conn)
            logger.info(f"Loaded connection: {conn.connection_name} ({conn.url})")

    def _register_tools(self):
        """Register all MCP tools organized by domain."""
        # Core tools (list_connections, get_health, get_current_org)
        register_core_tools(self.mcp, self.connectors, self.connections)

        # Dashboard tools
        register_dashboard_tools(self.mcp, self.connectors)

        # Datasource tools
        register_datasource_tools(self.mcp, self.connectors)

        # Alert tools
        register_alert_tools(self.mcp, self.connectors)

        # User/team/annotation tools
        register_user_tools(self.mcp, self.connectors)

        # Admin tools (only if --allow-admin flag is set)
        if self.allow_admin:
            logger.info("Admin endpoints enabled (--allow-admin)")
            register_admin_tools(self.mcp, self.connectors)
        else:
            logger.info("Admin endpoints disabled (use --allow-admin to enable)")

    async def cleanup(self):
        """Clean up resources"""
        for connector in self.connectors.values():
            await connector.close()

    def run(self):
        """Run the FastMCP server"""
        if not self.connections:
            logger.warning(
                "No connections loaded. Server will run with limited functionality."
            )
        else:
            logger.info(f"Loaded {len(self.connections)} Grafana connection(s)")

        # Run the FastMCP server (defaults to stdio transport)
        self.mcp.run()


def main():
    """Main entry point for the MCP server"""
    parser = argparse.ArgumentParser(
        description="MCP Read-Only Grafana Server - Secure read-only access to Grafana instances"
    )
    parser.add_argument(
        "config",
        nargs="?",
        default="connections.yaml",
        help="Path to connections.yaml configuration file (default: connections.yaml)",
    )
    parser.add_argument(
        "--allow-admin",
        action="store_true",
        help="Enable admin-only endpoints (Provisioning API). Requires Grafana admin permissions.",
    )

    args = parser.parse_args()

    # Create and run server
    server = ReadOnlyGrafanaServer(
        config_path=args.config, allow_admin=args.allow_admin
    )

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
