"""Validation utilities for MCP tools.

This module provides helper functions that centralize common validation
patterns used across all MCP tool functions.
"""

import functools
from collections.abc import Awaitable, Callable, Mapping
from typing import ParamSpec, TypeVar

from mcp import MCPError
from mcp.server.mcpserver.exceptions import ToolError

from .exceptions import ConnectionNotFoundError, GrafanaError
from .grafana_connector import GrafanaConnector

P = ParamSpec("P")
R = TypeVar("R")

# Exception types the tools raise for failures the caller can act on: a Grafana
# error (unknown connection, 401/403, other HTTP status, transport failure,
# timeout), a rejected argument or unparseable response (ValueError), or a
# problem reading or writing the session state file (OSError). Anything else is
# a bug and stays a crash.
ANTICIPATED_TOOL_ERRORS: tuple[type[Exception], ...] = (
    GrafanaError,
    ValueError,
    OSError,
)


def surface_tool_errors(fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """Report an anticipated tool failure to the caller with its message.

    Since mcp 2.1 the SDK treats any exception other than ``ToolError`` (or a
    protocol-level ``MCPError``) as a crash and replaces its text with the
    generic ``Error executing tool <name>``. The failures listed in
    ``ANTICIPATED_TOOL_ERRORS`` are re-raised as ``ToolError`` so the caller
    sees the reason. Anything else keeps the SDK's crash handling: the text
    stays on the server, logged with its traceback.

    Apply it below ``@mcp.tool()`` on every tool. ``functools.wraps`` keeps the
    signature and docstring the SDK reads to build the tool schema.
    """

    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return await fn(*args, **kwargs)
        except (ToolError, MCPError):
            raise
        except ANTICIPATED_TOOL_ERRORS as exc:
            raise ToolError(str(exc) or type(exc).__name__) from exc

    return wrapper


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
