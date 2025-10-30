# MCP Read-Only Grafana Server

[![Tests](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml/badge.svg)](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml)

A secure MCP (Model Context Protocol) server that provides **read-only** access to Grafana instances using session authentication.

## Features

- **Read-only access** - All operations are read-only, no modifications possible
- **Minimal write surface** - All API calls use HTTP GET except the Explore `/api/ds/query` endpoint, which requires POST for read-only query execution
- **Session-based authentication** - Uses Grafana session cookies for secure access
- **Automatic token refresh** - Grafana rotates session tokens every 10 minutes; the server automatically captures refreshed tokens from response headers and persists them to `.env`
- **Hierarchical dashboard navigation** - Handle large dashboards efficiently with lightweight metadata queries and per-panel detail fetching
- **Multiple instances** - Support for multiple Grafana connections
- **Comprehensive API coverage** - Access dashboards, panels, folders, datasources, and alerts
- **Security focused** - Timeouts, SSL verification, and secure token storage

## Prerequisites

This project requires:
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver
- [just](https://github.com/casey/just) - Command runner (optional, but recommended for development)

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Grafana Connections

Copy the sample configuration file:

```bash
cp connections.yaml.sample connections.yaml
```

Edit `connections.yaml` with your Grafana instances:

```yaml
- connection_name: production_grafana
  url: https://grafana.example.com
  description: Production Grafana instance
```

### 3. Set Up Authentication

Create a `.env` file from the sample:

```bash
cp .env.sample .env
```

Add your Grafana session tokens to `.env`:

```bash
GRAFANA_SESSION_PRODUCTION_GRAFANA=your_session_token_here
```

#### How to Get Your Grafana Session Token:

1. Login to your Grafana instance in a web browser
2. Open Developer Tools (F12)
3. Go to Application/Storage → Cookies
4. Find the cookie named `grafana_session` or `grafana_sess`
5. Copy the value and paste it in the `.env` file

### 4. Validate and Test Connections

```bash
# Validate configuration file
just validate

# Test Grafana connectivity
just test-connection              # Test all connections
just test-connection production_grafana  # Test specific connection
```

### 5. Run the Server

Run the server manually to test:

```bash
just run

# Or with a custom config file
just run /path/to/connections.yaml
```

### 6. Add MCP to Your AI Assistant

For **Claude Code**:
```bash
claude mcp add mcp-read-only-grafana -- uv --directory {PATH_TO_MCP_READ_ONLY_GRAFANA} run python -m src.server
```

For **Codex**:
```bash
codex mcp add mcp-read-only-grafana -- uv --directory {PATH_TO_MCP_READ_ONLY_GRAFANA} run python -m src.server
```

Replace `{PATH_TO_MCP_READ_ONLY_GRAFANA}` with the absolute path to where you cloned this repository (e.g., `/Users/yourname/projects/mcp-read-only-grafana`).

## Available MCP Tools

### `list_connections`
List all configured Grafana instances.

**Returns:** JSON with connection names, URLs, and descriptions

### `get_health`
Check Grafana instance health and version.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Health status and version information

### `search_dashboards`
Search for dashboards by name or tag.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `query` (optional): Search query for dashboard names
- `tag` (optional): Tag to filter dashboards

**Returns:** List of matching dashboards with UIDs, titles, and tags

### `get_dashboard_info`
Get lightweight dashboard metadata and panel list (without full panel definitions). **Recommended first step for exploring dashboards, especially large ones.**

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard_uid` (required): UID of the dashboard

**Returns:** Dashboard metadata, variables, and list of all panels with basic info

### `get_dashboard_panel`
Get full configuration for a single panel from a dashboard. **Use this after `get_dashboard_info()` to explore specific panels in detail.**

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard_uid` (required): UID of the dashboard
- `panel_id` (required): Panel ID to retrieve

**Returns:** Full panel JSON including queries, transformations, and field config

### `get_dashboard`
Get complete dashboard definition. **Use with caution for large dashboards - may exceed token limits. Prefer `get_dashboard_info()` + `get_dashboard_panel()` for large dashboards.**

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard_uid` (required): UID of the dashboard

**Returns:** Full dashboard JSON including panels, variables, and settings

### `get_dashboard_panels`
Get simplified panel information from a dashboard. Returns basic panel metadata without full configuration.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard_uid` (required): UID of the dashboard

**Returns:** List of panels with IDs, titles, types, and descriptions

### `list_folders`
List all folders in Grafana.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Folder hierarchy with IDs and titles

### `list_folder_dashboards`
List all dashboards within a specific folder.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `folder_uid` (required): UID of the folder

**Returns:** List of dashboards in the folder with UIDs, titles, and URLs

### `list_datasources`
List configured data sources.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Data source names, types, UIDs, and configuration

### `query_prometheus`
Execute a PromQL query against a Prometheus datasource.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `datasource_uid` (required): UID of the Prometheus datasource
- `query` (required): PromQL query string
- `time_from` (optional): Start time (RFC3339 or relative like "now-1h")
- `time_to` (optional): End time (RFC3339 or "now")
- `step` (optional): Query resolution step (e.g., "15s", "1m")

**Returns:** Query results with timestamps and values

### `query_loki`
Execute a LogQL query against a Loki datasource.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `datasource_uid` (required): UID of the Loki datasource
- `query` (required): LogQL query string
- `time_from` (optional): Start time (RFC3339 or relative like "now-1h")
- `time_to` (optional): End time (RFC3339 or "now")
- `limit` (optional): Maximum number of log lines (default: 100)

**Returns:** Log query results with timestamps and log lines

### `explore_query`
Execute Grafana Explore queries via the `/api/ds/query` endpoint.

> Note: This is the only tool that issues an HTTP POST (required by Grafana Explore). The call is still read-only and does not mutate Grafana state.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `queries` (required): List of Explore query definitions (including datasource, `refId`, etc.)
- `range_from` (optional): Relative or absolute start time (e.g., `now-6h`)
- `range_to` (optional): End time (e.g., `now`)
- `max_data_points` (optional): Maximum number of datapoints to request
- `interval_ms` (optional): Query interval in milliseconds
- `additional_options` (optional): Extra request fields that must not overlap with reserved keys

**Returns:** Raw Explore results as returned by Grafana

### `list_alerts`
List alert rules.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `folder_uid` (optional): Filter alerts by folder

**Returns:** Alert rules with status and conditions

### `get_alert_rule_by_uid`
Get a specific alert rule by its UID.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `alert_uid` (required): UID of the alert rule

**Returns:** Alert rule details including conditions, labels, and annotations

### `list_annotations`
List annotations (events marked on dashboards).

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `time_from` (optional): Start time for annotation search
- `time_to` (optional): End time for annotation search
- `dashboard_id` (optional): Filter by dashboard ID
- `tags` (optional): List of tags to filter by

**Returns:** Annotations with timestamps, text, and tags

### `get_dashboard_versions`
Get version history for a dashboard.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard_uid` (required): UID of the dashboard

**Returns:** List of dashboard versions with timestamps and change messages

### `get_current_org`
Get current organization information.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Organization name and ID

### `list_users`
List all users in the organization.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** User list with IDs, names, emails, and roles

### `list_teams`
List all teams in the organization.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Team list with IDs, names, and member counts

## Configuration Options

### Connection Settings

Each connection in `connections.yaml` supports:

- `connection_name`: Unique identifier (letters, numbers, underscores)
- `url`: Grafana instance URL (without trailing slash)
- `description`: Human-readable description
- `timeout`: Request timeout in seconds (default: 30)
- `verify_ssl`: Verify SSL certificates (default: true)

### Environment Variables

- `GRAFANA_SESSION_<CONNECTION_NAME>`: Session token (required)
- `GRAFANA_TIMEOUT_<CONNECTION_NAME>`: Override timeout for specific connection

## Security

The server implements a **read-only security model**:

1. **HTTP method restriction** - Only GET requests are performed, no write operations possible
2. **Timeout protection** - Configurable request timeouts (default: 30s)
3. **SSL verification** - Enabled by default for all connections
4. **Session token security** - Tokens stored only in environment variables, never in code

### How Read-Only Is Enforced

**Grafana API** - The connector exclusively uses HTTP GET requests. All API methods are implemented through a single `_get()` function that only calls `httpx.AsyncClient.get()`. No write operations (POST, PUT, DELETE, PATCH) are implemented in the codebase.

Grafana's REST API follows standard conventions:
- **GET** - Read operations only (dashboards, datasources, alerts, users, teams, etc.)
- **POST** - Create operations (not implemented)
- **PUT** - Update operations (not implemented)
- **DELETE** - Delete operations (not implemented)
- **PATCH** - Partial update operations (not implemented)

Since the connector only implements GET requests, it is **impossible to modify, create, or delete any Grafana resources** through this MCP server.

### Additional Security Considerations

1. **Session tokens are sensitive** - Never commit `.env` or `connections.yaml` to version control
2. **Automatic token refresh** - Session tokens are automatically captured and persisted when Grafana rotates them
3. **Permission scope** - The server inherits the read permissions of the session token's user account
4. **No credential storage** - Tokens are only stored in environment variables and `.env` file

## Troubleshooting

### Session Token Management

**Automatic Token Refresh**: Grafana rotates session tokens every 10 minutes. The server automatically:
- Captures refreshed tokens from Grafana API response headers
- Updates tokens in memory immediately
- Persists new tokens back to `.env` file
- **No manual token updates needed** - the server keeps itself authenticated!

If you manually need to update a token:
1. Update the `GRAFANA_SESSION_*` value in `.env`
2. The new token will be picked up on the next request automatically
3. No need to restart the MCP server or Claude Desktop

### Authentication Failed

If you get authentication errors despite automatic refresh:
1. Verify the initial token is valid in `.env`
2. Check that the `.env` file is writable (needed for automatic token persistence)
3. Ensure the environment variable name matches the connection name (e.g., `GRAFANA_SESSION_PRODUCTION_GRAFANA` for `connection_name: production_grafana`)

### Connection Timeout

If requests are timing out:
1. Increase the timeout in `connections.yaml`
2. Or set `GRAFANA_TIMEOUT_<CONNECTION_NAME>` in `.env`
3. Check network connectivity to the Grafana instance

### SSL Verification Issues

For self-signed certificates (not recommended for production):
```yaml
- connection_name: local_grafana
  url: https://localhost:3000
  verify_ssl: false
```

## Development

### Available Commands

See all available commands:
```bash
just
```

Common commands:
```bash
just install          # Install dependencies
just validate         # Validate configuration
just test-connection  # Test Grafana connections
just run              # Run the server
just lint             # Run linter
just lint-fix         # Auto-fix linting issues
just format           # Format code
just test             # Run tests
```

### Running Tests

```bash
just test
# or
uv run pytest
```

### Code Formatting

```bash
just format
just lint
# or
uv run black src/
uv run ruff check src/
```

## License

MIT License - See LICENSE file for details
