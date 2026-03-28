"""User, team, and annotation MCP tools.

This module provides tools for:
- Getting current user profile and permissions
- Listing organization users and teams
- Listing annotations
"""

import json
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


def register_user_tools(
    mcp: FastMCP,
    connectors: Dict[str, GrafanaConnector],
) -> None:
    """Register user-related MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
    """

    @mcp.tool()
    async def get_current_user(connection_name: str) -> str:
        """
        Get profile information for the authenticated Grafana user.

        Note: This endpoint only works with session-based authentication.
        API keys are service account tokens and are not associated with a
        user profile. When using API key auth, this will return a 404 error.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string describing the current user (id, login, email, role, etc.).
        """
        connector = get_connector(connectors, connection_name)
        user = await connector.get_current_user()
        return json.dumps(user, indent=2)

    @mcp.tool()
    async def get_user_permissions(connection_name: str) -> str:
        """
        Get permissions granted to the authenticated user.

        Lists the permissions granted to the signed-in user. Returns a map of
        action names to their authorized scopes. Useful for checking what the
        current API key or session can access.

        Note: Requires Grafana 8.0+ with RBAC enabled. May return 404 on older
        versions or instances without fine-grained access control.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string mapping action names to authorized scopes.
        """
        connector = get_connector(connectors, connection_name)
        permissions = await connector.get_user_permissions()
        return json.dumps(permissions, indent=2)

    @mcp.tool()
    async def list_users(
        connection_name: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        List all users in the current organization.

        Args:
            connection_name: Name of the Grafana connection
            page: Optional page number (1-indexed)
            per_page: Optional page size
            fields: Optional subset of Grafana org-user fields (for example: orgId,userId,avatarUrl,email,name,login,role,lastSeenAt,lastSeenAtAge,authLabels)

        Returns:
            JSON string with list of users.
        """
        connector = get_connector(connectors, connection_name)
        users = await connector.list_users(
            page=page, per_page=per_page, fields=fields
        )
        return json.dumps(users, indent=2)

    @mcp.tool()
    async def list_teams(
        connection_name: str,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        List all teams in the organization.

        Args:
            connection_name: Name of the Grafana connection
            page: Optional page number
            per_page: Optional page size
            fields: Optional subset of Grafana team fields (for example: id,orgId,uid,name,avatarUrl,email,memberCount)

        Returns:
            JSON string with list of teams.
        """
        connector = get_connector(connectors, connection_name)
        teams = await connector.list_teams(
            page=page, per_page=per_page, fields=fields
        )
        return json.dumps(teams, indent=2)

    @mcp.tool()
    async def list_annotations(
        connection_name: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        dashboard_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """
        List annotations for a time range.

        Args:
            connection_name: Name of the Grafana connection
            time_from: Start time for annotations
            time_to: End time for annotations
            dashboard_id: Filter by dashboard ID
            tags: Filter by tags

        Returns:
            JSON string with list of annotations.
        """
        connector = get_connector(connectors, connection_name)
        annotations = await connector.list_annotations(
            time_from, time_to, dashboard_id, tags
        )
        return json.dumps(annotations, indent=2)
