"""Write-capable MCP tools.

This module provides tools that mutate Grafana resources.
These tools are only registered by the write-capable public command.

Includes:
- Provisioned alert rule management
- Contact point management
- Notification policy management
- Mute timing management
- Notification template management
- Folder creation
"""

import json
from collections.abc import Mapping
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

from ..grafana_connector import GrafanaConnector
from ..validation import get_connector


def register_admin_tools(
    mcp: FastMCP,
    connectors: Mapping[str, GrafanaConnector],
) -> None:
    """Register write-capable MCP tools.

    These tools are only registered by the write-capable public command.

    Args:
        mcp: FastMCP server instance
        connectors: Dictionary mapping connection names to GrafanaConnector instances
    """

    # =========================================================================
    # Provisioned Alert Rules (Read)
    # =========================================================================

    @mcp.tool()
    async def list_provisioned_alert_rules(connection_name: str) -> str:
        """
        [WRITE] Fetch all provisioned alert rules via the read-only provisioning API.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with the complete ProvisionedAlertRules payload.
        """
        connector = get_connector(connectors, connection_name)
        rules = await connector.list_provisioned_alert_rules()
        return json.dumps(rules, indent=2)

    @mcp.tool()
    async def get_provisioned_alert_rule(connection_name: str, alert_uid: str) -> str:
        """
        [WRITE] Get a specific alert rule by UID from the provisioning API.

        Args:
            connection_name: Name of the Grafana connection
            alert_uid: UID of the alert rule

        Returns:
            JSON string with alert rule configuration.
        """
        connector = get_connector(connectors, connection_name)
        rule = await connector.get_provisioned_alert_rule(alert_uid)
        return json.dumps(rule, indent=2)

    @mcp.tool()
    async def export_alert_rule(connection_name: str, alert_uid: str) -> str:
        """
        [WRITE] Export a specific alert rule in provisioning format.

        Args:
            connection_name: Name of the Grafana connection
            alert_uid: UID of the alert rule to export

        Returns:
            JSON string with alert rule in provisioning format.
        """
        connector = get_connector(connectors, connection_name)
        exported = await connector.export_alert_rule(alert_uid)
        return json.dumps(exported, indent=2)

    @mcp.tool()
    async def export_all_alert_rules(connection_name: str) -> str:
        """
        [WRITE] Export all alert rules in provisioning format.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with all alert rules in provisioning format.
        """
        connector = get_connector(connectors, connection_name)
        exported = await connector.export_all_alert_rules()
        return json.dumps(exported, indent=2)

    @mcp.tool()
    async def get_rule_group(connection_name: str, folder_uid: str, group: str) -> str:
        """
        [WRITE] Get a specific alert rule group.

        Args:
            connection_name: Name of the Grafana connection
            folder_uid: UID of the folder
            group: Name of the rule group

        Returns:
            JSON string with rule group configuration.
        """
        connector = get_connector(connectors, connection_name)
        rule_group = await connector.get_rule_group(folder_uid, group)
        return json.dumps(rule_group, indent=2)

    @mcp.tool()
    async def export_rule_group(
        connection_name: str, folder_uid: str, group: str
    ) -> str:
        """
        [WRITE] Export a specific rule group in provisioning format.

        Args:
            connection_name: Name of the Grafana connection
            folder_uid: UID of the folder
            group: Name of the rule group

        Returns:
            JSON string with rule group in provisioning format.
        """
        connector = get_connector(connectors, connection_name)
        exported = await connector.export_rule_group(folder_uid, group)
        return json.dumps(exported, indent=2)

    # =========================================================================
    # Contact Points
    # =========================================================================

    @mcp.tool()
    async def list_contact_points(connection_name: str) -> str:
        """
        [WRITE] Get all contact points.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with list of contact point configurations.
        """
        connector = get_connector(connectors, connection_name)
        contact_points = await connector.list_contact_points()
        return json.dumps(contact_points, indent=2)

    # =========================================================================
    # Notification Policies
    # =========================================================================

    @mcp.tool()
    async def get_notification_policies(connection_name: str) -> str:
        """
        [WRITE] Get the notification policy tree.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with notification policy tree configuration.
        """
        connector = get_connector(connectors, connection_name)
        policies = await connector.get_notification_policies()
        return json.dumps(policies, indent=2)

    # =========================================================================
    # Notification Templates
    # =========================================================================

    @mcp.tool()
    async def list_notification_templates(connection_name: str) -> str:
        """
        [WRITE] Get all notification templates.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with list of notification template configurations.
        """
        connector = get_connector(connectors, connection_name)
        templates = await connector.list_notification_templates()
        return json.dumps(templates, indent=2)

    @mcp.tool()
    async def get_notification_template(connection_name: str, name: str) -> str:
        """
        [WRITE] Get a specific notification template by name.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the template

        Returns:
            JSON string with notification template configuration.
        """
        connector = get_connector(connectors, connection_name)
        template = await connector.get_notification_template(name)
        return json.dumps(template, indent=2)

    # =========================================================================
    # Mute Timings
    # =========================================================================

    @mcp.tool()
    async def list_mute_timings(connection_name: str) -> str:
        """
        [WRITE] Get all mute timings.

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string with list of mute timing configurations.
        """
        connector = get_connector(connectors, connection_name)
        mute_timings = await connector.list_mute_timings()
        return json.dumps(mute_timings, indent=2)

    @mcp.tool()
    async def get_mute_timing(connection_name: str, name: str) -> str:
        """
        [WRITE] Get a specific mute timing by name.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the mute timing

        Returns:
            JSON string with mute timing configuration.
        """
        connector = get_connector(connectors, connection_name)
        mute_timing = await connector.get_mute_timing(name)
        return json.dumps(mute_timing, indent=2)

    # =========================================================================
    # Write Operations - Dashboards
    # =========================================================================

    @mcp.tool()
    async def save_dashboard(
        connection_name: str,
        dashboard: Dict[str, Any],
        folder_uid: Optional[str] = None,
        folder_id: Optional[int] = None,
        message: Optional[str] = None,
        overwrite: bool = False,
    ) -> str:
        """
        [WRITE] Create or update a dashboard from raw Grafana dashboard JSON.

        If the dashboard UID already exists, the tool fetches the live dashboard
        first and reuses its current id/version. Unless you explicitly pass
        `folder_uid` or `folder_id`, it also preserves the dashboard's current
        folder instead of moving it to the root level.

        Args:
            connection_name: Name of the Grafana connection
            dashboard: Raw Grafana dashboard model JSON (for example a repo dashboard file)
            folder_uid: Optional folder UID override for the save target
            folder_id: Optional folder ID override for the save target
            message: Optional dashboard version history message
            overwrite: Set true to overwrite an existing dashboard with the same UID

        Returns:
            JSON string with Grafana's save-dashboard response (id, uid, url, version, status).
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.save_dashboard(
            dashboard=dashboard,
            folder_uid=folder_uid,
            folder_id=folder_id,
            message=message,
            overwrite=overwrite,
        )
        return json.dumps(result, indent=2)

    # =========================================================================
    # Write Operations - Folders
    # =========================================================================

    @mcp.tool()
    async def create_folder(
        connection_name: str,
        title: str,
        uid: Optional[str] = None,
        parent_uid: Optional[str] = None,
    ) -> str:
        """
        [WRITE] Create a new folder in Grafana.

        Args:
            connection_name: Name of the Grafana connection
            title: The title of the folder
            uid: Optional unique identifier for the folder
            parent_uid: Optional parent folder UID (requires nested folders feature)

        Returns:
            JSON string with created folder details (uid, title, url, etc.).
        """
        connector = get_connector(connectors, connection_name)
        folder = await connector.create_folder(title, uid, parent_uid)
        return json.dumps(folder, indent=2)

    # =========================================================================
    # Write Operations - Alert Rules
    # =========================================================================

    @mcp.tool()
    async def create_alert_rule(connection_name: str, rule: Dict[str, Any]) -> str:
        """
        [WRITE] Create a new alert rule.

        Args:
            connection_name: Name of the Grafana connection
            rule: Alert rule configuration (requires: title, ruleGroup, folderUID,
                  condition, data, noDataState, execErrState)

        Returns:
            JSON string with the created alert rule (including UID).
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.create_alert_rule(rule)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def update_alert_rule(
        connection_name: str, alert_uid: str, rule: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Update an existing alert rule.

        Args:
            connection_name: Name of the Grafana connection
            alert_uid: UID of the alert rule to update
            rule: Updated alert rule configuration

        Returns:
            JSON string with the updated alert rule.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.update_alert_rule(alert_uid, rule)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def delete_alert_rule(connection_name: str, alert_uid: str) -> str:
        """
        [WRITE] Delete an alert rule.

        Args:
            connection_name: Name of the Grafana connection
            alert_uid: UID of the alert rule to delete

        Returns:
            JSON string confirming deletion.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.delete_alert_rule(alert_uid)
        return json.dumps({"status": "deleted", "uid": alert_uid, **result}, indent=2)

    @mcp.tool()
    async def update_rule_group(
        connection_name: str,
        folder_uid: str,
        group: str,
        config: Dict[str, Any],
    ) -> str:
        """
        [WRITE] Update a rule group's configuration (interval, rules).

        Args:
            connection_name: Name of the Grafana connection
            folder_uid: UID of the folder
            group: Name of the rule group
            config: Rule group configuration (folderUid, interval, rules, title)

        Returns:
            JSON string with the updated rule group.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.update_rule_group_interval(folder_uid, group, config)
        return json.dumps(result, indent=2)

    # =========================================================================
    # Write Operations - Contact Points
    # =========================================================================

    @mcp.tool()
    async def create_contact_point(
        connection_name: str, contact_point: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Create a new contact point.

        Args:
            connection_name: Name of the Grafana connection
            contact_point: Contact point configuration (requires: name, type, settings)

        Returns:
            JSON string with the created contact point (including UID).
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.create_contact_point(contact_point)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def update_contact_point(
        connection_name: str, uid: str, contact_point: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Update an existing contact point.

        Args:
            connection_name: Name of the Grafana connection
            uid: UID of the contact point to update
            contact_point: Updated contact point configuration

        Returns:
            JSON string with the updated contact point.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.update_contact_point(uid, contact_point)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def delete_contact_point(connection_name: str, uid: str) -> str:
        """
        [WRITE] Delete a contact point.

        Args:
            connection_name: Name of the Grafana connection
            uid: UID of the contact point to delete

        Returns:
            JSON string confirming deletion.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.delete_contact_point(uid)
        return json.dumps({"status": "deleted", "uid": uid, **result}, indent=2)

    # =========================================================================
    # Write Operations - Notification Policies
    # =========================================================================

    @mcp.tool()
    async def set_notification_policies(
        connection_name: str, policies: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Set the notification policy tree.

        Args:
            connection_name: Name of the Grafana connection
            policies: Notification policy tree configuration (Route object)

        Returns:
            JSON string with the updated notification policies.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.set_notification_policies(policies)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def delete_notification_policies(connection_name: str) -> str:
        """
        [WRITE] Clear the notification policy tree (reset to defaults).

        Args:
            connection_name: Name of the Grafana connection

        Returns:
            JSON string confirming deletion.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.delete_notification_policies()
        return json.dumps({"status": "deleted", **result}, indent=2)

    # =========================================================================
    # Write Operations - Mute Timings
    # =========================================================================

    @mcp.tool()
    async def create_mute_timing(
        connection_name: str, mute_timing: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Create a new mute timing.

        Args:
            connection_name: Name of the Grafana connection
            mute_timing: Mute timing configuration (requires: name, time_intervals)

        Returns:
            JSON string with the created mute timing.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.create_mute_timing(mute_timing)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def update_mute_timing(
        connection_name: str, name: str, mute_timing: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Update an existing mute timing.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the mute timing to update
            mute_timing: Updated mute timing configuration

        Returns:
            JSON string with the updated mute timing.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.update_mute_timing(name, mute_timing)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def delete_mute_timing(connection_name: str, name: str) -> str:
        """
        [WRITE] Delete a mute timing.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the mute timing to delete

        Returns:
            JSON string confirming deletion.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.delete_mute_timing(name)
        return json.dumps({"status": "deleted", "name": name, **result}, indent=2)

    # =========================================================================
    # Write Operations - Notification Templates
    # =========================================================================

    @mcp.tool()
    async def set_notification_template(
        connection_name: str, name: str, template: Dict[str, Any]
    ) -> str:
        """
        [WRITE] Create or update a notification template.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the template
            template: Template configuration (requires: template field with content)

        Returns:
            JSON string with the created/updated template.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.set_notification_template(name, template)
        return json.dumps(result, indent=2)

    @mcp.tool()
    async def delete_notification_template(connection_name: str, name: str) -> str:
        """
        [WRITE] Delete a notification template.

        Args:
            connection_name: Name of the Grafana connection
            name: Name of the template to delete

        Returns:
            JSON string confirming deletion.
        """
        connector = get_connector(connectors, connection_name)
        result = await connector.delete_notification_template(name)
        return json.dumps({"status": "deleted", "name": name, **result}, indent=2)
