import httpx
import logging
from typing import List, Dict, Any, Optional, Iterable
from urllib.parse import unquote
from .config import GrafanaConnection

logger = logging.getLogger(__name__)


class GrafanaConnector:
    """Connector for read-only Grafana API access"""

    def __init__(self, connection: GrafanaConnection):
        self.connection = connection
        self.client = httpx.AsyncClient(
            base_url=str(connection.url),
            cookies={"grafana_session": connection.session_token},
            timeout=connection.timeout,
            verify=connection.verify_ssl,
            follow_redirects=True,
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    @staticmethod
    def _filter_fields(
        record: Dict[str, Any],
        requested_fields: Optional[Iterable[str]] = None,
        allowed_fields: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """
        Project a record to the requested subset of fields.

        Args:
            record: Input record
            requested_fields: Optional subset requested by the caller
            allowed_fields: Optional set of allowed keys; defaults to record keys

        Returns:
            Dict limited to the requested fields.
        """
        if not requested_fields:
            return record

        allowed_iterable = allowed_fields or record.keys()
        allowed = set(allowed_iterable)
        requested_list = list(requested_fields)
        invalid = [field for field in requested_list if field not in allowed]
        if invalid:
            raise ValueError(f"Unsupported field(s) requested: {', '.join(invalid)}")

        return {field: record[field] for field in requested_list if field in record}

    async def _get(self, endpoint: str, **params) -> Dict[str, Any]:
        """Execute a GET request to Grafana API"""
        # Reload session token from .env before each request
        session_token = self.connection.reload_session_token()
        self.client.cookies.set("grafana_session", session_token)

        try:
            response = await self.client.get(f"/api{endpoint}", params=params)
            response.raise_for_status()

            # Check for refreshed session cookie in response headers
            self._check_and_update_session_cookie(response)

            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception(
                    f"Authentication failed for {self.connection.connection_name}. Session may have expired."
                )
            elif e.response.status_code == 403:
                raise Exception(
                    f"Permission denied for {self.connection.connection_name}. User may lack read permissions."
                )
            else:
                raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.TimeoutException:
            raise Exception(
                f"Request timed out after {self.connection.timeout} seconds"
            )
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    async def _post(
        self, endpoint: str, json_payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a POST request to Grafana API"""
        session_token = self.connection.reload_session_token()
        self.client.cookies.set("grafana_session", session_token)

        try:
            response = await self.client.post(f"/api{endpoint}", json=json_payload)
            response.raise_for_status()

            # Check for refreshed session cookie in response headers
            self._check_and_update_session_cookie(response)

            if response.content:
                return response.json()
            return {}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise Exception(
                    f"Authentication failed for {self.connection.connection_name}. Session may have expired."
                )
            elif e.response.status_code == 403:
                raise Exception(
                    f"Permission denied for {self.connection.connection_name}. User may lack read permissions."
                )
            else:
                raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.TimeoutException:
            raise Exception(
                f"Request timed out after {self.connection.timeout} seconds"
            )
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")

    def _check_and_update_session_cookie(self, response: httpx.Response) -> None:
        """
        Check response headers for refreshed session cookie and update if found.
        Grafana rotates session tokens every 10 minutes via Set-Cookie headers.
        """
        # Look for Set-Cookie headers
        set_cookie_headers = response.headers.get_list("set-cookie")

        for cookie_header in set_cookie_headers:
            # Parse cookie header manually (simple parsing for grafana_session)
            if "grafana_session=" in cookie_header:
                # Extract cookie value (format: grafana_session=VALUE; Path=/; ...)
                parts = cookie_header.split(";")
                for part in parts:
                    part = part.strip()
                    if part.startswith("grafana_session="):
                        new_token = part.split("=", 1)[1]
                        # URL decode if needed
                        new_token = unquote(new_token)

                        # Only update if it's different from current token
                        if new_token != self.connection.session_token:
                            logger.info(
                                f"Session token rotated for {self.connection.connection_name}. "
                                f"Old: {self.connection.session_token[:16]}... "
                                f"New: {new_token[:16]}..."
                            )

                            # Update in memory and persist to .env
                            self.connection.update_session_token(
                                new_token, persist=True
                            )

                            # Update httpx client cookies
                            self.client.cookies.set("grafana_session", new_token)

                        break

    async def get_health(self) -> Dict[str, Any]:
        """Get Grafana instance health status"""
        health_data = await self._get("/health")
        # Also get version info
        try:
            settings = await self._get("/frontend/settings")
            health_data["version"] = settings.get("buildInfo", {}).get(
                "version", "unknown"
            )
        except Exception:
            health_data["version"] = "unknown"
        return health_data

    async def search_dashboards(
        self,
        query: Optional[str] = None,
        tag: Optional[str] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for dashboards by name or tag"""
        params = {"type": "dash-db"}
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag
        if limit is not None:
            params["limit"] = limit
        if page is not None:
            params["page"] = page

        results = await self._get("/search", **params)

        projected_results = []
        for dashboard in results:
            record = dict(dashboard)
            if fields:
                record = self._filter_fields(record, requested_fields=fields)
            projected_results.append(record)

        return projected_results

    async def get_dashboard(self, dashboard_uid: str) -> Dict[str, Any]:
        """Get full dashboard definition by UID"""
        result = await self._get(f"/dashboards/uid/{dashboard_uid}")

        # Extract relevant information
        dashboard = result.get("dashboard", {})
        meta = result.get("meta", {})

        return {
            "uid": dashboard.get("uid"),
            "title": dashboard.get("title"),
            "description": dashboard.get("description"),
            "tags": dashboard.get("tags", []),
            "timezone": dashboard.get("timezone"),
            "panels": dashboard.get("panels", []),
            "templating": dashboard.get("templating", {}),
            "annotations": dashboard.get("annotations", {}),
            "links": dashboard.get("links", []),
            "time": dashboard.get("time", {}),
            "refresh": dashboard.get("refresh"),
            "schema_version": dashboard.get("schemaVersion"),
            "version": dashboard.get("version"),
            "folder_id": meta.get("folderId"),
            "folder_title": meta.get("folderTitle"),
            "folder_uid": meta.get("folderUid"),
            "created": meta.get("created"),
            "created_by": meta.get("createdBy"),
            "updated": meta.get("updated"),
            "updated_by": meta.get("updatedBy"),
        }

    async def list_folders(self) -> List[Dict[str, Any]]:
        """List all folders in Grafana"""
        folders = await self._get("/folders")

        # Format folder information
        formatted_folders = []
        for folder in folders:
            formatted = {
                "uid": folder.get("uid"),
                "title": folder.get("title"),
                "id": folder.get("id"),
                "url": folder.get("url"),
                "can_admin": folder.get("canAdmin", False),
                "can_edit": folder.get("canEdit", False),
                "can_save": folder.get("canSave", False),
                "created": folder.get("created"),
                "updated": folder.get("updated"),
            }
            formatted_folders.append(formatted)

        return formatted_folders

    async def list_datasources(self) -> List[Dict[str, Any]]:
        """List all configured data sources"""
        datasources = await self._get("/datasources")

        # Format datasource information
        formatted_sources = []
        for ds in datasources:
            formatted = {
                "id": ds.get("id"),
                "uid": ds.get("uid"),
                "name": ds.get("name"),
                "type": ds.get("type"),
                "type_name": ds.get("typeName"),
                "url": ds.get("url", ""),
                "database": ds.get("database", ""),
                "is_default": ds.get("isDefault", False),
                "read_only": ds.get("readOnly", False),
            }
            formatted_sources.append(formatted)

        return formatted_sources

    async def get_datasource_health(self, datasource_uid: str) -> Dict[str, Any]:
        """Check the health of a specific datasource"""
        return await self._get(f"/datasources/uid/{datasource_uid}/health")

    async def list_alerts(
        self, folder_uid: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List alert rules, optionally filtered by folder"""
        # Get alert rules from the new unified alerting API
        try:
            rules = await self._get("/ruler/grafana/api/v1/rules")
        except Exception:
            # Fallback to legacy alerts if unified alerting is not available
            return await self._list_legacy_alerts()

        # Flatten the nested structure and filter by folder if specified
        formatted_alerts = []
        for namespace, groups in rules.items():
            if folder_uid and not namespace.startswith(folder_uid):
                continue

            for group in groups:
                for rule in group.get("rules", []):
                    formatted = {
                        "uid": rule.get("grafana_alert", {}).get("uid"),
                        "title": rule.get("grafana_alert", {}).get("title"),
                        "condition": rule.get("grafana_alert", {}).get("condition"),
                        "data": rule.get("grafana_alert", {}).get("data"),
                        "no_data_state": rule.get("grafana_alert", {}).get(
                            "noDataState"
                        ),
                        "exec_err_state": rule.get("grafana_alert", {}).get(
                            "execErrState"
                        ),
                        "folder": namespace,
                        "evaluation_group": group.get("name"),
                        "evaluation_interval": group.get("interval"),
                    }
                    formatted_alerts.append(formatted)

        return formatted_alerts

    async def _list_legacy_alerts(self) -> List[Dict[str, Any]]:
        """List legacy alert rules (for older Grafana versions)"""
        try:
            alerts = await self._get("/alerts")
            formatted_alerts = []
            for alert in alerts:
                formatted = {
                    "id": alert.get("id"),
                    "dashboard_id": alert.get("dashboardId"),
                    "panel_id": alert.get("panelId"),
                    "name": alert.get("name"),
                    "state": alert.get("state"),
                    "new_state_date": alert.get("newStateDate"),
                    "eval_data": alert.get("evalData"),
                    "dashboard_uid": alert.get("dashboardUid"),
                    "dashboard_slug": alert.get("dashboardSlug"),
                    "dashboard_title": alert.get("dashboardTitle"),
                    "panel_title": alert.get("panelTitle"),
                }
                formatted_alerts.append(formatted)
            return formatted_alerts
        except Exception:
            return []

    async def get_dashboard_info(self, dashboard_uid: str) -> Dict[str, Any]:
        """Get lightweight dashboard metadata without full panel definitions"""
        result = await self._get(f"/dashboards/uid/{dashboard_uid}")

        dashboard = result.get("dashboard", {})
        meta = result.get("meta", {})

        # Get minimal panel info (no queries, no full config)
        panels_minimal = []
        for panel in dashboard.get("panels", []):
            panels_minimal.append(
                {
                    "id": panel.get("id"),
                    "title": panel.get("title"),
                    "type": panel.get("type"),
                    "gridPos": panel.get("gridPos"),
                    "description": (
                        panel.get("description", "")[:100]
                        if panel.get("description")
                        else ""
                    ),  # Truncate long descriptions
                }
            )

        return {
            "uid": dashboard.get("uid"),
            "title": dashboard.get("title"),
            "description": dashboard.get("description"),
            "tags": dashboard.get("tags", []),
            "timezone": dashboard.get("timezone"),
            "version": dashboard.get("version"),
            "folder_id": meta.get("folderId"),
            "folder_title": meta.get("folderTitle"),
            "folder_uid": meta.get("folderUid"),
            "created": meta.get("created"),
            "created_by": meta.get("createdBy"),
            "updated": meta.get("updated"),
            "updated_by": meta.get("updatedBy"),
            "time": dashboard.get("time", {}),
            "refresh": dashboard.get("refresh"),
            "templating": dashboard.get("templating", {}),
            "annotations": dashboard.get("annotations", {}),
            "links": dashboard.get("links", []),
            "panels_summary": {
                "total_count": len(panels_minimal),
                "panels": panels_minimal,
            },
        }

    async def get_dashboard_panel(
        self, dashboard_uid: str, panel_id: int
    ) -> Dict[str, Any]:
        """Get full details for a single panel from a dashboard"""
        result = await self._get(f"/dashboards/uid/{dashboard_uid}")
        dashboard = result.get("dashboard", {})

        # Find the specific panel
        for panel in dashboard.get("panels", []):
            if panel.get("id") == panel_id:
                return panel

        raise Exception(
            f"Panel with id {panel_id} not found in dashboard {dashboard_uid}"
        )

    async def get_dashboard_panels(self, dashboard_uid: str) -> List[Dict[str, Any]]:
        """Get simplified panel information from a dashboard"""
        dashboard = await self.get_dashboard(dashboard_uid)
        panels = []

        for panel in dashboard.get("panels", []):
            simplified = {
                "id": panel.get("id"),
                "title": panel.get("title"),
                "type": panel.get("type"),
                "datasource": panel.get("datasource"),
                "targets": panel.get("targets", []),
                "grid_pos": panel.get("gridPos"),
                "description": panel.get("description"),
            }
            panels.append(simplified)

        return panels

    async def query_prometheus(
        self,
        datasource_uid: str,
        query: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        step: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a PromQL query against a Prometheus datasource"""
        # Build query parameters
        params = {
            "query": query,
        }

        # Add time range if specified
        if time_from:
            params["from"] = time_from
        if time_to:
            params["to"] = time_to
        if step:
            params["step"] = step

        # Use the proxy endpoint to query through Grafana
        endpoint = (
            f"/datasources/proxy/uid/{datasource_uid}/api/v1/query_range"
            if step
            else f"/datasources/proxy/uid/{datasource_uid}/api/v1/query"
        )

        result = await self._get(endpoint, **params)
        return result

    async def query_loki(
        self,
        datasource_uid: str,
        query: str,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> Dict[str, Any]:
        """Execute a LogQL query against a Loki datasource"""
        # Build query parameters
        params = {
            "query": query,
            "limit": limit,
        }

        # Add time range if specified (Loki uses nanoseconds)
        if time_from:
            params["start"] = time_from
        if time_to:
            params["end"] = time_to

        # Use the proxy endpoint to query through Grafana
        endpoint = f"/datasources/proxy/uid/{datasource_uid}/loki/api/v1/query_range"

        result = await self._get(endpoint, **params)
        return result

    async def explore_query(
        self,
        queries: List[Dict[str, Any]],
        range_from: Optional[str] = None,
        range_to: Optional[str] = None,
        max_data_points: Optional[int] = None,
        interval_ms: Optional[int] = None,
        additional_options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a Grafana Explore query via /api/ds/query"""
        if not queries:
            raise ValueError("queries must contain at least one query definition")

        payload: Dict[str, Any] = {
            "queries": queries,
        }

        if range_from is not None:
            payload["from"] = range_from
        if range_to is not None:
            payload["to"] = range_to
        if max_data_points is not None:
            payload["maxDataPoints"] = max_data_points
        if interval_ms is not None:
            payload["intervalMs"] = interval_ms

        if additional_options:
            # Avoid letting callers accidentally overwrite core keys
            for key, value in additional_options.items():
                if key in payload:
                    raise ValueError(
                        f"additional_options contains reserved key '{key}'"
                    )
                payload[key] = value

        return await self._post("/ds/query", json_payload=payload)

    async def get_current_org(self) -> Dict[str, Any]:
        """Get current organization information"""
        return await self._get("/org")

    async def list_users(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all users in the current organization"""
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page

        users = await self._get("/org/users", **params)

        formatted_users = []
        for user in users:
            record = dict(user)
            if fields:
                record = self._filter_fields(record, requested_fields=fields)
            formatted_users.append(record)

        return formatted_users

    async def list_teams(
        self,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all teams in the organization"""
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page

        result = await self._get("/teams/search", **params)
        teams = result.get("teams", [])

        formatted_teams = []
        for team in teams:
            record = dict(team)
            if fields:
                record = self._filter_fields(record, requested_fields=fields)
            formatted_teams.append(record)

        return formatted_teams

    async def get_alert_rule_by_uid(self, alert_uid: str) -> Dict[str, Any]:
        """Get detailed information about a specific alert rule"""
        result = await self._get(f"/ruler/grafana/api/v1/rules/{alert_uid}")
        return result

    # Ruler API endpoints (non-admin)
    async def get_ruler_rules(self) -> Dict[str, Any]:
        """
        Get all alert rules from the Ruler API.

        Returns a dict mapping namespace (folder) to list of rule groups.
        Each rule group contains rules and evaluation configuration.

        Returns:
            Dict mapping namespace to rule groups
        """
        return await self._get("/ruler/grafana/api/v1/rules")

    async def get_ruler_namespace_rules(self, namespace: str) -> Dict[str, Any]:
        """
        Get all rule groups for a specific namespace (folder).

        Args:
            namespace: The namespace/folder name

        Returns:
            Dict mapping namespace to list of rule groups
        """
        return await self._get(f"/ruler/grafana/api/v1/rules/{namespace}")

    async def get_ruler_group(self, namespace: str, group_name: str) -> Dict[str, Any]:
        """
        Get a specific alert rule group from a namespace.

        Args:
            namespace: The namespace/folder name
            group_name: The rule group name

        Returns:
            Rule group configuration with all rules
        """
        return await self._get(f"/ruler/grafana/api/v1/rules/{namespace}/{group_name}")

    async def list_provisioned_alert_rules(self) -> List[Dict[str, Any]]:
        """
        Fetch all alert rules from the provisioning API.

        Uses the documented read-only endpoint GET /api/v1/provisioning/alert-rules
        to return the ProvisionedAlertRules payload without any mutation.
        """
        return await self._get("/v1/provisioning/alert-rules")

    async def get_provisioned_alert_rule(self, alert_uid: str) -> Dict[str, Any]:
        """
        Get a specific alert rule by UID from the provisioning API.

        Args:
            alert_uid: UID of the alert rule

        Returns:
            Alert rule configuration
        """
        return await self._get(f"/v1/provisioning/alert-rules/{alert_uid}")

    async def export_alert_rule(self, alert_uid: str) -> Dict[str, Any]:
        """
        Export a specific alert rule in provisioning format.

        Args:
            alert_uid: UID of the alert rule to export

        Returns:
            Alert rule in provisioning YAML format
        """
        return await self._get(f"/v1/provisioning/alert-rules/{alert_uid}/export")

    async def export_all_alert_rules(self) -> Dict[str, Any]:
        """
        Export all alert rules in provisioning format.

        Returns:
            All alert rules in provisioning YAML format
        """
        return await self._get("/v1/provisioning/alert-rules/export")

    async def get_rule_group(self, folder_uid: str, group: str) -> Dict[str, Any]:
        """
        Get a specific alert rule group.

        Args:
            folder_uid: UID of the folder
            group: Name of the rule group

        Returns:
            Rule group configuration
        """
        return await self._get(
            f"/v1/provisioning/folder/{folder_uid}/rule-groups/{group}"
        )

    async def export_rule_group(self, folder_uid: str, group: str) -> Dict[str, Any]:
        """
        Export a specific rule group in provisioning format.

        Args:
            folder_uid: UID of the folder
            group: Name of the rule group

        Returns:
            Rule group in provisioning YAML format
        """
        return await self._get(
            f"/v1/provisioning/folder/{folder_uid}/rule-groups/{group}/export"
        )

    # Contact Points
    async def list_contact_points(self) -> List[Dict[str, Any]]:
        """
        Get all contact points.

        Returns:
            List of contact point configurations
        """
        return await self._get("/v1/provisioning/contact-points")

    async def export_contact_points(self) -> Dict[str, Any]:
        """
        Export all contact points in provisioning format.

        Returns:
            Contact points in provisioning YAML format
        """
        return await self._get("/v1/provisioning/contact-points/export")

    # Notification Policies
    async def get_notification_policies(self) -> Dict[str, Any]:
        """
        Get the notification policy tree.

        Returns:
            Notification policy tree configuration
        """
        return await self._get("/v1/provisioning/policies")

    async def export_notification_policies(self) -> Dict[str, Any]:
        """
        Export notification policies in provisioning format.

        Returns:
            Notification policies in provisioning YAML format
        """
        return await self._get("/v1/provisioning/policies/export")

    # Notification Templates
    async def list_notification_templates(self) -> List[Dict[str, Any]]:
        """
        Get all notification templates.

        Returns:
            List of notification template configurations
        """
        return await self._get("/v1/provisioning/templates")

    async def get_notification_template(self, name: str) -> Dict[str, Any]:
        """
        Get a specific notification template by name.

        Args:
            name: Name of the template

        Returns:
            Notification template configuration
        """
        return await self._get(f"/v1/provisioning/templates/{name}")

    # Mute Timings
    async def list_mute_timings(self) -> List[Dict[str, Any]]:
        """
        Get all mute timings.

        Returns:
            List of mute timing configurations
        """
        return await self._get("/v1/provisioning/mute-timings")

    async def get_mute_timing(self, name: str) -> Dict[str, Any]:
        """
        Get a specific mute timing by name.

        Args:
            name: Name of the mute timing

        Returns:
            Mute timing configuration
        """
        return await self._get(f"/v1/provisioning/mute-timings/{name}")

    async def export_all_mute_timings(self) -> Dict[str, Any]:
        """
        Export all mute timings in provisioning format.

        Returns:
            All mute timings in provisioning YAML format
        """
        return await self._get("/v1/provisioning/mute-timings/export")

    async def export_mute_timing(self, name: str) -> Dict[str, Any]:
        """
        Export a specific mute timing in provisioning format.

        Args:
            name: Name of the mute timing

        Returns:
            Mute timing in provisioning YAML format
        """
        return await self._get(f"/v1/provisioning/mute-timings/{name}/export")

    async def list_folder_dashboards(
        self,
        folder_uid: str,
        limit: Optional[int] = None,
        page: Optional[int] = None,
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List all dashboards in a specific folder"""
        params = {
            "type": "dash-db",
            "folderUids": folder_uid,
        }

        if limit is not None:
            params["limit"] = limit
        if page is not None:
            params["page"] = page

        results = await self._get("/search", **params)

        formatted_dashboards = []
        for dashboard in results:
            record = dict(dashboard)
            if fields:
                record = self._filter_fields(record, requested_fields=fields)
            formatted_dashboards.append(record)

        return formatted_dashboards

    async def list_annotations(
        self,
        time_from: Optional[str] = None,
        time_to: Optional[str] = None,
        dashboard_id: Optional[int] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """List annotations for a time range"""
        params = {}

        if time_from:
            params["from"] = time_from
        if time_to:
            params["to"] = time_to
        if dashboard_id:
            params["dashboardId"] = dashboard_id
        if tags:
            params["tags"] = tags

        annotations = await self._get("/annotations", **params)

        formatted_annotations = []
        for ann in annotations:
            formatted = {
                "id": ann.get("id"),
                "dashboard_id": ann.get("dashboardId"),
                "panel_id": ann.get("panelId"),
                "time": ann.get("time"),
                "time_end": ann.get("timeEnd"),
                "text": ann.get("text"),
                "tags": ann.get("tags", []),
                "created": ann.get("created"),
                "updated": ann.get("updated"),
            }
            formatted_annotations.append(formatted)

        return formatted_annotations

    async def get_dashboard_versions(self, dashboard_uid: str) -> List[Dict[str, Any]]:
        """Get version history of a dashboard"""
        versions = await self._get(f"/dashboards/uid/{dashboard_uid}/versions")

        formatted_versions = []
        for version in versions:
            formatted = {
                "id": version.get("id"),
                "version": version.get("version"),
                "created": version.get("created"),
                "created_by": version.get("createdBy"),
                "message": version.get("message"),
            }
            formatted_versions.append(formatted)

        return formatted_versions
