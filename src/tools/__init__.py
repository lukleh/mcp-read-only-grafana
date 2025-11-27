"""MCP tool modules organized by domain.

This package contains domain-specific tool registration functions
that are called by the main server to register all MCP tools.

Modules:
    core_tools: Connection management and health checks
    dashboard_tools: Dashboard CRUD and navigation
    datasource_tools: Datasource queries (Prometheus, Loki)
    alert_tools: Alert rules and state visibility
    user_tools: Users, teams, annotations
    admin_tools: Admin-only write operations (requires --allow-admin)
"""

from .core_tools import register_core_tools
from .dashboard_tools import register_dashboard_tools
from .datasource_tools import register_datasource_tools
from .alert_tools import register_alert_tools
from .user_tools import register_user_tools
from .admin_tools import register_admin_tools

__all__ = [
    "register_core_tools",
    "register_dashboard_tools",
    "register_datasource_tools",
    "register_alert_tools",
    "register_user_tools",
    "register_admin_tools",
]
