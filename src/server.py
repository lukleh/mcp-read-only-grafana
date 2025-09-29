#!/usr/bin/env python3
"""
MCP Read-Only Grafana Server
Provides secure read-only access to Grafana instances via MCP protocol.
"""

import logging
import sys
import json
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .config import ConfigParser, GrafanaConnection
from .grafana_connector import GrafanaConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReadOnlyGrafanaServer:
    """MCP Read-Only Grafana Server using FastMCP"""

    def __init__(self, config_path: str = "connections.yaml"):
        """Initialize the server with configuration"""
        self.config_path = config_path
        self.connections: Dict[str, GrafanaConnection] = {}
        self.connectors: Dict[str, GrafanaConnector] = {}

        # Initialize FastMCP server
        self.mcp = FastMCP("mcp-read-only-grafana")

        # Load connections
        self._load_connections()

        # Setup tools
        self._setup_tools()

    def _load_connections(self):
        """Load all connections from config file"""
        parser = ConfigParser(self.config_path)

        try:
            connections = parser.load_config()
        except FileNotFoundError:
            logger.warning(f"Configuration file not found: {self.config_path}")
            logger.info("Please create a connections.yaml file from connections.yaml.sample")
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            health = await connector.get_health()
            return json.dumps(health, indent=2)

        @self.mcp.tool()
        async def search_dashboards(
            connection_name: str,
            query: Optional[str] = None,
            tag: Optional[str] = None
        ) -> str:
            """
            Search for dashboards by name or tag.

            Args:
                connection_name: Name of the Grafana connection
                query: Optional search query for dashboard names
                tag: Optional tag to filter dashboards

            Returns:
                JSON string with list of matching dashboards.
            """
            if connection_name not in self.connectors:
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            dashboards = await connector.search_dashboards(query=query, tag=tag)
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            info = await connector.get_dashboard_info(dashboard_uid)
            return json.dumps(info, indent=2)

        @self.mcp.tool()
        async def get_dashboard_panel(connection_name: str, dashboard_uid: str, panel_id: int) -> str:
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            datasources = await connector.list_datasources()
            return json.dumps(datasources, indent=2)

        @self.mcp.tool()
        async def query_prometheus(
            connection_name: str,
            datasource_uid: str,
            query: str,
            time_from: Optional[str] = None,
            time_to: Optional[str] = None,
            step: Optional[str] = None
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            result = await connector.query_prometheus(datasource_uid, query, time_from, time_to, step)
            return json.dumps(result, indent=2)

        @self.mcp.tool()
        async def query_loki(
            connection_name: str,
            datasource_uid: str,
            query: str,
            time_from: Optional[str] = None,
            time_to: Optional[str] = None,
            limit: Optional[int] = 100
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            result = await connector.query_loki(datasource_uid, query, time_from, time_to, limit)
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            org = await connector.get_current_org()
            return json.dumps(org, indent=2)

        @self.mcp.tool()
        async def list_users(connection_name: str) -> str:
            """
            List all users in the current organization.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of users.
            """
            if connection_name not in self.connectors:
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            users = await connector.list_users()
            return json.dumps(users, indent=2)

        @self.mcp.tool()
        async def list_teams(connection_name: str) -> str:
            """
            List all teams in the organization.

            Args:
                connection_name: Name of the Grafana connection

            Returns:
                JSON string with list of teams.
            """
            if connection_name not in self.connectors:
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            teams = await connector.list_teams()
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            alert = await connector.get_alert_rule_by_uid(alert_uid)
            return json.dumps(alert, indent=2)

        @self.mcp.tool()
        async def list_folder_dashboards(connection_name: str, folder_uid: str) -> str:
            """
            List all dashboards in a specific folder.

            Args:
                connection_name: Name of the Grafana connection
                folder_uid: UID of the folder

            Returns:
                JSON string with list of dashboards in the folder.
            """
            if connection_name not in self.connectors:
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            dashboards = await connector.list_folder_dashboards(folder_uid)
            return json.dumps(dashboards, indent=2)

        @self.mcp.tool()
        async def list_annotations(
            connection_name: str,
            time_from: Optional[str] = None,
            time_to: Optional[str] = None,
            dashboard_id: Optional[int] = None,
            tags: Optional[List[str]] = None
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            annotations = await connector.list_annotations(time_from, time_to, dashboard_id, tags)
            return json.dumps(annotations, indent=2)

        @self.mcp.tool()
        async def get_dashboard_versions(connection_name: str, dashboard_uid: str) -> str:
            """
            Get version history of a dashboard.

            Args:
                connection_name: Name of the Grafana connection
                dashboard_uid: UID of the dashboard

            Returns:
                JSON string with list of dashboard versions.
            """
            if connection_name not in self.connectors:
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            versions = await connector.get_dashboard_versions(dashboard_uid)
            return json.dumps(versions, indent=2)

        @self.mcp.tool()
        async def list_alerts(
            connection_name: str,
            folder_uid: Optional[str] = None
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
                raise ValueError(f"Connection '{connection_name}' not found. Available connections: {', '.join(self.connectors.keys())}")

            connector = self.connectors[connection_name]
            alerts = await connector.list_alerts(folder_uid=folder_uid)
            return json.dumps(alerts, indent=2)

    async def cleanup(self):
        """Clean up resources"""
        for connector in self.connectors.values():
            await connector.close()

    def run(self):
        """Run the FastMCP server"""
        if not self.connections:
            logger.warning("No connections loaded. Server will run with limited functionality.")
        else:
            logger.info(f"Loaded {len(self.connections)} Grafana connection(s)")

        # Run the FastMCP server (defaults to stdio transport)
        self.mcp.run()


def main():
    """Main entry point for the MCP server"""
    # Get config file path from command line or use default
    config_path = sys.argv[1] if len(sys.argv) > 1 else "connections.yaml"

    # Create and run server
    server = ReadOnlyGrafanaServer(config_path)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()