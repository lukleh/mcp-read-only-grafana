"""Custom exceptions for Grafana MCP server.

This module provides a hierarchy of exception types for better error handling
and clearer error messages when working with Grafana APIs.

Exception Hierarchy:
    GrafanaError (base)
    ├── ConnectionNotFoundError - Invalid connection name
    ├── AuthenticationError - 401 responses, expired sessions
    ├── PermissionDeniedError - 403 responses, insufficient permissions
    ├── GrafanaAPIError - Other HTTP errors from Grafana API
    └── GrafanaTimeoutError - Request timeout
"""

from typing import List, Optional


class GrafanaError(Exception):
    """Base exception for all Grafana-related errors."""

    pass


class ConnectionNotFoundError(GrafanaError):
    """Raised when a connection name doesn't exist in the configuration.

    Attributes:
        connection_name: The requested connection name that wasn't found.
        available: List of valid connection names.
    """

    def __init__(self, connection_name: str, available: List[str]):
        self.connection_name = connection_name
        self.available = available
        available_str = ", ".join(available) if available else "(none configured)"
        super().__init__(
            f"Connection '{connection_name}' not found. "
            f"Available connections: {available_str}"
        )


class AuthenticationError(GrafanaError):
    """Raised when authentication fails (HTTP 401).

    This typically indicates an expired or invalid session token or API key.

    Attributes:
        connection_name: The connection that failed authentication.
        message: Additional context about the failure.
    """

    def __init__(self, connection_name: str, message: str = ""):
        self.connection_name = connection_name
        detail = f" {message}" if message else " Session may have expired."
        super().__init__(f"Authentication failed for {connection_name}.{detail}")


class PermissionDeniedError(GrafanaError):
    """Raised when user lacks required permissions (HTTP 403).

    Attributes:
        connection_name: The connection where permission was denied.
        operation: Optional description of the attempted operation.
    """

    def __init__(self, connection_name: str, operation: str = ""):
        self.connection_name = connection_name
        self.operation = operation
        detail = f" for {operation}" if operation else ""
        super().__init__(
            f"Permission denied for {connection_name}{detail}. "
            "User may lack required permissions."
        )


class GrafanaAPIError(GrafanaError):
    """Raised for Grafana API errors with HTTP status codes.

    Attributes:
        status_code: The HTTP status code returned.
        message: The error message or response body.
        connection_name: Optional connection name for context.
    """

    def __init__(
        self, status_code: int, message: str, connection_name: Optional[str] = None
    ):
        self.status_code = status_code
        self.message = message
        self.connection_name = connection_name
        prefix = f"[{connection_name}] " if connection_name else ""
        super().__init__(f"{prefix}HTTP {status_code}: {message}")


class GrafanaTimeoutError(GrafanaError):
    """Raised when a Grafana API request times out.

    Attributes:
        timeout_seconds: The timeout value that was exceeded.
        connection_name: Optional connection name for context.
    """

    def __init__(self, timeout_seconds: int, connection_name: Optional[str] = None):
        self.timeout_seconds = timeout_seconds
        self.connection_name = connection_name
        prefix = f"[{connection_name}] " if connection_name else ""
        super().__init__(f"{prefix}Request timed out after {timeout_seconds} seconds")
