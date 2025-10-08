import httpx
import logging
from typing import List, Dict, Any, Optional
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
                raise Exception(f"Authentication failed for {self.connection.connection_name}. Session may have expired.")
            elif e.response.status_code == 403:
                raise Exception(f"Permission denied for {self.connection.connection_name}. User may lack read permissions.")
            else:
                raise Exception(f"HTTP {e.response.status_code}: {e.response.text}")
        except httpx.TimeoutException:
            raise Exception(f"Request timed out after {self.connection.timeout} seconds")
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
                            self.connection.update_session_token(new_token, persist=True)

                            # Update httpx client cookies
                            self.client.cookies.set("grafana_session", new_token)

                        break

    async def get_health(self) -> Dict[str, Any]:
        """Get Grafana instance health status"""
        health_data = await self._get("/health")
        # Also get version info
        try:
            settings = await self._get("/frontend/settings")
            health_data['version'] = settings.get('buildInfo', {}).get('version', 'unknown')
        except Exception:
            health_data['version'] = 'unknown'
        return health_data

    async def search_dashboards(self, query: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for dashboards by name or tag"""
        params = {"type": "dash-db"}
        if query:
            params["query"] = query
        if tag:
            params["tag"] = tag

        results = await self._get("/search", **params)

        # Enhance results with additional info
        enhanced_results = []
        for dashboard in results:
            enhanced = {
                "uid": dashboard.get("uid"),
                "title": dashboard.get("title"),
                "url": dashboard.get("url"),
                "type": dashboard.get("type"),
                "tags": dashboard.get("tags", []),
                "folder_title": dashboard.get("folderTitle", "General"),
                "folder_uid": dashboard.get("folderUid"),
            }
            enhanced_results.append(enhanced)

        return enhanced_results

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

    async def list_alerts(self, folder_uid: Optional[str] = None) -> List[Dict[str, Any]]:
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
                        "no_data_state": rule.get("grafana_alert", {}).get("noDataState"),
                        "exec_err_state": rule.get("grafana_alert", {}).get("execErrState"),
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
            panels_minimal.append({
                "id": panel.get("id"),
                "title": panel.get("title"),
                "type": panel.get("type"),
                "gridPos": panel.get("gridPos"),
                "description": panel.get("description", "")[:100] if panel.get("description") else "",  # Truncate long descriptions
            })

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
                "panels": panels_minimal
            }
        }

    async def get_dashboard_panel(self, dashboard_uid: str, panel_id: int) -> Dict[str, Any]:
        """Get full details for a single panel from a dashboard"""
        result = await self._get(f"/dashboards/uid/{dashboard_uid}")
        dashboard = result.get("dashboard", {})

        # Find the specific panel
        for panel in dashboard.get("panels", []):
            if panel.get("id") == panel_id:
                return panel

        raise Exception(f"Panel with id {panel_id} not found in dashboard {dashboard_uid}")

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

    async def query_prometheus(self, datasource_uid: str, query: str, time_from: Optional[str] = None, time_to: Optional[str] = None, step: Optional[str] = None) -> Dict[str, Any]:
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
        endpoint = f"/datasources/proxy/uid/{datasource_uid}/api/v1/query_range" if step else f"/datasources/proxy/uid/{datasource_uid}/api/v1/query"

        result = await self._get(endpoint, **params)
        return result

    async def query_loki(self, datasource_uid: str, query: str, time_from: Optional[str] = None, time_to: Optional[str] = None, limit: Optional[int] = 100) -> Dict[str, Any]:
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

    async def get_current_org(self) -> Dict[str, Any]:
        """Get current organization information"""
        return await self._get("/org")

    async def list_users(self) -> List[Dict[str, Any]]:
        """List all users in the current organization"""
        users = await self._get("/org/users")

        formatted_users = []
        for user in users:
            formatted = {
                "user_id": user.get("userId"),
                "email": user.get("email"),
                "name": user.get("name"),
                "login": user.get("login"),
                "role": user.get("role"),
                "last_seen_at": user.get("lastSeenAt"),
                "last_seen_at_age": user.get("lastSeenAtAge"),
            }
            formatted_users.append(formatted)

        return formatted_users

    async def list_teams(self) -> List[Dict[str, Any]]:
        """List all teams in the organization"""
        result = await self._get("/teams/search")
        teams = result.get("teams", [])

        formatted_teams = []
        for team in teams:
            formatted = {
                "id": team.get("id"),
                "uid": team.get("uid"),
                "name": team.get("name"),
                "email": team.get("email"),
                "member_count": team.get("memberCount", 0),
            }
            formatted_teams.append(formatted)

        return formatted_teams

    async def get_alert_rule_by_uid(self, alert_uid: str) -> Dict[str, Any]:
        """Get detailed information about a specific alert rule"""
        result = await self._get(f"/ruler/grafana/api/v1/rules/{alert_uid}")
        return result

    async def list_folder_dashboards(self, folder_uid: str) -> List[Dict[str, Any]]:
        """List all dashboards in a specific folder"""
        params = {
            "type": "dash-db",
            "folderUids": folder_uid,
        }

        results = await self._get("/search", **params)

        formatted_dashboards = []
        for dashboard in results:
            formatted = {
                "uid": dashboard.get("uid"),
                "title": dashboard.get("title"),
                "url": dashboard.get("url"),
                "tags": dashboard.get("tags", []),
            }
            formatted_dashboards.append(formatted)

        return formatted_dashboards

    async def list_annotations(self, time_from: Optional[str] = None, time_to: Optional[str] = None, dashboard_id: Optional[int] = None, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
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
