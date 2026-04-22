"""Alert-related MCP tools.

This module provides tools for:
- Listing alert rules
- Getting alert rule details
- Ruler API access (non-admin)
- Alert state visibility and history
- Currently firing alerts
"""

import json
from collections.abc import Mapping
from typing import List, Optional

from mcp.server.fastmcp import FastMCP

from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


def register_alert_tools(
    mcp: FastMCP,
    connectors: Mapping[str, GrafanaConnector],
) -> None:
    """Register alert-related MCP tools.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
    """

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        alerts = await connector.list_alerts(folder_uid=folder_uid)
        return json.dumps(alerts, indent=2)

    @mcp.tool()
    async def get_alert_rule_by_uid(connection_name: str, alert_uid: str) -> str:
        """
        Get detailed information about a specific alert rule.

        Args:
            connection_name: Name of the Grafana connection
            alert_uid: UID of the alert rule

        Returns:
            JSON string with alert rule details.
        """
        connector = get_connector(connectors, connection_name)
        alert = await connector.get_alert_rule_by_uid(alert_uid)
        return json.dumps(alert, indent=2)

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        rules = await connector.get_ruler_rules()
        return json.dumps(rules, indent=2)

    @mcp.tool()
    async def get_ruler_namespace_rules(connection_name: str, namespace: str) -> str:
        """
        Get all rule groups for a specific namespace (folder).

        Args:
            connection_name: Name of the Grafana connection
            namespace: The namespace/folder name

        Returns:
            JSON string with dict mapping namespace to rule groups.
        """
        connector = get_connector(connectors, connection_name)
        rules = await connector.get_ruler_namespace_rules(namespace)
        return json.dumps(rules, indent=2)

    @mcp.tool()
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
        connector = get_connector(connectors, connection_name)
        group = await connector.get_ruler_group(namespace, group_name)
        return json.dumps(group, indent=2)

    @mcp.tool()
    async def get_alert_rules_with_state(
        connection_name: str,
        state: Optional[str] = None,
        rule_name: Optional[str] = None,
    ) -> str:
        """
        Get all alert rules with their current evaluation state.

        This endpoint returns rules organized by namespace with their current state
        (Normal, Pending, Alerting, NoData, Error). It's the same endpoint used by
        Grafana's Alert List panel - useful for checking if an alert is working after creation.

        Args:
            connection_name: Name of the Grafana connection
            state: Optional filter by state (e.g., "firing", "pending", "inactive")
            rule_name: Optional filter by rule name (partial match)

        Returns:
            JSON string with rules organized by namespace, each including state, health, and evaluation info.
        """
        connector = get_connector(connectors, connection_name)
        rules = await connector.get_prometheus_rules(state=state, rule_name=rule_name)
        return json.dumps(rules, indent=2)

    @mcp.tool()
    async def get_firing_alerts(
        connection_name: str,
        filter_labels: Optional[List[str]] = None,
        silenced: Optional[bool] = None,
        inhibited: Optional[bool] = None,
        active: Optional[bool] = None,
    ) -> str:
        """
        Get currently firing alert instances from Alertmanager.

        Returns alerts that have transitioned from Pending to Firing state.
        Use this to see which alerts are actively firing and their details.

        Args:
            connection_name: Name of the Grafana connection
            filter_labels: Optional label matchers (e.g., ["alertname=HighCPU", "severity=critical"])
            silenced: Include silenced alerts (default: true)
            inhibited: Include inhibited alerts (default: true)
            active: Include active alerts (default: true)

        Returns:
            JSON string with list of firing alert instances including labels, annotations, and startsAt.
        """
        connector = get_connector(connectors, connection_name)
        alerts = await connector.get_alertmanager_alerts(
            filter_labels=filter_labels,
            silenced=silenced,
            inhibited=inhibited,
            active=active,
        )
        return json.dumps(alerts, indent=2)

    @mcp.tool()
    async def get_alert_state_history(
        connection_name: str,
        rule_uid: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        from_time: Optional[str] = None,
        to_time: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        """
        Get alert state transition history.

        Returns the history of state changes for alert rules, including
        transitions between Normal, Pending, Alerting, NoData, and Error states.
        Useful for debugging alert behavior and understanding evaluation patterns.

        Args:
            connection_name: Name of the Grafana connection
            rule_uid: Optional filter by specific rule UID
            labels: Optional label matchers to filter history
            from_time: Start time (ISO 8601 or relative like "now-1h")
            to_time: End time (ISO 8601 or relative like "now")
            limit: Maximum number of history entries to return

        Returns:
            JSON string with state history entries including timestamps and state transitions.
        """
        connector = get_connector(connectors, connection_name)
        history = await connector.get_alert_state_history(
            rule_uid=rule_uid,
            labels=labels,
            from_time=from_time,
            to_time=to_time,
            limit=limit,
        )
        return json.dumps(history, indent=2)
