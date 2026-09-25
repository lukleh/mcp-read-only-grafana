# Repository Guidelines

## Project Overview

MCP Read-Only Grafana Server provides a read-only default command plus a separate write-capable command for Grafana via the Model Context Protocol (MCP). It authenticates with a Grafana API key (preferred) or a deprecated browser session cookie, and supports multiple Grafana connections simultaneously.

## Project Structure & Module Organization
`src/mcp_read_only_grafana/server.py` boots the MCP server, runtime-path helpers, and root management subcommands. The Grafana API client lives in `grafana_connector.py`; connection parsing and credential precedence live in `config.py`; runtime path resolution lives in `runtime_paths.py`; typed errors are in `exceptions.py`; and validation helpers are in `validation.py`. Tool registration is split by domain under `src/mcp_read_only_grafana/tools/` (`dashboard`, `datasource`, `alert`, `user`, `admin`, plus core helpers). Tests live in `tests/`, and `connections.schema.json` plus `connections.yaml.sample` document the config surface.

## Runtime Config Location
- The live runtime Grafana config file is:
  `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
- The checked-in [`connections.yaml.sample`](connections.yaml.sample) file is
  documentation/source material only.
- `--write-sample-config` writes the sample into the resolved runtime config
  directory.
- `--config-dir /path/to/config-dir` changes the live config file location to:
  `/path/to/config-dir/connections.yaml`

When updating config-location documentation, keep these aligned:
- [README.md](README.md)
- [connections.yaml.sample](connections.yaml.sample)
- [src/mcp_read_only_grafana/server.py](src/mcp_read_only_grafana/server.py)

## Build, Test, and Development Commands
- `uv sync --extra dev` installs runtime and development dependencies.
- `uv run mcp-read-only-grafana` runs the read-only server manually for testing.
- `uv run mcp-grafana-write` runs the separate write-capable command.
- `uv run mcp-read-only-grafana --print-paths` shows the resolved config, state, and cache locations.
- `uv run mcp-read-only-grafana --write-sample-config` writes the default config files; add `--overwrite` only when replacing them intentionally.
- `uv run mcp-read-only-grafana validate-config` validates `connections.yaml` against the packaged schema.
- `uv run mcp-read-only-grafana test-connection` checks all configured connections; pass a connection name to scope it.
- `uv run pytest -q` runs the full test suite.
- `uv run pytest tests/test_server.py -q` is a fast focused iteration loop.
- `uv run pytest -v -m "not integration"` runs only unit tests, which need no credentials.
- `uv run pytest tests/test_integration_all_endpoints.py -v -m integration` runs the integration suite, which requires Grafana credentials.
- `RUN_WRITE_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v -m integration` runs the write-capable integration coverage.
- `uv run pytest tests/test_integration_all_endpoints.py::TestAlertingProvisioningAPI -v` runs one integration category.
- `uv run ruff check src/mcp_read_only_grafana tests` lints and `uv run ty check` type-checks `src/`.

### Test Configuration

**Write test control:** integration tests for write-capable endpoints (Provisioning API, user/team
management) are skipped by default. Set `RUN_WRITE_TESTS=1` to enable them, either exported or
inline for a single run. Accepted values: `1`, `true`, `yes`, `on` (case-insensitive).

Write-capable test coverage:
- `test_list_users` - Requires org admin permissions
- `test_list_teams` - Requires org admin permissions
- `TestAlertingProvisioningAPI` - All 16 provisioning API endpoints (requires Grafana admin)

Integration test connection selection:
- By default, the suite looks for a repo-root `connections.yaml` entry named
  `grafana`
- Override that with `GRAFANA_TEST_CONNECTION_NAME=<connection_name>` if your
  local test fixture uses a different name
- The chosen integration-test connection must have session-based auth available
  because the suite exercises `/api/user`

## Architecture

### Core Components

**src/mcp_read_only_grafana/server.py** - MCP server entry point
- `ReadOnlyGrafanaServer` class manages connections and orchestrates tool registration
- Calls domain-specific registration functions from `src/mcp_read_only_grafana/tools/`
- Handles package bootstrap flags such as `--write-sample-config`, `--overwrite`, and `--print-paths`
- Dispatches root CLI management subcommands such as `validate-config` and `test-connection`
- Error handling: every tool carries `@surface_tool_errors` below `@mcp.tool()`, so anticipated
  failures reach the caller with their message (see "Error Handling Pattern")

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
| `dashboard_tools.py` | 8 tools | Dashboard reads and navigation (writes live in `admin_tools.py`) |
| `datasource_tools.py` | 5 tools | Prometheus, Loki queries |
| `alert_tools.py` | 8 tools | Alert rules, state, history |
| `user_tools.py` | 5 tools | Users, teams, annotations |
| `admin_tools.py` | 28 tools | Write-capable tools exposed by `mcp-grafana-write` |

`tools/validate_config.py` and `tools/test_connection.py` back the root CLI subcommands and
register no MCP tools.

Each module exports a `register_*_tools(mcp, connectors)` function; `register_core_tools` also takes the `connections` list.

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

Since mcp 2.1 the SDK reports any exception other than `ToolError` to the caller as the generic
`Error executing tool <name>`. `surface_tool_errors` in `validation.py` re-raises the types in
`ANTICIPATED_TOOL_ERRORS` (`GrafanaError`, `ValueError`, `OSError`) as `ToolError` so the caller
sees the reason; anything else stays a crash with its traceback in the server log. Stack it below
`@mcp.tool()` on every new tool; `tests/test_tool_error_surfacing.py` fails if one is missing.
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
5. **MCP error handling**: Raise the typed errors; `@surface_tool_errors` forwards their message to the caller
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

## Coding Style & Naming Conventions
Target Python 3.11+ with four-space indentation, explicit type hints, and concise docstrings when behavior is not obvious. Use `snake_case` for modules, functions, tests, and config keys; use `PascalCase` for classes and Pydantic models. Keep domain logic in the existing tool modules rather than collapsing it back into `server.py`, and preserve the shared connector and validation helpers instead of duplicating request or auth checks.

## Testing Guidelines
Pytest uses `unit` and `integration` markers from `pyproject.toml`. Add or update tests for any change to credential precedence, session refresh, pagination, dashboard traversal, or write-capable endpoint gating. When touching write functionality, keep both the default read-only behavior and the `mcp-grafana-write` path covered, and only rely on `RUN_WRITE_TESTS=1` for cases that truly need privileged live credentials.

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

## Commit & Pull Request Guidelines
Follow the current history style with short imperative commit subjects and small focused diffs. Pull requests should explain whether the change affects the read-only command, the write command, or both, and should list the exact local commands you ran, including any integration coverage.

## Security & Configuration Tips
Prefer API keys or service-account tokens over the deprecated session-cookie fallback. Do not weaken the separation between the default read-only command and the write-capable command. Treat rotated session state in `~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json` as sensitive local data.
