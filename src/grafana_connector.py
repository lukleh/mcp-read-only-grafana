import httpx
import logging
from typing import Any, Dict, Iterable, NoReturn
from urllib.parse import unquote
from .config import GrafanaConnection
from .exceptions import (
    AuthenticationError,
    GrafanaAPIError,
    GrafanaTimeoutError,
    PermissionDeniedError,
)

logger = logging.getLogger(__name__)

SEARCH_DASHBOARD_FIELDS = {
    "id",
    "orgId",
    "uid",
    "title",
    "uri",
    "url",
    "slug",
    "type",
    "tags",
    "isStarred",
    "folderId",
    "folderTitle",
    "folderUid",
    "folderUrl",
    "sortMeta",
}

USER_FIELDS = {
    "orgId",
    "userId",
    "avatarUrl",
    "email",
    "name",
    "login",
    "role",
    "lastSeenAt",
    "lastSeenAtAge",
    "authLabels",
}

TEAM_FIELDS = {
    "id",
    "orgId",
    "uid",
    "name",
    "avatarUrl",
    "email",
    "memberCount",
}


class GrafanaConnector:
    """Async client for Grafana API.

    Authentication:
        Supports two authentication methods:
        - API key (Bearer token): Set GRAFANA_API_KEY_<CONNECTION_NAME>
        - Session cookie: Set GRAFANA_SESSION_<CONNECTION_NAME>

        If both are configured, API key takes precedence.

    Credentials are reloaded from the environment and cached session state before
    each request to support token rotation without server restart.
    """

    def __init__(self, connection: GrafanaConnection):
        self.connection = connection
        headers = {}
        cookies = None

        if connection.api_key:
            headers["Authorization"] = f"Bearer {connection.api_key}"
        elif connection.session_token:
            cookies = {"grafana_session": connection.session_token}

        self.client = httpx.AsyncClient(
            base_url=str(connection.url),
            headers=headers or None,
            cookies=cookies,
            timeout=connection.timeout,
            verify=connection.verify_ssl,
            follow_redirects=True,
        )

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

    @staticmethod
    def _validate_requested_fields(
        records: Iterable[Dict[str, Any]],
        requested_fields: Iterable[str] | None = None,
        allowed_fields: Iterable[str] | None = None,
    ) -> None:
        """
        Validate requested projection fields against the overall response shape.

        Args:
            records: Response records to inspect
            requested_fields: Optional subset requested by the caller
            allowed_fields: Optional baseline set of known sparse keys that may
                be valid even when they are absent from the current response page
        """
        if not requested_fields:
            return

        allowed = set()
        if allowed_fields:
            allowed.update(allowed_fields)
        for record in records:
            allowed.update(record.keys())

        requested_list = list(requested_fields)
        invalid = [field for field in requested_list if field not in allowed]
        if invalid:
            raise ValueError(f"Unsupported field(s) requested: {', '.join(invalid)}")

    @staticmethod
    def _filter_fields(
        record: Dict[str, Any],
        requested_fields: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """
        Project a record to the requested subset of fields.

        Args:
            record: Input record
            requested_fields: Optional subset requested by the caller

        Returns:
            Dict limited to the requested fields.
        """
        if not requested_fields:
            return record

        requested_list = list(requested_fields)
        return {field: record[field] for field in requested_list if field in record}

    def _refresh_credentials(self) -> None:
        """Refresh credentials from the environment and cached session state.

        Reloads either API key or session token depending on which auth
        method is configured. API key takes precedence if both are set.
        """
        if self.connection.api_key:
            api_key = self.connection.reload_api_key()
            self.client.headers["Authorization"] = f"Bearer {api_key}"
        else:
            session_token = self.connection.reload_session_token()
            self.client.cookies.set("grafana_session", session_token)

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Process a successful response: check cookie refresh, parse JSON.

        Args:
            response: The httpx response object

        Returns:
            Parsed JSON response, or empty dict if no content
        """
        self._check_and_update_session_cookie(response)
        if response.content:
            return response.json()
        return {}

    def _handle_http_error(self, e: httpx.HTTPStatusError, operation: str) -> NoReturn:
        """Convert HTTP errors to appropriate custom exceptions.

        This method always raises an exception and never returns normally.

        Args:
            e: The httpx HTTPStatusError
            operation: Description of the operation (e.g., "read", "write", "delete")

        Raises:
            AuthenticationError: For 401 responses
            PermissionDeniedError: For 403 responses
            GrafanaAPIError: For other HTTP errors
        """
        if e.response.status_code == 401:
            raise AuthenticationError(self.connection.connection_name)
        elif e.response.status_code == 403:
            raise PermissionDeniedError(self.connection.connection_name, operation)
        else:
            raise GrafanaAPIError(
                e.response.status_code,
                e.response.text,
                self.connection.connection_name,
            )

    async def _get(self, endpoint: str, **params) -> Dict[str, Any]:
        """Execute a GET request to Grafana API."""
        self._refresh_credentials()
        try:
            response = await self.client.get(f"/api{endpoint}", params=params)
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "read")
        except httpx.TimeoutException:
            raise GrafanaTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )

    async def _post(
        self, endpoint: str, json_payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute a POST request to Grafana API."""
        self._refresh_credentials()
        try:
            response = await self.client.post(f"/api{endpoint}", json=json_payload)
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "write")
        except httpx.TimeoutException:
            raise GrafanaTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )

    async def _put(
        self, endpoint: str, json_payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """Execute a PUT request to Grafana API."""
        self._refresh_credentials()
        try:
            response = await self.client.put(f"/api{endpoint}", json=json_payload)
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "write")
        except httpx.TimeoutException:
            raise GrafanaTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )

    async def _delete(self, endpoint: str) -> Dict[str, Any]:
        """Execute a DELETE request to Grafana API."""
        self._refresh_credentials()
        try:
            response = await self.client.delete(f"/api{endpoint}")
            response.raise_for_status()
            return self._handle_response(response)
        except httpx.HTTPStatusError as e:
            self._handle_http_error(e, "delete")
        except httpx.TimeoutException:
            raise GrafanaTimeoutError(
                self.connection.timeout, self.connection.connection_name
            )

    def _check_and_update_session_cookie(self, response: httpx.Response) -> None:
        """
        Check response headers for refreshed session cookie and update if found.
        Grafana rotates session tokens every 10 minutes via Set-Cookie headers.
        """
        # Skip if using API key authentication
        if not self.connection.session_token:
            return

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

                            # Update in memory and persist to cached state
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
        query: str | None = None,
        tag: str | None = None,
        limit: int | None = None,
        page: int | None = None,
        fields: list[str] | None = None,
    ) -> list[Dict[str, Any]]:
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
        records = [dict(dashboard) for dashboard in results]

        if fields:
            self._validate_requested_fields(records, fields, SEARCH_DASHBOARD_FIELDS)
            return [self._filter_fields(record, fields) for record in records]

        return records

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

    async def list_folders(self) -> list[Dict[str, Any]]:
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

    async def create_folder(
        self, title: str, uid: str | None = None, parent_uid: str | None = None
    ) -> Dict[str, Any]:
        """
        Create a new folder in Grafana.

        Args:
            title: The title of the folder
            uid: Optional unique identifier for the folder
            parent_uid: Optional parent folder UID (requires nested folders feature)

        Returns:
            Dict with created folder details (uid, title, url, etc.)
        """
        payload: Dict[str, Any] = {"title": title}
        if uid:
            payload["uid"] = uid
        if parent_uid:
            payload["parentUid"] = parent_uid

        return await self._post("/folders", json_payload=payload)

    async def list_datasources(self) -> list[Dict[str, Any]]:
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
        self, folder_uid: str | None = None
    ) -> list[Dict[str, Any]]:
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

    async def _list_legacy_alerts(self) -> list[Dict[str, Any]]:
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

    async def get_dashboard_panels(self, dashboard_uid: str) -> list[Dict[str, Any]]:
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
        time_from: str | None = None,
        time_to: str | None = None,
        step: str | None = None,
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
        time_from: str | None = None,
        time_to: str | None = None,
        limit: int | None = 100,
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
        queries: list[Dict[str, Any]],
        range_from: str | None = None,
        range_to: str | None = None,
        max_data_points: int | None = None,
        interval_ms: int | None = None,
        additional_options: Dict[str, Any] | None = None,
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

    async def get_current_user(self) -> Dict[str, Any]:
        """Get the currently authenticated user profile"""
        return await self._get("/user")

    async def get_user_permissions(self) -> Dict[str, Any]:
        """
        Get the current user's permissions.

        Lists the permissions granted to the signed-in user. Returns a map of
        actions to their authorized scopes.

        Note: Requires Grafana 8.0+ with RBAC enabled. May return 404 on older
        versions or instances without fine-grained access control.

        Returns:
            Dict mapping action names to list of authorized scopes.
        """
        return await self._get("/access-control/user/permissions")

    async def list_users(
        self,
        page: int | None = None,
        per_page: int | None = None,
        fields: list[str] | None = None,
    ) -> list[Dict[str, Any]]:
        """List all users in the current organization"""
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page

        users = await self._get("/org/users", **params)
        records = [dict(user) for user in users]

        if fields:
            self._validate_requested_fields(records, fields, USER_FIELDS)
            return [self._filter_fields(record, fields) for record in records]

        return records

    async def list_teams(
        self,
        page: int | None = None,
        per_page: int | None = None,
        fields: list[str] | None = None,
    ) -> list[Dict[str, Any]]:
        """List all teams in the organization"""
        params: Dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["perpage"] = per_page

        result = await self._get("/teams/search", **params)
        teams = result.get("teams", [])
        records = [dict(team) for team in teams]

        if fields:
            self._validate_requested_fields(records, fields, TEAM_FIELDS)
            return [self._filter_fields(record, fields) for record in records]

        return records

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

    # Prometheus-compatible alerting endpoints (for alert state visibility)
    async def get_prometheus_rules(
        self,
        state: str | None = None,
        rule_name: str | None = None,
    ) -> Dict[str, Any]:
        """
        Get all alert rules with their current evaluation state.

        This endpoint returns rules organized by namespace with their current state
        (Normal, Pending, Alerting, NoData, Error). It's the same endpoint used by
        Grafana's Alert List panel.

        Args:
            state: Optional filter by state (e.g., "firing", "pending", "inactive")
            rule_name: Optional filter by rule name (partial match)

        Returns:
            Dict with 'status' and 'data' containing groups organized by namespace,
            each rule including its current state, health, and evaluation info.
        """
        params: Dict[str, Any] = {}
        if state:
            params["state"] = state
        if rule_name:
            params["rule_name"] = rule_name

        return await self._get("/prometheus/grafana/api/v1/rules", **params)

    async def get_alertmanager_alerts(
        self,
        filter_labels: list[str] | None = None,
        silenced: bool | None = None,
        inhibited: bool | None = None,
        active: bool | None = None,
    ) -> list[Dict[str, Any]]:
        """
        Get currently firing alert instances from Alertmanager.

        Returns alerts that have transitioned from Pending to Firing state.
        These are the actual alert instances with their labels and annotations.

        Args:
            filter_labels: Optional label matchers (e.g., ["alertname=HighCPU", "severity=critical"])
            silenced: Include silenced alerts (default: true)
            inhibited: Include inhibited alerts (default: true)
            active: Include active alerts (default: true)

        Returns:
            List of firing alert instances with labels, annotations, startsAt, etc.
        """
        params: Dict[str, Any] = {}
        if filter_labels:
            params["filter"] = filter_labels
        if silenced is not None:
            params["silenced"] = str(silenced).lower()
        if inhibited is not None:
            params["inhibited"] = str(inhibited).lower()
        if active is not None:
            params["active"] = str(active).lower()

        return await self._get("/alertmanager/grafana/api/v2/alerts", **params)

    async def get_alert_state_history(
        self,
        rule_uid: str | None = None,
        labels: Dict[str, str] | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        limit: int | None = None,
    ) -> Dict[str, Any]:
        """
        Get alert state transition history.

        Returns the history of state changes for alert rules, including
        transitions between Normal, Pending, Alerting, NoData, and Error states.

        Args:
            rule_uid: Optional filter by specific rule UID
            labels: Optional label matchers to filter history
            from_time: Start time (ISO 8601 or relative like "now-1h")
            to_time: End time (ISO 8601 or relative like "now")
            limit: Maximum number of history entries to return

        Returns:
            Dict containing state history entries with timestamps and state transitions.
        """
        params: Dict[str, Any] = {}
        if rule_uid:
            params["ruleUID"] = rule_uid
        if labels:
            # Convert labels dict to query format
            for key, value in labels.items():
                params[f"labels[{key}]"] = value
        if from_time:
            params["from"] = from_time
        if to_time:
            params["to"] = to_time
        if limit is not None:
            params["limit"] = limit

        return await self._get("/v1/rules/history", **params)

    async def list_provisioned_alert_rules(self) -> list[Dict[str, Any]]:
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

    # Alert Rule Write Operations
    async def create_alert_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new alert rule.

        Args:
            rule: Alert rule configuration (requires: title, ruleGroup, folderUID,
                  condition, data, noDataState, execErrState)

        Returns:
            Created alert rule with UID
        """
        return await self._post("/v1/provisioning/alert-rules", json_payload=rule)

    async def update_alert_rule(
        self, alert_uid: str, rule: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing alert rule.

        Args:
            alert_uid: UID of the alert rule to update
            rule: Updated alert rule configuration

        Returns:
            Updated alert rule
        """
        return await self._put(
            f"/v1/provisioning/alert-rules/{alert_uid}", json_payload=rule
        )

    async def delete_alert_rule(self, alert_uid: str) -> Dict[str, Any]:
        """
        Delete an alert rule.

        Args:
            alert_uid: UID of the alert rule to delete

        Returns:
            Empty dict on success
        """
        return await self._delete(f"/v1/provisioning/alert-rules/{alert_uid}")

    async def update_rule_group_interval(
        self, folder_uid: str, group: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a rule group's configuration (interval, rules).

        Args:
            folder_uid: UID of the folder
            group: Name of the rule group
            config: Rule group configuration (folderUid, interval, rules, title)

        Returns:
            Updated rule group
        """
        return await self._put(
            f"/v1/provisioning/folder/{folder_uid}/rule-groups/{group}",
            json_payload=config,
        )

    # Contact Points
    async def list_contact_points(self) -> list[Dict[str, Any]]:
        """
        Get all contact points.

        Returns:
            List of contact point configurations
        """
        return await self._get("/v1/provisioning/contact-points")

    # Contact Point Write Operations
    async def create_contact_point(
        self, contact_point: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new contact point.

        Args:
            contact_point: Contact point configuration (requires: name, type, settings)

        Returns:
            Created contact point with UID
        """
        return await self._post(
            "/v1/provisioning/contact-points", json_payload=contact_point
        )

    async def update_contact_point(
        self, uid: str, contact_point: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing contact point.

        Args:
            uid: UID of the contact point to update
            contact_point: Updated contact point configuration

        Returns:
            Updated contact point
        """
        return await self._put(
            f"/v1/provisioning/contact-points/{uid}", json_payload=contact_point
        )

    async def delete_contact_point(self, uid: str) -> Dict[str, Any]:
        """
        Delete a contact point.

        Args:
            uid: UID of the contact point to delete

        Returns:
            Empty dict on success
        """
        return await self._delete(f"/v1/provisioning/contact-points/{uid}")

    # Notification Policies
    async def get_notification_policies(self) -> Dict[str, Any]:
        """
        Get the notification policy tree.

        Returns:
            Notification policy tree configuration
        """
        return await self._get("/v1/provisioning/policies")

    # Notification Policy Write Operations
    async def set_notification_policies(
        self, policies: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Set the notification policy tree.

        Args:
            policies: Notification policy tree configuration (Route object)

        Returns:
            Updated notification policies
        """
        return await self._put("/v1/provisioning/policies", json_payload=policies)

    async def delete_notification_policies(self) -> Dict[str, Any]:
        """
        Clear the notification policy tree (reset to defaults).

        Returns:
            Empty dict on success
        """
        return await self._delete("/v1/provisioning/policies")

    # Notification Templates
    async def list_notification_templates(self) -> list[Dict[str, Any]]:
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

    # Notification Template Write Operations
    async def set_notification_template(
        self, name: str, template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create or update a notification template.

        Args:
            name: Name of the template
            template: Template configuration (requires: template field with content)

        Returns:
            Created/updated template
        """
        return await self._put(
            f"/v1/provisioning/templates/{name}", json_payload=template
        )

    async def delete_notification_template(self, name: str) -> Dict[str, Any]:
        """
        Delete a notification template.

        Args:
            name: Name of the template to delete

        Returns:
            Empty dict on success
        """
        return await self._delete(f"/v1/provisioning/templates/{name}")

    # Mute Timings
    async def list_mute_timings(self) -> list[Dict[str, Any]]:
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

    # Mute Timing Write Operations
    async def create_mute_timing(self, mute_timing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new mute timing.

        Args:
            mute_timing: Mute timing configuration (requires: name, time_intervals)

        Returns:
            Created mute timing
        """
        return await self._post("/v1/provisioning/mute-timings", json_payload=mute_timing)

    async def update_mute_timing(
        self, name: str, mute_timing: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing mute timing.

        Args:
            name: Name of the mute timing to update
            mute_timing: Updated mute timing configuration

        Returns:
            Updated mute timing
        """
        return await self._put(
            f"/v1/provisioning/mute-timings/{name}", json_payload=mute_timing
        )

    async def delete_mute_timing(self, name: str) -> Dict[str, Any]:
        """
        Delete a mute timing.

        Args:
            name: Name of the mute timing to delete

        Returns:
            Empty dict on success
        """
        return await self._delete(f"/v1/provisioning/mute-timings/{name}")

    async def list_folder_dashboards(
        self,
        folder_uid: str,
        limit: int | None = None,
        page: int | None = None,
        fields: list[str] | None = None,
    ) -> list[Dict[str, Any]]:
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
        records = [dict(dashboard) for dashboard in results]

        if fields:
            self._validate_requested_fields(records, fields, SEARCH_DASHBOARD_FIELDS)
            return [self._filter_fields(record, fields) for record in records]

        return records

    async def list_annotations(
        self,
        time_from: str | None = None,
        time_to: str | None = None,
        dashboard_id: int | None = None,
        tags: list[str] | None = None,
    ) -> list[Dict[str, Any]]:
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

    async def get_dashboard_versions(self, dashboard_uid: str) -> list[Dict[str, Any]]:
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
