"""Core MCP tools for connection management and health checks.

This module provides:
- list_connections: List all available Grafana connections
- get_health: Check Grafana instance health and version
- get_current_org: Get current organization information
"""

import json
from collections.abc import Mapping

from mcp.server.fastmcp import FastMCP

from ..config import GrafanaConnection
from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


def register_core_tools(
    mcp: FastMCP,
    connectors: Mapping[str, GrafanaConnector],
    connections: Mapping[str, GrafanaConnection],
) -> None:
    """Register core MCP tools for connection management.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
        connections: Dictionary mapping connection names to GrafanaConnection configs
    """

    @mcp.tool()
    async def list_connections() -> str:
        """
        List all available Grafana connections with their configuration details.

        Returns:
            JSON string with connection details including name, url, and description.
        """
        if not connections:
            return json.dumps({"message": "No connections configured"}, indent=2)

        conn_list = []
        for name, conn in connections.items():
            conn_info = {
                "name": name,
                "url": str(conn.url),
                "description": conn.description,
                "timeout": conn.timeout,
                "verify_ssl": conn.verify_ssl,
            }
            conn_list.append(conn_info)

        return json.dumps(conn_list, indent=2)

    @mcp.tool()
    async def get_health(connection_name: str) -> str:
        """
        Check Grafana instance health and version information.

        Args:
            connection_name: Name of the Grafana connection to check

        Returns:
            JSON string with health status and version information.
        """
        connector = get_connector(connectors, connection_name)
        health = await connector.get_health()
        return json.dumps(health, indent=2)

    @mcp.tool()
    async def get_current_org(connection_name: str) -> str:
        """
        Get current organization information.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with organization details.
        """
        connector = get_connector(connectors, connection_name)
        org = await connector.get_current_org()
        return json.dumps(org, indent=2)
