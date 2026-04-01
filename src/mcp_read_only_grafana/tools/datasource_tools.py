"""Datasource-related MCP tools.

This module provides tools for:
- Listing and checking datasource health
- Executing Prometheus (PromQL) queries
- Executing Loki (LogQL) queries
- Running Grafana Explore queries
"""

import json
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from ..exceptions import GrafanaAPIError
from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


async def _get_datasource_health_result(
    connector: GrafanaConnector,
    datasource_uid: str,
) -> Dict[str, Any]:
    """Return datasource health or a structured explanation for unsupported cases."""
    try:
        return await connector.get_datasource_health(datasource_uid)
    except GrafanaAPIError as exc:
        if exc.status_code != 404:
            raise

    try:
        datasources = await connector.list_datasources()
    except Exception:
        datasources = []

    datasource = next(
        (item for item in datasources if item.get("uid") == datasource_uid),
        None,
    )

    if datasource:
        return {
            "status": "unsupported",
            "supported": False,
            "reason": "health_endpoint_not_implemented",
            "datasource_uid": datasource_uid,
            "datasource_name": datasource.get("name"),
            "datasource_type": datasource.get("type"),
            "message": (
                "Grafana returned 404 for the datasource health endpoint. "
                "This usually means the datasource plugin does not implement "
                "/api/datasources/uid/:uid/health."
            ),
        }

    return {
        "status": "not_found",
        "supported": False,
        "reason": "datasource_uid_not_found",
        "datasource_uid": datasource_uid,
        "message": (
            "Grafana returned 404 for the datasource health endpoint and the "
            "datasource UID was not present in the datasource list."
        ),
    }


def register_datasource_tools(
    mcp: FastMCP,
    connectors: Dict[str, GrafanaConnector],
) -> None:
    """Register datasource-related MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
    """

    @mcp.tool()
    async def list_datasources(connection_name: str) -> str:
        """
        List all configured data sources in Grafana.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with list of data sources and their configuration.
        """
        connector = get_connector(connectors, connection_name)
        datasources = await connector.list_datasources()
        return json.dumps(datasources, indent=2)

    @mcp.tool()
    async def get_datasource_health(connection_name: str, datasource_uid: str) -> str:
        """
        Run the health check for a specific datasource.

        Args:
            connection_name: Name of the Grafana connection
            datasource_uid: UID of the datasource to probe

        Returns:
            JSON string with health information reported by Grafana.
            If Grafana returns 404, the tool returns a structured
            `unsupported` or `not_found` result instead of a raw error.
        """
        connector = get_connector(connectors, connection_name)
        health = await _get_datasource_health_result(connector, datasource_uid)
        return json.dumps(health, indent=2)

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        result = await connector.query_prometheus(
            datasource_uid, query, time_from, time_to, step
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        result = await connector.query_loki(
            datasource_uid, query, time_from, time_to, limit
        )
        return json.dumps(result, indent=2)

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        result = await connector.explore_query(
            queries=queries,
            range_from=range_from,
            range_to=range_to,
            max_data_points=max_data_points,
            interval_ms=interval_ms,
            additional_options=additional_options,
        )
        return json.dumps(result, indent=2)
