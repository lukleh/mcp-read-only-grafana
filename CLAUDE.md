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

# Linting
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
- Env var patterns (uppercase, hyphens→underscores): `GRAFANA_API_KEY_<CONNECTION_NAME>`,
  `GRAFANA_SESSION_<CONNECTION_NAME>`, `GRAFANA_TIMEOUT_<CONNECTION_NAME>`
- **Dynamic credential reloading**: `reload_api_key()` and `reload_session_token()` re-resolve on
  every call. `_load_credential_values()` sets the precedence: YAML-configured value first, then the
  runtime environment, then the persisted state file — each layer overriding the previous one

**src/mcp_read_only_grafana/runtime_paths.py** - Runtime path resolution
- Resolves config, state, and cache directories from CLI flags, environment variables, or defaults
- Owns the package runtime layout used by both `uvx` and local development

**src/mcp_read_only_grafana/grafana_connector.py** - Grafana API client
- `GrafanaConnector` wraps httpx for Grafana API calls
- **Critical**: every request calls `_refresh_credentials()` first, so credentials are re-resolved
  without restarting the server. It applies the API key as a `Bearer` header when the connection has
  one, and otherwise falls back to the `grafana_session` cookie
- `_write_headers()` adds `X-Disable-Provenance: true` to alerting provisioning writes (matched by
  `_is_alerting_provisioning_endpoint()`) so API-created rules do not become UI-locked
- All API methods return formatted dictionaries/lists, not raw responses

**src/mcp_read_only_grafana/exceptions.py** - Custom exception hierarchy
- `GrafanaError` (base), `ConnectionNotFoundError`, `AuthenticationError`
- `PermissionDeniedError`, `GrafanaAPIError`, `GrafanaTimeoutError`

**src/mcp_read_only_grafana/validation.py** - Validation utilities
- `get_connector()`: Centralizes connection validation, used by every tool module

### Tool Organization

Tools are organized into domain-specific modules under `src/mcp_read_only_grafana/tools/`:

| Module | Tools | Description |
|--------|-------|-------------|
| `core_tools.py` | `list_connections`, `get_health`, `get_current_org` | Connection management |
| `dashboard_tools.py` | 8 tools | Dashboard CRUD and navigation |
| `datasource_tools.py` | 5 tools | Prometheus, Loki queries |
| `alert_tools.py` | 8 tools | Alert rules, state, history |
| `user_tools.py` | 5 tools | Users, teams, annotations |
| `admin_tools.py` | 28 tools | Write-capable tools exposed by `mcp-grafana-write` |

`tools/validate_config.py` and `tools/test_connection.py` back the root CLI subcommands and
register no MCP tools.

Each module exports a `register_*_tools(mcp, connectors)` function.

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates a `GrafanaConnection`
3. Credentials come from three layers, later overriding earlier: the value declared in
   `connections.yaml`, then the runtime environment, then the persisted state file
4. On each API request, `_refresh_credentials()` re-resolves them — `reload_api_key()` when the
   connection has an `api_key`, `reload_session_token()` otherwise

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

Two mechanisms, in preference order — **API key first, session cookie as a deprecated fallback**.
If a connection has both, the API key wins.

- **API key (preferred)**: a Grafana API key or service-account token (`glsa_…`), sent as a
  `Bearer` header. It may be set directly in `connections.yaml` as `api_key`, or supplied as
  `GRAFANA_API_KEY_<NAME>`.
- **Session cookie (deprecated)**: a browser `grafana_session` cookie, for short-lived local use
  only. Set as `session_token` in YAML or `GRAFANA_SESSION_<NAME>`.

Either kind is re-resolved before every request, with the persisted state file taking precedence
over the environment, which takes precedence over the YAML value. Rotated session cookies are
captured back into that state file.

See `connections.yaml.sample` for the authoritative description of the fields.

## Key Design Decisions

1. **Read-only by default**: `mcp-read-only-grafana` keeps the safe read surface
2. **Credential reload**: Credentials are re-resolved from the configured sources on every request
3. **Credentials may live in YAML**: an `api_key` in `connections.yaml` is the supported normal
   setup. Environment variables and the persisted state file override it when present
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly
6. **Write endpoint separation**: Provisioning API endpoints and other mutations are only registered by the `mcp-grafana-write` command
   - These endpoints often require elevated Grafana permissions
   - Marked with `[WRITE]` prefix in their docstrings
   - Includes: alert rules, contact points, notification policies, templates, mute timings
7. **Provenance disabled by default**: alerting provisioning writes send
   `X-Disable-Provenance: true` unless a caller opts out, so rules created through the API stay
   editable in the Grafana UI
8. **Dual alerting APIs**:
   - **Ruler API** (non-admin): Available by default, allows regular users to view/manage their own alerts
     - `get_ruler_rules()`, `get_ruler_namespace_rules()`, `get_ruler_group()`
   - **Provisioning API** (write-capable): Exposed by `mcp-grafana-write`, used for infrastructure-as-code workflows
     - `list_provisioned_alert_rules()`, `get_provisioned_alert_rule()`, etc.

## Releasing

A merged PR does **not** ship to PyPI on its own — publishing is triggered by pushing a
`vX.Y.Z` git tag, which runs `.github/workflows/publish.yml`. See [`RELEASING.md`](RELEASING.md)
for the authoritative checklist; the short version:

1. **Bump the version** in `pyproject.toml` `[project].version` (single source of truth; the
   runtime reads it via `importlib.metadata`), then refresh the lockfile: `uv sync --extra dev`.
2. **Promote the changelog**: in `CHANGELOG.md`, move the `## [Unreleased]` items into a new
   `## [X.Y.Z] - YYYY-MM-DD` section.
3. **Commit on `main`** (`pyproject.toml` + `CHANGELOG.md` + `uv.lock`), then tag and push — the
   tag must match `pyproject.toml` exactly or CI fails the release:
   `git tag vX.Y.Z && git push origin main && git push origin vX.Y.Z`.
4. **Approve the publish**: the workflow's final job pauses on the GitHub `pypi` environment for
   manual approval, then publishes via PyPI Trusted Publishing (OIDC — no stored token).
