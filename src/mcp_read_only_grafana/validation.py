"""Validation utilities for MCP tools.

This module provides helper functions that centralize common validation
patterns used across all MCP tool functions.
"""

from collections.abc import Mapping

from .exceptions import ConnectionNotFoundError
from .grafana_connector import GrafanaConnector


def get_connector(
    connectors: Mapping[str, GrafanaConnector],
    connection_name: str,
) -> GrafanaConnector:
    """Get a connector by name or raise ConnectionNotFoundError.

    This centralizes the repeated validation pattern found in all tool functions,
    replacing 50+ instances of:

        if connection_name not in self.connectors:
            raise ValueError(
                f"Connection '{connection_name}' not found. "
                f"Available connections: {', '.join(self.connectors.keys())}"
            )
        connector = self.connectors[connection_name]

    With a single call:

        connector = get_connector(connectors, connection_name)

    Args:
        connectors: Dictionary mapping connection names to GrafanaConnector instances.
        connection_name: The name of the connection to retrieve.

    Returns:
        The GrafanaConnector for the specified connection.

    Raises:
        ConnectionNotFoundError: If connection_name is not in connectors.

    Example:
        ```python
        @mcp.tool()
        async def get_health(connection_name: str) -> str:
            connector = get_connector(connectors, connection_name)
            health = await connector.get_health()
            return json.dumps(health, indent=2)
        ```
    """
    connector = connectors.get(connection_name)
    if connector is None:
        raise ConnectionNotFoundError(
            connection_name=connection_name,
            available=list(connectors.keys()),
        )
    return connector
