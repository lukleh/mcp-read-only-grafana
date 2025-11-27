"""Type definitions for Grafana API responses.

This module provides TypedDict definitions for common Grafana response shapes,
improving type safety and enabling better IDE/LLM inference.

Note: All TypedDict classes use `total=False` to handle optional fields gracefully.
Grafana API responses may omit certain fields depending on context and permissions.
"""

from typing import Any, Dict, List, Optional, TypedDict


# =============================================================================
# Health and Connection Types
# =============================================================================


class HealthResponse(TypedDict, total=False):
    """Response from /api/health endpoint."""

    database: str  # "ok" or error message
    version: str  # Grafana version (e.g., "9.5.3")
    commit: str  # Git commit hash


class ConnectionInfo(TypedDict):
    """Information about a configured Grafana connection."""

    name: str
    url: str
    description: str


# =============================================================================
# Dashboard Types
# =============================================================================


class DashboardSearchResult(TypedDict, total=False):
    """Result from dashboard search API."""

    uid: str
    title: str
    url: str
    type: str  # "dash-db"
    tags: List[str]
    folderTitle: str
    folderUid: str


class PanelInfo(TypedDict, total=False):
    """Basic panel information (lightweight)."""

    id: int
    title: str
    type: str  # "graph", "stat", "table", etc.
    description: str


class PanelGridPos(TypedDict, total=False):
    """Panel position in dashboard grid."""

    h: int  # height
    w: int  # width
    x: int  # x position
    y: int  # y position


class PanelFull(TypedDict, total=False):
    """Complete panel definition including queries."""

    id: int
    title: str
    type: str
    description: str
    gridPos: PanelGridPos
    targets: List[Dict[str, Any]]  # Query definitions (datasource-specific)
    options: Dict[str, Any]  # Panel-specific options
    fieldConfig: Dict[str, Any]  # Field configuration


class DashboardMeta(TypedDict, total=False):
    """Dashboard metadata from API response."""

    folder_id: Optional[int]
    folder_title: Optional[str]
    folder_uid: Optional[str]
    created: str
    created_by: str
    updated: str
    updated_by: str


class DashboardFull(TypedDict, total=False):
    """Full dashboard definition."""

    uid: str
    title: str
    description: Optional[str]
    tags: List[str]
    timezone: str
    panels: List[PanelFull]
    templating: Dict[str, Any]  # Template variables
    annotations: Dict[str, Any]  # Annotation queries
    links: List[Dict[str, Any]]  # Dashboard links
    time: Dict[str, str]  # {"from": "now-6h", "to": "now"}
    refresh: Optional[str]  # Auto-refresh interval
    schema_version: int
    version: int
    # Metadata fields
    folder_id: Optional[int]
    folder_title: Optional[str]
    folder_uid: Optional[str]
    created: Optional[str]
    created_by: Optional[str]
    updated: Optional[str]
    updated_by: Optional[str]


class DashboardInfo(TypedDict, total=False):
    """Lightweight dashboard info (from get_dashboard_info)."""

    uid: str
    title: str
    description: Optional[str]
    tags: List[str]
    folder_title: Optional[str]
    folder_uid: Optional[str]
    schema_version: int
    version: int
    variables: List[Dict[str, Any]]
    panels_summary: Dict[str, Any]  # Panel count and types
    panels: List[PanelInfo]


# =============================================================================
# Folder Types
# =============================================================================


class FolderInfo(TypedDict, total=False):
    """Folder information."""

    uid: str
    id: int
    title: str
    url: str
    can_admin: bool
    can_edit: bool
    can_save: bool
    created: str
    updated: str


# =============================================================================
# Datasource Types
# =============================================================================


class DatasourceInfo(TypedDict, total=False):
    """Datasource configuration information."""

    id: int
    uid: str
    name: str
    type: str  # "prometheus", "loki", "influxdb", etc.
    type_name: str  # Human-readable type name
    url: str
    database: str
    is_default: bool
    read_only: bool


class DatasourceHealthResponse(TypedDict, total=False):
    """Response from datasource health check."""

    status: str  # "OK" or "ERROR"
    message: str


# =============================================================================
# Alert Types
# =============================================================================


class AlertRuleInfo(TypedDict, total=False):
    """Alert rule information."""

    uid: str
    title: str
    condition: str
    data: List[Dict[str, Any]]  # Alert queries
    no_data_state: str  # "NoData", "OK", "Alerting"
    exec_err_state: str  # "Error", "OK", "Alerting"
    folder: str
    evaluation_group: str
    evaluation_interval: str


class AlertRuleWithState(TypedDict, total=False):
    """Alert rule with current state information."""

    uid: str
    title: str
    state: str  # "Normal", "Pending", "Alerting", "NoData", "Error"
    health: str  # "ok", "error", "nodata"
    folder: str
    evaluation_group: str
    last_evaluation: str  # ISO timestamp
    last_state_change: str  # ISO timestamp
    active_at: Optional[str]
    labels: Dict[str, str]
    annotations: Dict[str, str]


class FiringAlert(TypedDict, total=False):
    """Currently firing alert instance."""

    uid: str
    title: str
    state: str  # Usually "firing" or "pending"
    labels: Dict[str, str]
    annotations: Dict[str, str]
    starts_at: str
    ends_at: Optional[str]
    fingerprint: str


# =============================================================================
# User and Team Types
# =============================================================================


class UserInfo(TypedDict, total=False):
    """User information in organization."""

    userId: int
    email: str
    name: str
    login: str
    role: str  # "Admin", "Editor", "Viewer"
    lastSeenAt: str
    lastSeenAtAge: str


class TeamInfo(TypedDict, total=False):
    """Team information."""

    id: int
    uid: str
    name: str
    email: str
    memberCount: int


# =============================================================================
# Annotation Types
# =============================================================================


class AnnotationInfo(TypedDict, total=False):
    """Annotation information."""

    id: int
    alertId: int
    dashboardId: int
    panelId: int
    time: int  # Unix timestamp in milliseconds
    timeEnd: int
    text: str
    tags: List[str]
    created: int
    updated: int


# =============================================================================
# Query Response Types
# =============================================================================


class PrometheusQueryResult(TypedDict, total=False):
    """Result from Prometheus query."""

    status: str  # "success" or "error"
    data: Dict[str, Any]  # Query result data
    errorType: str
    error: str


class LokiQueryResult(TypedDict, total=False):
    """Result from Loki LogQL query."""

    status: str
    data: Dict[str, Any]
