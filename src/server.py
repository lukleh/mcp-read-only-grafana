#!/usr/bin/env python3
"""
MCP Read-Only Grafana Server
Provides secure read-only access to Grafana instances via MCP protocol.
"""

import argparse
import logging
import sys
import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .config import ConfigParser, GrafanaConnection
from .grafana_connector import GrafanaConnector

logging.basicConfig(level=logging.INFO)
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

        # Setup tools
        self._setup_tools()

        # Setup admin tools if enabled
        if self.allow_admin:
            logger.info("Admin endpoints enabled (--allow-admin)")
            self._setup_admin_tools()
        else:
            logger.info("Admin endpoints disabled (use --allow-admin to enable)")

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

    def _setup_tools(self):
        """Setup MCP tools using FastMCP decorators"""

        @self.mcp.tool()
        async def list_connections() -> str:
            """
            List all available Grafana connections with their configuration details.

            Returns:
                JSON string with connection details including name, url, and description.
            """
            if not self.connections:
                return json.dumps({"message": "No connections configured"}, indent=2)

            conn_list = []
            for name, conn in self.connections.items():
                conn_info = {
                    "name": name,
                    "url": str(conn.url),
                    "description": conn.description,
                    "timeout": conn.timeout,
                    "verify_ssl": conn.verify_ssl,
                }
                conn_list.append(conn_info)

            return json.dumps(conn_list, indent=2)

        @self.mcp.tool()
        async def get_health(connection_name: str) -> str:
            """
            Check Grafana instance health and version information.

            Args:
                connection_name: Name of the Grafana connection to check

            Returns:
                JSON string with health status and version information.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            health = await connector.get_health()
            return json.dumps(health, indent=2)

        @self.mcp.tool()
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
                fields: Optional subset of Grafana fields to return (uid,title,url,type,tags,folderTitle,folderUid)

            Returns:
                JSON string with list of matching dashboards.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            dashboards = await connector.search_dashboards(
                query=query,
                tag=tag,
                limit=limit,
                page=page,
                fields=fields,
            )
            return json.dumps(dashboards, indent=2)

        @self.mcp.tool()
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
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            info = await connector.get_dashboard_info(dashboard_uid)
            return json.dumps(info, indent=2)

        @self.mcp.tool()
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
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            panel = await connector.get_dashboard_panel(dashboard_uid, panel_id)
            return json.dumps(panel, indent=2)

        @self.mcp.tool()
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
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            dashboard = await connector.get_dashboard(dashboard_uid)
            return json.dumps(dashboard, indent=2)

        @self.mcp.tool()
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
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            panels = await connector.get_dashboard_panels(dashboard_uid)
            return json.dumps(panels, indent=2)

        @self.mcp.tool()
        async def list_folders(connection_name: str) -> str:
            """
            List all folders in the Grafana instance.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of folders and their properties.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            folders = await connector.list_folders()
            return json.dumps(folders, indent=2)

        @self.mcp.tool()
        async def list_datasources(connection_name: str) -> str:
            """
            List all configured data sources in Grafana.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of data sources and their configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            datasources = await connector.list_datasources()
            return json.dumps(datasources, indent=2)

        @self.mcp.tool()
        async def get_datasource_health(
            connection_name: str, datasource_uid: str
        ) -> str:
            """
            Run the health check for a specific datasource.

            Args:
                connection_name: Name of the Grafana connection
                datasource_uid: UID of the datasource to probe

            Returns:
                JSON string with health information reported by Grafana.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            health = await connector.get_datasource_health(datasource_uid)
            return json.dumps(health, indent=2)

        @self.mcp.tool()
        async def query_prometheus(
            connection_name: str,
            datasource_uid: str,
            query: str,
            time_from: Optional[str] = None,
            time_to: Optional[str] = None,
            step: Optional[str] = None,
        ) -> str:
            """
            Execute a PromQL query against a Prometheus datasource.

            Args:
                connection_name: Name of the Grafana connection
                datasource_uid: UID of the Prometheus datasource
                query: PromQL query to execute
                time_from: Start time (e.g., 'now-1h' or timestamp)
                time_to: End time (e.g., 'now' or timestamp)
                step: Query resolution step (e.g., '15s')

            Returns:
                JSON string with query results.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            result = await connector.query_prometheus(
                datasource_uid, query, time_from, time_to, step
            )
            return json.dumps(result, indent=2)

        @self.mcp.tool()
        async def query_loki(
            connection_name: str,
            datasource_uid: str,
            query: str,
            time_from: Optional[str] = None,
            time_to: Optional[str] = None,
            limit: Optional[int] = 100,
        ) -> str:
            """
            Execute a LogQL query against a Loki datasource.

            Args:
                connection_name: Name of the Grafana connection
                datasource_uid: UID of the Loki datasource
                query: LogQL query to execute
                time_from: Start time in nanoseconds or relative time
                time_to: End time in nanoseconds or relative time
                limit: Maximum number of log lines to return

            Returns:
                JSON string with query results.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            result = await connector.query_loki(
                datasource_uid, query, time_from, time_to, limit
            )
            return json.dumps(result, indent=2)

        @self.mcp.tool()
        async def explore_query(
            connection_name: str,
            queries: List[Dict[str, Any]],
            range_from: Optional[str] = None,
            range_to: Optional[str] = None,
            max_data_points: Optional[int] = None,
            interval_ms: Optional[int] = None,
            additional_options: Optional[Dict[str, Any]] = None,
        ) -> str:
            """
            Execute a Grafana Explore query via the /api/ds/query endpoint.

            Args:
                connection_name: Name of the Grafana connection
                queries: List of Explore query definitions to execute
                range_from: Optional relative or absolute start time (e.g., 'now-6h')
                range_to: Optional end time (e.g., 'now')
                max_data_points: Optional maximum number of datapoints to request
                interval_ms: Optional query interval in milliseconds
                additional_options: Extra fields to merge into the request body

            Returns:
                JSON string with the query response payload.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            result = await connector.explore_query(
                queries=queries,
                range_from=range_from,
                range_to=range_to,
                max_data_points=max_data_points,
                interval_ms=interval_ms,
                additional_options=additional_options,
            )
            return json.dumps(result, indent=2)

        @self.mcp.tool()
        async def get_current_org(connection_name: str) -> str:
            """
            Get current organization information.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with organization details.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            org = await connector.get_current_org()
            return json.dumps(org, indent=2)

        @self.mcp.tool()
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
                fields: Optional subset of Grafana fields (userId,email,name,login,role,lastSeenAt,lastSeenAtAge)

            Returns:
                JSON string with list of users.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            users = await connector.list_users(
                page=page, per_page=per_page, fields=fields
            )
            return json.dumps(users, indent=2)

        @self.mcp.tool()
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
                fields: Optional subset of Grafana fields (id,uid,name,email,memberCount)

            Returns:
                JSON string with list of teams.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            teams = await connector.list_teams(
                page=page, per_page=per_page, fields=fields
            )
            return json.dumps(teams, indent=2)

        @self.mcp.tool()
        async def get_alert_rule_by_uid(connection_name: str, alert_uid: str) -> str:
            """
            Get detailed information about a specific alert rule.

            Args:
                connection_name: Name of the Grafana connection
                alert_uid: UID of the alert rule

            Returns:
                JSON string with alert rule details.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            alert = await connector.get_alert_rule_by_uid(alert_uid)
            return json.dumps(alert, indent=2)

        @self.mcp.tool()
        async def get_ruler_rules(connection_name: str) -> str:
            """
            Get all alert rules from the Ruler API.

            Returns a dict mapping namespace (folder) to list of rule groups.
            Each rule group contains rules and evaluation configuration.
            This is the non-admin alternative to the Provisioning API.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with all rule groups organized by namespace.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            rules = await connector.get_ruler_rules()
            return json.dumps(rules, indent=2)

        @self.mcp.tool()
        async def get_ruler_namespace_rules(
            connection_name: str, namespace: str
        ) -> str:
            """
            Get all rule groups for a specific namespace (folder).

            Args:
                connection_name: Name of the Grafana connection
                namespace: The namespace/folder name

            Returns:
                JSON string with dict mapping namespace to rule groups.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            rules = await connector.get_ruler_namespace_rules(namespace)
            return json.dumps(rules, indent=2)

        @self.mcp.tool()
        async def get_ruler_group(
            connection_name: str, namespace: str, group_name: str
        ) -> str:
            """
            Get a specific alert rule group from a namespace.

            Args:
                connection_name: Name of the Grafana connection
                namespace: The namespace/folder name
                group_name: The rule group name

            Returns:
                JSON string with rule group configuration including all rules.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            group = await connector.get_ruler_group(namespace, group_name)
            return json.dumps(group, indent=2)

        @self.mcp.tool()
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
                fields: Optional subset of Grafana fields to return (uid,title,url,tags,folderUid)

            Returns:
                JSON string with list of dashboards in the folder.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            dashboards = await connector.list_folder_dashboards(
                folder_uid=folder_uid,
                limit=limit,
                page=page,
                fields=fields,
            )
            return json.dumps(dashboards, indent=2)

        @self.mcp.tool()
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
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            annotations = await connector.list_annotations(
                time_from, time_to, dashboard_id, tags
            )
            return json.dumps(annotations, indent=2)

        @self.mcp.tool()
        async def get_dashboard_versions(
            connection_name: str, dashboard_uid: str
        ) -> str:
            """
            Get version history of a dashboard.

            Args:
                connection_name: Name of the Grafana connection
                dashboard_uid: UID of the dashboard

            Returns:
                JSON string with list of dashboard versions.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            versions = await connector.get_dashboard_versions(dashboard_uid)
            return json.dumps(versions, indent=2)

        @self.mcp.tool()
        async def list_alerts(
            connection_name: str, folder_uid: Optional[str] = None
        ) -> str:
            """
            List alert rules, optionally filtered by folder.

            Args:
                connection_name: Name of the Grafana connection
                folder_uid: Optional folder UID to filter alerts

            Returns:
                JSON string with list of alert rules and their status.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            alerts = await connector.list_alerts(folder_uid=folder_uid)
            return json.dumps(alerts, indent=2)

    def _setup_admin_tools(self):
        """Setup admin-only MCP tools (Provisioning API)

        These tools require Grafana admin permissions and are only registered
        when --allow-admin flag is provided.
        """

        @self.mcp.tool()
        async def list_provisioned_alert_rules(connection_name: str) -> str:
            """
            [ADMIN] Fetch all provisioned alert rules via the read-only provisioning API.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with the complete ProvisionedAlertRules payload.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            rules = await connector.list_provisioned_alert_rules()
            return json.dumps(rules, indent=2)

        @self.mcp.tool()
        async def get_provisioned_alert_rule(
            connection_name: str, alert_uid: str
        ) -> str:
            """
            [ADMIN] Get a specific alert rule by UID from the provisioning API.

            Args:
                connection_name: Name of the Grafana connection
                alert_uid: UID of the alert rule

            Returns:
                JSON string with alert rule configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            rule = await connector.get_provisioned_alert_rule(alert_uid)
            return json.dumps(rule, indent=2)

        @self.mcp.tool()
        async def export_alert_rule(connection_name: str, alert_uid: str) -> str:
            """
            [ADMIN] Export a specific alert rule in provisioning format.

            Args:
                connection_name: Name of the Grafana connection
                alert_uid: UID of the alert rule to export

            Returns:
                JSON string with alert rule in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_alert_rule(alert_uid)
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def export_all_alert_rules(connection_name: str) -> str:
            """
            [ADMIN] Export all alert rules in provisioning format.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with all alert rules in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_all_alert_rules()
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def get_rule_group(
            connection_name: str, folder_uid: str, group: str
        ) -> str:
            """
            [ADMIN] Get a specific alert rule group.

            Args:
                connection_name: Name of the Grafana connection
                folder_uid: UID of the folder
                group: Name of the rule group

            Returns:
                JSON string with rule group configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            rule_group = await connector.get_rule_group(folder_uid, group)
            return json.dumps(rule_group, indent=2)

        @self.mcp.tool()
        async def export_rule_group(
            connection_name: str, folder_uid: str, group: str
        ) -> str:
            """
            [ADMIN] Export a specific rule group in provisioning format.

            Args:
                connection_name: Name of the Grafana connection
                folder_uid: UID of the folder
                group: Name of the rule group

            Returns:
                JSON string with rule group in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_rule_group(folder_uid, group)
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def list_contact_points(connection_name: str) -> str:
            """
            [ADMIN] Get all contact points.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of contact point configurations.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            contact_points = await connector.list_contact_points()
            return json.dumps(contact_points, indent=2)

        @self.mcp.tool()
        async def export_contact_points(connection_name: str) -> str:
            """
            [ADMIN] Export all contact points in provisioning format.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with contact points in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_contact_points()
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def get_notification_policies(connection_name: str) -> str:
            """
            [ADMIN] Get the notification policy tree.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with notification policy tree configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            policies = await connector.get_notification_policies()
            return json.dumps(policies, indent=2)

        @self.mcp.tool()
        async def export_notification_policies(connection_name: str) -> str:
            """
            [ADMIN] Export notification policies in provisioning format.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with notification policies in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_notification_policies()
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def list_notification_templates(connection_name: str) -> str:
            """
            [ADMIN] Get all notification templates.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of notification template configurations.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            templates = await connector.list_notification_templates()
            return json.dumps(templates, indent=2)

        @self.mcp.tool()
        async def get_notification_template(connection_name: str, name: str) -> str:
            """
            [ADMIN] Get a specific notification template by name.

            Args:
                connection_name: Name of the Grafana connection
                name: Name of the template

            Returns:
                JSON string with notification template configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            template = await connector.get_notification_template(name)
            return json.dumps(template, indent=2)

        @self.mcp.tool()
        async def list_mute_timings(connection_name: str) -> str:
            """
            [ADMIN] Get all mute timings.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of mute timing configurations.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            mute_timings = await connector.list_mute_timings()
            return json.dumps(mute_timings, indent=2)

        @self.mcp.tool()
        async def get_mute_timing(connection_name: str, name: str) -> str:
            """
            [ADMIN] Get a specific mute timing by name.

            Args:
                connection_name: Name of the Grafana connection
                name: Name of the mute timing

            Returns:
                JSON string with mute timing configuration.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            mute_timing = await connector.get_mute_timing(name)
            return json.dumps(mute_timing, indent=2)

        @self.mcp.tool()
        async def export_all_mute_timings(connection_name: str) -> str:
            """
            [ADMIN] Export all mute timings in provisioning format.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with all mute timings in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_all_mute_timings()
            return json.dumps(exported, indent=2)

        @self.mcp.tool()
        async def export_mute_timing(connection_name: str, name: str) -> str:
            """
            [ADMIN] Export a specific mute timing in provisioning format.

            Args:
                connection_name: Name of the Grafana connection
                name: Name of the mute timing

            Returns:
                JSON string with mute timing in provisioning format.
            """
            if connection_name not in self.connectors:
                raise ValueError(
                    f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}"
                )

            connector = self.connectors[connection_name]
            exported = await connector.export_mute_timing(name)
            return json.dumps(exported, indent=2)

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
