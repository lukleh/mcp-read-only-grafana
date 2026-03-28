# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP Read-Only Grafana Server provides read-only access to Grafana instances via the Model Context Protocol (MCP). It uses session-based authentication and supports multiple Grafana connections simultaneously.

## Development Commands

```bash
# Install dependencies
uv sync

# Run the server manually for testing
uv run python -m src.server

# Run with custom config file
uv run python -m src.server /path/to/connections.yaml

# Run with admin endpoints enabled (requires Grafana admin permissions)
uv run python -m src.server --allow-admin

# Run with both custom config and admin endpoints
uv run python -m src.server /path/to/connections.yaml --allow-admin

# Code formatting
uv run black src/
uv run ruff check src/

# Run tests
uv run pytest

# Run ALL integration tests (requires Grafana credentials)
uv run pytest tests/test_integration_all_endpoints.py -v -m integration

# Run integration tests INCLUDING admin-only endpoints (requires admin credentials)
RUN_ADMIN_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v -m integration

# Run specific test category (e.g., only alerting tests)
uv run pytest tests/test_integration_all_endpoints.py::TestAlertingProvisioningAPI -v

# Run only unit tests (no credentials needed)
uv run pytest -v -m "not integration"
```

### Test Configuration

**Admin Test Control:**
Integration tests for admin-only endpoints (Provisioning API, user/team management) are skipped by default. To run them:

```bash
# Enable admin tests via environment variable
export RUN_ADMIN_TESTS=1
uv run pytest tests/test_integration_all_endpoints.py -v

# Or inline for a single run
RUN_ADMIN_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v
```

**Admin-only test coverage:**
- `test_list_users` - Requires org admin permissions
- `test_list_teams` - Requires org admin permissions
- `TestAlertingProvisioningAPI` - All 16 provisioning API endpoints (requires Grafana admin)

Accepted values: `1`, `true`, `yes`, `on` (case-insensitive)

## Architecture

### Core Components

**src/server.py** - MCP server entry point (~150 lines)
- `ReadOnlyGrafanaServer` class manages connections and orchestrates tool registration
- Calls domain-specific registration functions from `src/tools/`
- Error handling: Let exceptions propagate naturally - the MCP framework handles them

**src/config.py** - Configuration management
- `GrafanaConnection` (Pydantic model): Validates connection settings
- `ConfigParser`: Loads connections from YAML and environment variables
- Session token pattern: `GRAFANA_SESSION_<CONNECTION_NAME>` (uppercase, hyphens→underscores)
- **Dynamic token reloading**: `reload_session_token()` reloads the runtime environment and persisted session cache on every call

**src/grafana_connector.py** - Grafana API client
- `GrafanaConnector` wraps httpx for Grafana API calls
- **Critical**: `_get()` calls `connection.reload_session_token()` before EVERY request
- This allows updating injected session tokens without restarting the server
- All API methods return formatted dictionaries/lists, not raw responses

**src/exceptions.py** - Custom exception hierarchy
- `GrafanaError` (base), `ConnectionNotFoundError`, `AuthenticationError`
- `PermissionDeniedError`, `GrafanaAPIError`, `GrafanaTimeoutError`

**src/types.py** - TypedDict definitions for Grafana responses
- `DashboardFull`, `PanelInfo`, `AlertRuleInfo`, `DatasourceInfo`, etc.

**src/validation.py** - Validation utilities
- `get_connector()`: Centralizes connection validation (replaces 55 repeated checks)

### Tool Organization

Tools are organized into domain-specific modules under `src/tools/`:

| Module | Tools | Description |
|--------|-------|-------------|
| `core_tools.py` | `list_connections`, `get_health`, `get_current_org` | Connection management |
| `dashboard_tools.py` | 8 tools | Dashboard CRUD and navigation |
| `datasource_tools.py` | 5 tools | Prometheus, Loki queries |
| `alert_tools.py` | 8 tools | Alert rules, state, history |
| `user_tools.py` | 4 tools | Users, teams, annotations |
| `admin_tools.py` | 27 tools | Admin-only (requires `--allow-admin`) |

Each module exports a `register_*_tools(mcp, connectors)` function.

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates a `GrafanaConnection`
3. Session tokens are loaded from environment variables at startup
4. On each API request, `reload_session_token()` re-reads the runtime environment and persisted session cache to get fresh tokens

### Error Handling Pattern

Custom exceptions in `src/exceptions.py` provide clear, typed errors:
- `ConnectionNotFoundError`: Invalid connection name (shows available options)
- `AuthenticationError`: HTTP 401, expired session
- `PermissionDeniedError`: HTTP 403, insufficient permissions
- `GrafanaAPIError`: Other HTTP errors with status code
- `GrafanaTimeoutError`: Request timeout

The MCP framework automatically converts exceptions to proper error responses.
Tool functions use `get_connector()` for validation instead of manual checks.

### Authentication

Session-based authentication using Grafana session cookies:
- Tokens are injected via environment variables (never in code or YAML)
- Tokens are reloaded from the runtime environment before each request to support token rotation
- Connection name in YAML maps to `GRAFANA_SESSION_<NAME>` in environment

## Key Design Decisions

1. **Read-only by design**: Only GET requests are performed
2. **Session token reload**: Tokens are reloaded from the runtime environment on every request to handle expiration gracefully
3. **No credential storage**: Tokens only in environment variables, never in config files
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly
6. **Admin endpoint protection**: Provisioning API endpoints (16 total) are only registered when `--allow-admin` flag is provided
   - These endpoints require Grafana admin permissions
   - Marked with `[ADMIN]` prefix in their docstrings
   - Includes: alert rules, contact points, notification policies, templates, mute timings
7. **Dual alerting APIs**:
   - **Ruler API** (non-admin): Available by default, allows regular users to view/manage their own alerts
     - `get_ruler_rules()`, `get_ruler_namespace_rules()`, `get_ruler_group()`
   - **Provisioning API** (admin-only): Requires `--allow-admin`, used for infrastructure-as-code workflows
     - `list_provisioned_alert_rules()`, `get_provisioned_alert_rule()`, etc.
