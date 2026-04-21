# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP Read-Only Grafana Server provides a read-only default command plus a separate write-capable command for Grafana via the Model Context Protocol (MCP). It uses session-based authentication and supports multiple Grafana connections simultaneously.

## Runtime Config Location

- Live runtime config file:
  `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
- Checked-in sample file:
  [`connections.yaml.sample`](connections.yaml.sample)

Important distinction:

- The installed server reads the live runtime file under `~/.config/...` by default
- The checked-in sample file is documentation/source material only
- `uv run mcp-read-only-grafana --write-sample-config` writes the sample into the resolved runtime config directory
- `uv run mcp-read-only-grafana --config-dir /path/to/config-dir` changes the live config file to `/path/to/config-dir/connections.yaml`

## Development Commands

```bash
# Install dependencies
uv sync --extra dev

# Run the server manually for testing
uv run mcp-read-only-grafana

# Show the resolved runtime paths
uv run mcp-read-only-grafana --print-paths

# Run the separate write-capable command
uv run mcp-grafana-write

# Write or refresh the default sample config
uv run mcp-read-only-grafana --write-sample-config
uv run mcp-read-only-grafana --write-sample-config --overwrite

# Validate configuration through the public root CLI
uv run mcp-read-only-grafana validate-config

# Test all configured connections or one named connection
uv run mcp-read-only-grafana test-connection
uv run mcp-read-only-grafana test-connection production_grafana

# Code formatting
uv run black src/mcp_read_only_grafana/
uv run ruff check src/mcp_read_only_grafana/ tests/

# Run tests
uv run pytest -q

# Run ALL integration tests (requires Grafana credentials)
uv run pytest tests/test_integration_all_endpoints.py -v -m integration

# Run integration tests INCLUDING write-capable endpoints (requires privileged credentials)
RUN_WRITE_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v -m integration

# Override the default integration-test connection name if needed
GRAFANA_TEST_CONNECTION_NAME=my_grafana uv run pytest tests/test_integration_all_endpoints.py -v -m integration

# Run specific test category (e.g., only alerting tests)
uv run pytest tests/test_integration_all_endpoints.py::TestAlertingProvisioningAPI -v

# Run only unit tests (no credentials needed)
uv run pytest -v -m "not integration"
```

### Test Configuration

**Write Test Control:**
Integration tests for write-capable endpoints (Provisioning API, user/team management) are skipped by default. To run them:

```bash
# Enable write-capable tests via environment variable
export RUN_WRITE_TESTS=1
uv run pytest tests/test_integration_all_endpoints.py -v

# Or inline for a single run
RUN_WRITE_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v
```

**Write-capable test coverage:**
- `test_list_users` - Requires org admin permissions
- `test_list_teams` - Requires org admin permissions
- `TestAlertingProvisioningAPI` - All 16 provisioning API endpoints (requires Grafana admin)

**Integration test connection selection:**
- By default, the suite looks for a repo-root `connections.yaml` entry named
  `grafana`
- Override that with `GRAFANA_TEST_CONNECTION_NAME=<connection_name>` if your
  local test fixture uses a different name
- The chosen integration-test connection must have session-based auth available
  because the suite exercises `/api/user`

Accepted values: `1`, `true`, `yes`, `on` (case-insensitive)

## Architecture

### Core Components

**src/mcp_read_only_grafana/server.py** - MCP server entry point
- `ReadOnlyGrafanaServer` class manages connections and orchestrates tool registration
- Calls domain-specific registration functions from `src/mcp_read_only_grafana/tools/`
- Handles package bootstrap flags such as `--write-sample-config`, `--overwrite`, and `--print-paths`
- Dispatches root CLI management subcommands such as `validate-config` and `test-connection`
- Error handling: Let exceptions propagate naturally - the MCP framework handles them

**src/mcp_read_only_grafana/config.py** - Configuration management
- `GrafanaConnection` (Pydantic model): Validates connection settings
- `ConfigParser`: Loads connections from YAML and environment variables
- Session token pattern: `GRAFANA_SESSION_<CONNECTION_NAME>` (uppercase, hyphens→underscores)
- **Dynamic token reloading**: `reload_session_token()` reloads the runtime environment and persisted session cache on every call

**src/mcp_read_only_grafana/runtime_paths.py** - Runtime path resolution
- Resolves config, state, and cache directories from CLI flags, environment variables, or defaults
- Owns the package runtime layout used by both `uvx` and local development

**src/mcp_read_only_grafana/grafana_connector.py** - Grafana API client
- `GrafanaConnector` wraps httpx for Grafana API calls
- **Critical**: `_get()` calls `connection.reload_session_token()` before EVERY request
- This reloads the configured credential sources without restarting the server
- All API methods return formatted dictionaries/lists, not raw responses

**src/mcp_read_only_grafana/exceptions.py** - Custom exception hierarchy
- `GrafanaError` (base), `ConnectionNotFoundError`, `AuthenticationError`
- `PermissionDeniedError`, `GrafanaAPIError`, `GrafanaTimeoutError`

**src/mcp_read_only_grafana/validation.py** - Validation utilities
- `get_connector()`: Centralizes connection validation (replaces 55 repeated checks)

### Tool Organization

Tools are organized into domain-specific modules under `src/mcp_read_only_grafana/tools/`:

| Module | Tools | Description |
|--------|-------|-------------|
| `core_tools.py` | `list_connections`, `get_health`, `get_current_org` | Connection management |
| `dashboard_tools.py` | 8 tools | Dashboard CRUD and navigation |
| `datasource_tools.py` | 5 tools | Prometheus, Loki queries |
| `alert_tools.py` | 8 tools | Alert rules, state, history |
| `user_tools.py` | 4 tools | Users, teams, annotations |
| `admin_tools.py` | 27 tools | Write-capable tools exposed by `mcp-grafana-write` |

Each module exports a `register_*_tools(mcp, connectors)` function.

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates a `GrafanaConnection`
3. Session tokens are loaded from environment variables at startup
4. On each API request, `reload_session_token()` re-reads the runtime environment and persisted session cache; persisted state overrides the live environment value when both are present

### Error Handling Pattern

Custom exceptions in `src/mcp_read_only_grafana/exceptions.py` provide clear, typed errors:
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
- Tokens are reloaded from the runtime environment before each request, but persisted rotated state takes precedence
- Connection name in YAML maps to `GRAFANA_SESSION_<NAME>` in environment

## Key Design Decisions

1. **Read-only by default**: `mcp-read-only-grafana` keeps the safe read surface
2. **Session token reload**: Tokens are reloaded from the configured credential sources on every request
3. **No credential storage in YAML**: Tokens are injected via environment variables and may be cached in the local session state file
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly
6. **Write endpoint separation**: Provisioning API endpoints and other mutations are only registered by the `mcp-grafana-write` command
   - These endpoints often require elevated Grafana permissions
   - Marked with `[WRITE]` prefix in their docstrings
   - Includes: alert rules, contact points, notification policies, templates, mute timings
7. **Dual alerting APIs**:
   - **Ruler API** (non-admin): Available by default, allows regular users to view/manage their own alerts
     - `get_ruler_rules()`, `get_ruler_namespace_rules()`, `get_ruler_group()`
   - **Provisioning API** (write-capable): Exposed by `mcp-grafana-write`, used for infrastructure-as-code workflows
     - `list_provisioned_alert_rules()`, `get_provisioned_alert_rule()`, etc.
