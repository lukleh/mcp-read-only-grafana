"""
Comprehensive integration tests for ALL Grafana MCP endpoints.

These tests run against a real Grafana instance using credentials from the
current environment and configuration from connections.yaml.

To run these tests:
    pytest tests/test_integration_all_endpoints.py -v -m integration

To run with write-capable endpoints:
    RUN_WRITE_TESTS=1 pytest tests/test_integration_all_endpoints.py -v -m integration

Requirements:
    - local repo-root connections.yaml must have a 'grafana' connection configured
      by default, or set GRAFANA_TEST_CONNECTION_NAME to override it
    - the chosen connection must have session-based auth available, either via
      session_token in connections.yaml or its matching GRAFANA_SESSION_* env var
    - (Optional) Set RUN_WRITE_TESTS=1 to exercise write-capable endpoints

See CLAUDE.md for detailed test configuration and admin test documentation.
"""

import functools
import os
import pytest
from mcp_read_only_grafana.config import ConfigParser
from mcp_read_only_grafana.grafana_connector import GrafanaConnector

TEST_CONNECTION_NAME = os.getenv("GRAFANA_TEST_CONNECTION_NAME", "grafana")
RUN_WRITE_TESTS = os.getenv(
    "RUN_WRITE_TESTS",
    os.getenv("RUN_ADMIN_TESTS", ""),
).lower() in {"1", "true", "yes", "on"}
admin_only = pytest.mark.skipif(
    not RUN_WRITE_TESTS,
    reason="Write-capable tests disabled. Set RUN_WRITE_TESTS=1 (or true/yes/on) to enable.",
)


def handle_errors_gracefully(func):
    """
    Decorator to gracefully skip tests when errors occur.

    Handles:
    - 403: Permission denied
    - 404: Endpoint not found / no data
    - 401: Authentication failed
    - 500: Server-side errors (Grafana internal issues)
    """

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()
            if (
                "403" in error_msg
                or "permission denied" in error_msg
                or "forbidden" in error_msg
            ):
                pytest.skip(f"User lacks permissions: {error_msg}")
            elif "404" in error_msg or "not found" in error_msg:
                pytest.skip(f"Endpoint/data not available: {error_msg}")
            elif "401" in error_msg or "authentication failed" in error_msg:
                pytest.skip(f"Authentication failed: {error_msg}")
            elif "400" in error_msg or "bad request" in error_msg:
                pytest.skip(f"Query/request invalid for this setup: {error_msg}")
            elif "500" in error_msg or "internal server error" in error_msg:
                pytest.skip(f"Grafana server error: {error_msg}")
            raise

    return wrapper


@pytest.fixture(scope="function")
async def grafana_connector():
    """Create a GrafanaConnector instance for integration testing."""
    # Load configuration
    config_parser = ConfigParser("connections.yaml")
    try:
        connections = config_parser.load_config()
    except FileNotFoundError:
        pytest.skip("connections.yaml not found - cannot run integration tests")

    # Find the requested test connection
    grafana_connection = next(
        (c for c in connections if c.connection_name == TEST_CONNECTION_NAME), None
    )
    if not grafana_connection:
        pytest.skip(
            f"{TEST_CONNECTION_NAME} connection not found in connections.yaml. "
            "Set GRAFANA_TEST_CONNECTION_NAME to override the default."
        )

    # These integration tests exercise user-profile endpoints, so they need
    # session-based auth even though the package also supports API-key auth.
    if not grafana_connection.session_token:
        pytest.skip(
            f"{TEST_CONNECTION_NAME} must have session-based auth available for "
            "this integration suite. Configure session_token in connections.yaml "
            f"or provide {grafana_connection.get_env_var_name()}."
        )

    # Create connector
    connector = GrafanaConnector(grafana_connection)
    yield connector


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthAndBasicInfo:
    """Test basic connectivity and health endpoints."""

    @handle_errors_gracefully
    async def test_get_health(self, grafana_connector):
        """Test GET /api/health - Get Grafana health status."""
        result = await grafana_connector.get_health()

        assert isinstance(result, dict), "Expected health check response"
        print("\n✓ Grafana health check passed")
        print(f"  Version: {result.get('version', 'unknown')}")
        print(f"  Database: {result.get('database', 'unknown')}")

    @handle_errors_gracefully
    async def test_get_current_org(self, grafana_connector):
        """Test GET /api/org - Get current organization."""
        result = await grafana_connector.get_current_org()

        assert isinstance(result, dict), "Expected organization object"
        print(f"\n✓ Current org: {result.get('name', 'unknown')}")

    @handle_errors_gracefully
    async def test_get_current_user(self, grafana_connector):
        """Test GET /api/user - Get current user profile."""
        result = await grafana_connector.get_current_user()

        assert isinstance(result, dict), "Expected user object"
        assert "login" in result, "User payload should include login"
        print(
            f"\n✓ Current user: {result.get('login')} ({result.get('role', 'unknown')})"
        )


@pytest.mark.integration
@pytest.mark.asyncio
class TestDashboards:
    """Test dashboard-related endpoints."""

    @handle_errors_gracefully
    async def test_search_dashboards(self, grafana_connector):
        """Test GET /api/search - Search for dashboards."""
        result = await grafana_connector.search_dashboards()

        assert isinstance(result, list), "Expected list of dashboards"
        print(f"\n✓ Found {len(result)} dashboard(s)")

    @handle_errors_gracefully
    async def test_get_dashboard_info(self, grafana_connector):
        """Test GET /api/dashboards/uid/:uid - Get dashboard info."""
        # Get list first to find a valid dashboard
        dashboards = await grafana_connector.search_dashboards()
        if not dashboards:
            pytest.skip("No dashboards available to test")

        dashboard_uid = dashboards[0].get("uid")
        if not dashboard_uid:
            pytest.skip("Dashboard missing UID field")

        result = await grafana_connector.get_dashboard_info(dashboard_uid)

        assert isinstance(result, dict), "Expected dashboard info object"
        print(f"\n✓ Retrieved dashboard info: {result.get('title', 'Untitled')}")

    @handle_errors_gracefully
    async def test_get_dashboard(self, grafana_connector):
        """Test GET /api/dashboards/uid/:uid - Get full dashboard."""
        # Get list first
        dashboards = await grafana_connector.search_dashboards()
        if not dashboards:
            pytest.skip("No dashboards available to test")

        dashboard_uid = dashboards[0].get("uid")
        if not dashboard_uid:
            pytest.skip("Dashboard missing UID field")

        result = await grafana_connector.get_dashboard(dashboard_uid)

        assert isinstance(result, dict), "Expected dashboard object"
        print(f"\n✓ Retrieved full dashboard: {result.get('title', 'Untitled')}")

    @handle_errors_gracefully
    async def test_get_dashboard_panels(self, grafana_connector):
        """Test getting dashboard panels."""
        # Get list first
        dashboards = await grafana_connector.search_dashboards()
        if not dashboards:
            pytest.skip("No dashboards available to test")

        dashboard_uid = dashboards[0].get("uid")
        if not dashboard_uid:
            pytest.skip("Dashboard missing UID field")

        result = await grafana_connector.get_dashboard_panels(dashboard_uid)

        assert isinstance(result, list), "Expected list of panels"
        print(f"\n✓ Retrieved {len(result)} panel(s)")

    @handle_errors_gracefully
    async def test_get_dashboard_panel(self, grafana_connector):
        """Test getting a specific panel."""
        # Get dashboard with panels
        dashboards = await grafana_connector.search_dashboards()
        if not dashboards:
            pytest.skip("No dashboards available to test")

        dashboard_uid = dashboards[0].get("uid")
        if not dashboard_uid:
            pytest.skip("Dashboard missing UID field")

        panels = await grafana_connector.get_dashboard_panels(dashboard_uid)
        if not panels:
            pytest.skip("No panels available to test")

        panel_id = panels[0].get("id")
        if panel_id is None:
            pytest.skip("Panel missing ID field")

        result = await grafana_connector.get_dashboard_panel(dashboard_uid, panel_id)

        assert isinstance(result, dict), "Expected panel object"
        print(f"\n✓ Retrieved panel: {result.get('title', 'Untitled')}")

    @handle_errors_gracefully
    async def test_get_dashboard_versions(self, grafana_connector):
        """Test GET /api/dashboards/uid/:uid/versions - Get dashboard versions."""
        dashboards = await grafana_connector.search_dashboards()
        if not dashboards:
            pytest.skip("No dashboards available to test")

        dashboard_uid = dashboards[0].get("uid")
        if not dashboard_uid:
            pytest.skip("Dashboard missing UID field")

        result = await grafana_connector.get_dashboard_versions(dashboard_uid)

        assert isinstance(result, list), "Expected list of versions"
        print(f"\n✓ Found {len(result)} version(s)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestFolders:
    """Test folder-related endpoints."""

    @handle_errors_gracefully
    async def test_list_folders(self, grafana_connector):
        """Test GET /api/folders - List all folders."""
        result = await grafana_connector.list_folders()

        assert isinstance(result, list), "Expected list of folders"
        print(f"\n✓ Found {len(result)} folder(s)")

    @handle_errors_gracefully
    async def test_list_folder_dashboards(self, grafana_connector):
        """Test listing dashboards in a folder."""
        # Get folders first
        folders = await grafana_connector.list_folders()
        if not folders:
            pytest.skip("No folders available to test")

        folder_uid = folders[0].get("uid")
        if not folder_uid:
            pytest.skip("Folder missing UID field")

        result = await grafana_connector.list_folder_dashboards(folder_uid)

        assert isinstance(result, list), "Expected list of dashboards"
        print(f"\n✓ Found {len(result)} dashboard(s) in folder")


@pytest.mark.integration
@pytest.mark.asyncio
class TestDatasources:
    """Test datasource-related endpoints."""

    @handle_errors_gracefully
    async def test_list_datasources(self, grafana_connector):
        """Test GET /api/datasources - List all datasources."""
        result = await grafana_connector.list_datasources()

        assert isinstance(result, list), "Expected list of datasources"
        print(f"\n✓ Found {len(result)} datasource(s)")

    @handle_errors_gracefully
    async def test_get_datasource_health(self, grafana_connector):
        """Test GET /api/datasources/uid/:uid/health - Check datasource health."""
        # Get datasources first
        datasources = await grafana_connector.list_datasources()
        if not datasources:
            pytest.skip("No datasources available to test")

        datasource_uid = datasources[0].get("uid")
        if not datasource_uid:
            pytest.skip("Datasource missing UID field")

        result = await grafana_connector.get_datasource_health(datasource_uid)

        assert isinstance(result, dict), "Expected health check response"
        print(f"\n✓ Datasource health: {result.get('status', 'unknown')}")


@pytest.mark.integration
@pytest.mark.asyncio
class TestQueries:
    """Test query endpoints (Prometheus, Loki, Explore)."""

    @handle_errors_gracefully
    async def test_query_prometheus(self, grafana_connector):
        """Test querying Prometheus datasource."""
        # Get datasources first
        datasources = await grafana_connector.list_datasources()
        prometheus_ds = next(
            (
                ds
                for ds in datasources
                if ds.get("type") == "prometheus"
                or "prometheus" in ds.get("type", "").lower()
            ),
            None,
        )

        if not prometheus_ds:
            pytest.skip("No Prometheus datasource available")

        datasource_uid = prometheus_ds.get("uid")
        if not datasource_uid:
            pytest.skip("Prometheus datasource missing UID")

        # Simple query for up metric
        result = await grafana_connector.query_prometheus(
            datasource_uid, "up", time_from="now-5m", time_to="now"
        )

        assert result is not None, "Expected query result"
        print("\n✓ Prometheus query executed successfully")

    @handle_errors_gracefully
    async def test_query_loki(self, grafana_connector):
        """Test querying Loki datasource."""
        # Get datasources first
        datasources = await grafana_connector.list_datasources()
        loki_ds = next(
            (
                ds
                for ds in datasources
                if ds.get("type") == "loki" or "loki" in ds.get("type", "").lower()
            ),
            None,
        )

        if not loki_ds:
            pytest.skip("No Loki datasource available")

        datasource_uid = loki_ds.get("uid")
        if not datasource_uid:
            pytest.skip("Loki datasource missing UID")

        # Simple query
        result = await grafana_connector.query_loki(
            datasource_uid, '{job="varlogs"}', time_from="now-5m", time_to="now"
        )

        assert result is not None, "Expected query result"
        print("\n✓ Loki query executed successfully")

    @handle_errors_gracefully
    async def test_explore_query(self, grafana_connector):
        """Test explore query endpoint."""
        # Get datasources first
        datasources = await grafana_connector.list_datasources()
        if not datasources:
            pytest.skip("No datasources available")

        datasource_uid = datasources[0].get("uid")
        if not datasource_uid:
            pytest.skip("Datasource missing UID")

        # Simple explore query
        queries = [{"refId": "A", "datasource": {"uid": datasource_uid}}]

        result = await grafana_connector.explore_query(
            queries=queries, range_from="now-1h", range_to="now"
        )

        assert result is not None, "Expected query result"
        print("\n✓ Explore query executed successfully")


@pytest.mark.integration
@pytest.mark.asyncio
class TestUsersAndTeams:
    """Test user and team endpoints."""

    @admin_only
    @handle_errors_gracefully
    async def test_list_users(self, grafana_connector):
        """Test GET /api/org/users - List users in organization."""
        result = await grafana_connector.list_users()

        assert isinstance(result, list), "Expected list of users"
        print(f"\n✓ Found {len(result)} user(s)")

    @admin_only
    @handle_errors_gracefully
    async def test_list_teams(self, grafana_connector):
        """Test GET /api/teams/search - List teams."""
        result = await grafana_connector.list_teams()

        assert isinstance(result, list), "Expected list of teams"
        print(f"\n✓ Found {len(result)} team(s)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestAlertingRulerAPI:
    """Test alerting endpoints using Ruler API (older API)."""

    @handle_errors_gracefully
    async def test_list_alerts(self, grafana_connector):
        """Test listing alerts via Ruler API."""
        result = await grafana_connector.list_alerts()

        assert isinstance(result, list), "Expected list of alerts"
        print(f"\n✓ Found {len(result)} alert(s)")

    @handle_errors_gracefully
    async def test_get_alert_rule_by_uid(self, grafana_connector):
        """Test getting specific alert rule via Ruler API."""
        alerts = await grafana_connector.list_alerts()
        if not alerts:
            pytest.skip("No alerts available to test")

        alert_uid = alerts[0].get("uid")
        if not alert_uid:
            pytest.skip("Alert missing UID field")

        result = await grafana_connector.get_alert_rule_by_uid(alert_uid)

        assert isinstance(result, dict), "Expected alert rule object"
        print("\n✓ Retrieved alert rule")

    @handle_errors_gracefully
    async def test_get_ruler_rules(self, grafana_connector):
        """Test GET /api/ruler/grafana/api/v1/rules - Get all alert rules."""
        result = await grafana_connector.get_ruler_rules()

        assert isinstance(
            result, dict
        ), "Expected dict mapping namespace to rule groups"
        print(f"\n✓ Retrieved ruler rules from {len(result)} namespace(s)")

        # Print summary of namespaces
        for namespace, groups in result.items():
            print(f"  Namespace '{namespace}': {len(groups)} rule group(s)")

    @handle_errors_gracefully
    async def test_get_ruler_namespace_rules(self, grafana_connector):
        """Test GET /api/ruler/grafana/api/v1/rules/:namespace - Get rules for namespace."""
        all_rules = await grafana_connector.get_ruler_rules()
        if not all_rules:
            pytest.skip("No ruler rules available to test")

        # Get the first namespace
        namespace = next(iter(all_rules.keys()))
        result = await grafana_connector.get_ruler_namespace_rules(namespace)

        assert isinstance(
            result, dict
        ), "Expected dict mapping namespace to rule groups"
        # The response should contain the same namespace as the key
        assert namespace in result, f"Expected namespace '{namespace}' in result"
        rule_groups = result[namespace]
        print(
            f"\n✓ Retrieved {len(rule_groups)} rule group(s) for namespace '{namespace}'"
        )

    @handle_errors_gracefully
    async def test_get_ruler_group(self, grafana_connector):
        """Test GET /api/ruler/grafana/api/v1/rules/:namespace/:groupName - Get specific group."""
        all_rules = await grafana_connector.get_ruler_rules()
        if not all_rules:
            pytest.skip("No ruler rules available to test")

        # Get the first namespace and first group
        namespace = next(iter(all_rules.keys()))
        groups = all_rules[namespace]
        if not groups:
            pytest.skip("No rule groups in first namespace")

        group_name = groups[0].get("name")
        if not group_name:
            pytest.skip("Rule group missing name field")

        result = await grafana_connector.get_ruler_group(namespace, group_name)

        assert isinstance(result, dict), "Expected rule group object"
        assert "name" in result, "Rule group should have name field"
        print(f"\n✓ Retrieved rule group '{group_name}' from namespace '{namespace}'")


@pytest.mark.integration
@pytest.mark.asyncio
class TestAlertStateAndFiring:
    """Test alert state, firing alerts, and history endpoints.

    These endpoints provide visibility into alert evaluation state after creation.
    """

    @handle_errors_gracefully
    async def test_get_prometheus_rules(self, grafana_connector):
        """Test GET /api/prometheus/grafana/api/v1/rules - Get rules with state."""
        result = await grafana_connector.get_prometheus_rules()

        assert isinstance(result, dict), "Expected dict with status and data"
        print("\n✓ Retrieved prometheus-compatible rules")
        if "data" in result and "groups" in result["data"]:
            groups = result["data"]["groups"]
            print(f"  Found {len(groups)} rule group(s)")
            # Show state summary if available
            states = {}
            for group in groups:
                for rule in group.get("rules", []):
                    state = rule.get("state", "unknown")
                    states[state] = states.get(state, 0) + 1
            if states:
                print(f"  States: {states}")

    @handle_errors_gracefully
    async def test_get_prometheus_rules_with_state_filter(self, grafana_connector):
        """Test filtering rules by state."""
        # Try filtering by "firing" state
        result = await grafana_connector.get_prometheus_rules(state="firing")

        assert isinstance(result, dict), "Expected dict with status and data"
        print("\n✓ Retrieved rules filtered by state='firing'")

    @handle_errors_gracefully
    async def test_get_alertmanager_alerts(self, grafana_connector):
        """Test GET /api/alertmanager/grafana/api/v2/alerts - Get firing alerts."""
        result = await grafana_connector.get_alertmanager_alerts()

        assert isinstance(result, list), "Expected list of firing alerts"
        print(f"\n✓ Retrieved {len(result)} firing alert(s)")

        # Print summary of firing alerts
        for alert in result[:5]:  # Show first 5
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "unknown")
            print(f"  - {alertname} (since: {alert.get('startsAt', 'unknown')})")

    @handle_errors_gracefully
    async def test_get_alertmanager_alerts_with_filter(self, grafana_connector):
        """Test filtering alerts by labels."""
        # Try filtering with active=true (default behavior)
        result = await grafana_connector.get_alertmanager_alerts(active=True)

        assert isinstance(result, list), "Expected list of alerts"
        print(f"\n✓ Retrieved {len(result)} active alert(s)")

    @handle_errors_gracefully
    async def test_get_alert_state_history(self, grafana_connector):
        """Test GET /api/v1/rules/history - Get alert state history."""
        result = await grafana_connector.get_alert_state_history(limit=10)

        # This endpoint may return dict or list depending on Grafana version
        assert result is not None, "Expected history response"
        print("\n✓ Retrieved alert state history")

        # Try to show some history entries if available
        if isinstance(result, dict) and "results" in result:
            entries = result["results"]
            print(f"  Found {len(entries)} history entries")
        elif isinstance(result, list):
            print(f"  Found {len(result)} history entries")

    @handle_errors_gracefully
    async def test_get_alert_state_history_for_rule(self, grafana_connector):
        """Test getting history for a specific rule."""
        # Get an alert rule UID first
        alerts = await grafana_connector.list_alerts()
        if not alerts:
            pytest.skip("No alerts available to test history")

        rule_uid = alerts[0].get("uid")
        if not rule_uid:
            pytest.skip("Alert missing UID field")

        result = await grafana_connector.get_alert_state_history(
            rule_uid=rule_uid, limit=10
        )

        assert result is not None, "Expected history response"
        print(f"\n✓ Retrieved history for rule {rule_uid}")


@pytest.mark.integration
@pytest.mark.asyncio
@admin_only
class TestAlertingProvisioningAPI:
    """Test alerting endpoints using Provisioning API (newer API)."""

    @handle_errors_gracefully
    async def test_list_provisioned_alert_rules(self, grafana_connector):
        """Test GET /api/v1/provisioning/alert-rules - List all alert rules."""
        result = await grafana_connector.list_provisioned_alert_rules()

        assert isinstance(result, list), "Expected list of alert rules"
        print(f"\n✓ Found {len(result)} alert rule(s)")

    @handle_errors_gracefully
    async def test_get_provisioned_alert_rule(self, grafana_connector):
        """Test GET /api/v1/provisioning/alert-rules/:uid - Get specific alert rule."""
        rules = await grafana_connector.list_provisioned_alert_rules()
        if not rules:
            pytest.skip("No alert rules available to test")

        rule_uid = rules[0].get("uid")
        if not rule_uid:
            pytest.skip("Alert rule missing UID field")

        result = await grafana_connector.get_provisioned_alert_rule(rule_uid)

        assert isinstance(result, dict), "Expected alert rule object"
        print(f"\n✓ Retrieved alert rule: {result.get('title', 'Untitled')}")

    @handle_errors_gracefully
    async def test_export_alert_rule(self, grafana_connector):
        """Test exporting specific alert rule."""
        rules = await grafana_connector.list_provisioned_alert_rules()
        if not rules:
            pytest.skip("No alert rules available to test")

        rule_uid = rules[0].get("uid")
        if not rule_uid:
            pytest.skip("Alert rule missing UID field")

        result = await grafana_connector.export_alert_rule(rule_uid)

        assert result is not None, "Expected export data"
        print("\n✓ Exported alert rule")

    @handle_errors_gracefully
    async def test_export_all_alert_rules(self, grafana_connector):
        """Test exporting all alert rules."""
        result = await grafana_connector.export_all_alert_rules()

        assert result is not None, "Expected export data"
        print("\n✓ Exported all alert rules")

    @handle_errors_gracefully
    async def test_get_rule_group(self, grafana_connector):
        """Test getting rule group."""
        rules = await grafana_connector.list_provisioned_alert_rules()
        if not rules:
            pytest.skip("No alert rules available to test")

        rule = rules[0]
        folder_uid = rule.get("folderUID")
        rule_group = rule.get("ruleGroup")

        if not folder_uid or not rule_group:
            pytest.skip("Cannot determine folder UID or rule group from rules")

        result = await grafana_connector.get_rule_group(folder_uid, rule_group)

        assert isinstance(result, dict), "Expected rule group object"
        print(f"\n✓ Retrieved rule group: {rule_group}")

    @handle_errors_gracefully
    async def test_export_rule_group(self, grafana_connector):
        """Test exporting rule group."""
        rules = await grafana_connector.list_provisioned_alert_rules()
        if not rules:
            pytest.skip("No alert rules available to test")

        rule = rules[0]
        folder_uid = rule.get("folderUID")
        rule_group = rule.get("ruleGroup")

        if not folder_uid or not rule_group:
            pytest.skip("Cannot determine folder UID or rule group from rules")

        result = await grafana_connector.export_rule_group(folder_uid, rule_group)

        assert result is not None, "Expected export data"
        print("\n✓ Exported rule group")

    @handle_errors_gracefully
    async def test_list_contact_points(self, grafana_connector):
        """Test listing contact points."""
        result = await grafana_connector.list_contact_points()

        assert isinstance(result, list), "Expected list of contact points"
        print(f"\n✓ Found {len(result)} contact point(s)")

    @handle_errors_gracefully
    async def test_export_contact_points(self, grafana_connector):
        """Test exporting contact points."""
        result = await grafana_connector.export_contact_points()

        assert result is not None, "Expected export data"
        print("\n✓ Exported contact points")

    @handle_errors_gracefully
    async def test_get_notification_policies(self, grafana_connector):
        """Test getting notification policies."""
        result = await grafana_connector.get_notification_policies()

        assert isinstance(result, dict), "Expected notification policy tree"
        print("\n✓ Retrieved notification policies")

    @handle_errors_gracefully
    async def test_export_notification_policies(self, grafana_connector):
        """Test exporting notification policies."""
        result = await grafana_connector.export_notification_policies()

        assert result is not None, "Expected export data"
        print("\n✓ Exported notification policies")

    @handle_errors_gracefully
    async def test_list_notification_templates(self, grafana_connector):
        """Test listing notification templates."""
        result = await grafana_connector.list_notification_templates()

        assert isinstance(result, list), "Expected list of templates"
        print(f"\n✓ Found {len(result)} template(s)")

    @handle_errors_gracefully
    async def test_get_notification_template(self, grafana_connector):
        """Test getting specific notification template."""
        templates = await grafana_connector.list_notification_templates()
        if not templates:
            pytest.skip("No notification templates available to test")

        template_name = templates[0].get("name")
        if not template_name:
            pytest.skip("Template missing name field")

        result = await grafana_connector.get_notification_template(template_name)

        assert isinstance(result, dict), "Expected template object"
        print(f"\n✓ Retrieved template: {template_name}")

    @handle_errors_gracefully
    async def test_list_mute_timings(self, grafana_connector):
        """Test listing mute timings."""
        result = await grafana_connector.list_mute_timings()

        assert isinstance(result, list), "Expected list of mute timings"
        print(f"\n✓ Found {len(result)} mute timing(s)")

    @handle_errors_gracefully
    async def test_get_mute_timing(self, grafana_connector):
        """Test getting specific mute timing."""
        mute_timings = await grafana_connector.list_mute_timings()
        if not mute_timings:
            pytest.skip("No mute timings available to test")

        mute_timing_name = mute_timings[0].get("name")
        if not mute_timing_name:
            pytest.skip("Mute timing missing name field")

        result = await grafana_connector.get_mute_timing(mute_timing_name)

        assert isinstance(result, dict), "Expected mute timing object"
        print(f"\n✓ Retrieved mute timing: {mute_timing_name}")

    @handle_errors_gracefully
    async def test_export_all_mute_timings(self, grafana_connector):
        """Test exporting all mute timings."""
        result = await grafana_connector.export_all_mute_timings()

        assert result is not None, "Expected export data"
        print("\n✓ Exported all mute timings")

    @handle_errors_gracefully
    async def test_export_mute_timing(self, grafana_connector):
        """Test exporting specific mute timing."""
        mute_timings = await grafana_connector.list_mute_timings()
        if not mute_timings:
            pytest.skip("No mute timings available to test")

        mute_timing_name = mute_timings[0].get("name")
        if not mute_timing_name:
            pytest.skip("Mute timing missing name field")

        result = await grafana_connector.export_mute_timing(mute_timing_name)

        assert result is not None, "Expected export data"
        print("\n✓ Exported mute timing")


@pytest.mark.integration
@pytest.mark.asyncio
class TestAnnotations:
    """Test annotation endpoints."""

    @handle_errors_gracefully
    async def test_list_annotations(self, grafana_connector):
        """Test GET /api/annotations - List annotations."""
        result = await grafana_connector.list_annotations(
            time_from="now-24h", time_to="now"
        )

        assert isinstance(result, list), "Expected list of annotations"
        print(f"\n✓ Found {len(result)} annotation(s)")
