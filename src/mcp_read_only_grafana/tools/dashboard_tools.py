"""Dashboard-related MCP tools.

This module provides tools for:
- Searching dashboards
- Getting dashboard info, panels, and full definitions
- Listing folders and folder contents
- Dashboard version history
"""

import json
from collections.abc import Mapping
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


def register_dashboard_tools(
    mcp: FastMCP,
    connectors: Mapping[str, GrafanaConnector],
) -> None:
    """Register dashboard-related MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
    """

    @mcp.tool()
    async def search_dashboards(
        connection_name: str,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        Search for dashboards by name or tag.

        Args:
            connection_name: Name of the Grafana connection
            query: Optional search query for dashboard names
            tag: Optional tag to filter dashboards
            limit: Optional maximum number of results per page
            page: Optional page number (1-indexed)
            fields: Optional subset of Grafana search fields to return (for example: id,orgId,uid,title,uri,url,slug,type,tags,isStarred,folderId,folderUid,folderTitle,folderUrl)

        Returns:
            JSON string with list of matching dashboards.
        """
        connector = get_connector(connectors, connection_name)
        dashboards = await connector.search_dashboards(
            query=query,
            tag=tag,
            limit=limit,
            page=page,
            fields=fields,
        )
        return json.dumps(dashboards, indent=2)

    @mcp.tool()
    async def get_dashboard_info(connection_name: str, dashboard_uid: str) -> str:
        """
        Get lightweight dashboard metadata and panel list (without full panel definitions).

        This is the RECOMMENDED first step for exploring dashboards, especially large ones.
        Returns dashboard metadata, variables, and a list of all panels with basic info (id, title, type).
        Use get_dashboard_panel() to get full details for specific panels of interest.

        Args:
            connection_name: Name of the Grafana connection
            dashboard_uid: UID of the dashboard

        Returns:
            JSON string with dashboard metadata and panel summary list.
        """
        connector = get_connector(connectors, connection_name)
        info = await connector.get_dashboard_info(dashboard_uid)
        return json.dumps(info, indent=2)

    @mcp.tool()
    async def get_dashboard_panel(
        connection_name: str, dashboard_uid: str, panel_id: int
    ) -> str:
        """
        Get full configuration for a single panel from a dashboard.

        Use this after get_dashboard_info() to explore specific panels in detail.
        Returns complete panel definition including queries, transforms, and display settings.

        Args:
            connection_name: Name of the Grafana connection
            dashboard_uid: UID of the dashboard
            panel_id: ID of the specific panel to retrieve

        Returns:
            JSON string with complete panel configuration.
        """
        connector = get_connector(connectors, connection_name)
        panel = await connector.get_dashboard_panel(dashboard_uid, panel_id)
        return json.dumps(panel, indent=2)

    @mcp.tool()
    async def get_dashboard(connection_name: str, dashboard_uid: str) -> str:
        """
        Get full dashboard definition including all panels and settings.

        WARNING: Large dashboards (>50 panels) will likely exceed MCP response limits (25,000 tokens).
        For large dashboards, use this workflow instead:
        1. get_dashboard_info() - Get overview and panel list
        2. get_dashboard_panel() - Get details for specific panels of interest

        Args:
            connection_name: Name of the Grafana connection
            dashboard_uid: UID of the dashboard to retrieve

        Returns:
            JSON string with complete dashboard definition.
        """
        connector = get_connector(connectors, connection_name)
        dashboard = await connector.get_dashboard(dashboard_uid)
        return json.dumps(dashboard, indent=2)

    @mcp.tool()
    async def get_dashboard_panels(connection_name: str, dashboard_uid: str) -> str:
        """
        Get simplified panel information from a dashboard.

        Use this instead of get_dashboard() for large dashboards to avoid MCP size limits.
        Returns only essential panel information without full query definitions.

        Args:
            connection_name: Name of the Grafana connection
            dashboard_uid: UID of the dashboard

        Returns:
            JSON string with list of panels and their basic properties.
        """
        connector = get_connector(connectors, connection_name)
        panels = await connector.get_dashboard_panels(dashboard_uid)
        return json.dumps(panels, indent=2)

    @mcp.tool()
    async def list_folders(connection_name: str) -> str:
        """
        List all folders in the Grafana instance.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with list of folders and their properties.
        """
        connector = get_connector(connectors, connection_name)
        folders = await connector.list_folders()
        return json.dumps(folders, indent=2)

    @mcp.tool()
    async def list_folder_dashboards(
        connection_name: str,
        folder_uid: str,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        List all dashboards in a specific folder.

        Args:
            connection_name: Name of the Grafana connection
            folder_uid: UID of the folder
            limit: Optional maximum results per page
            page: Optional page number
            fields: Optional subset of Grafana search fields to return (for example: id,orgId,uid,title,uri,url,slug,type,tags,isStarred,folderId,folderUid,folderTitle,folderUrl)

        Returns:
            JSON string with list of dashboards in the folder.
        """
        connector = get_connector(connectors, connection_name)
        dashboards = await connector.list_folder_dashboards(
            folder_uid=folder_uid,
            limit=limit,
            page=page,
            fields=fields,
        )
        return json.dumps(dashboards, indent=2)

    @mcp.tool()
    async def get_dashboard_versions(connection_name: str, dashboard_uid: str) -> str:
        """
        Get version history of a dashboard.

        Args:
            connection_name: Name of the Grafana connection
            dashboard_uid: UID of the dashboard

        Returns:
            JSON string with list of dashboard versions.
        """
        connector = get_connector(connectors, connection_name)
        versions = await connector.get_dashboard_versions(dashboard_uid)
        return json.dumps(versions, indent=2)
