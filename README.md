# MCP Read-Only Grafana Server

[![Tests](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml/badge.svg)](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml)

A secure MCP (Model Context Protocol) server that provides access to Grafana instances using session authentication or API keys.

> Default layout:
> - Config: `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
> - Credentials: injected via the MCP client or shell environment
> - Rotated session state: `~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json`

**Compatibility:** Targeted and tested against Grafana 9.5.x. Newer versions (e.g., 10.x) should work for read-only endpoints but may expose extra fields not covered here.

## Features

- **Read-only by default** - All operations are read-only unless `--allow-admin` is enabled
- **Optional admin mode** - Enable write operations (create/update/delete alerts) with `--allow-admin` flag
- **Session-based authentication** - Uses Grafana session cookies for secure access (default) and also supports Grafana API keys
- **Automatic token refresh** - Grafana rotates session tokens every 10 minutes; the server automatically captures refreshed tokens from response headers and persists them to `session_tokens.json` (session-cookie mode only)
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

Create the config and state directories:

```bash
mkdir -p ~/.config/lukleh/mcp-read-only-grafana
mkdir -p ~/.local/state/lukleh/mcp-read-only-grafana
```

Copy the sample configuration file:

```bash
cp connections.yaml.sample ~/.config/lukleh/mcp-read-only-grafana/connections.yaml
```

Edit `~/.config/lukleh/mcp-read-only-grafana/connections.yaml` with your Grafana instances:

```yaml
- connection_name: production_grafana
  url: https://grafana.example.com
  description: Production Grafana instance
```

### 3. Set Up Authentication

Set credentials in the environment used to launch the server (for example,
export them in your shell for local testing or inject them via your MCP client
config).

You can authenticate **either** with a session cookie (auto-rotated) **or** with a Grafana API key (Bearer token):

- Session cookie (default, supports automatic rotation & persistence):
  ```bash
  export GRAFANA_SESSION_PRODUCTION_GRAFANA=your_session_token_here
  ```
- API key (no rotation; useful for service accounts or Grafana Cloud tokens):
  ```bash
  export GRAFANA_API_KEY_PRODUCTION_GRAFANA=your_api_key_here
  ```

If both are set, the server will prefer the API key.

#### How to Get Your Grafana Session Token:

1. Login to your Grafana instance in a web browser
2. Open Developer Tools
3. Go to Application/Storage → Cookies
4. Find the cookie named `grafana_session` or `grafana_sess`
5. Copy the value and export or inject it as `GRAFANA_SESSION_<CONNECTION_NAME>`

#### How to Get a Grafana API Key:

1. In Grafana, go to **Administration → Service Accounts** (or **Configuration → API Keys** on older versions)
2. Create a key with the minimum required read permissions
3. Copy the generated token (starts with `glsa_` or similar) and export or inject it as `GRAFANA_API_KEY_<CONNECTION_NAME>`

If you start with a session cookie, the server will keep refreshed cookies in `~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json`. On later requests, that persisted state file takes precedence over the live `GRAFANA_SESSION_*` environment value; clear or update the state file if you need to force a replacement token.

### 4. Validate and Test Connections

```bash
# Validate configuration file
just validate

# Show the exact paths in use
just print-paths

# Test Grafana connectivity
just test-connection              # Test all connections
just test-connection production_grafana  # Test specific connection
```

### 5. Run the Server

Run the server manually to test:

```bash
just run

# Enable admin mode for write operations (alert management)
uv run -- python -m src.server --allow-admin

# Point the server at a different config directory
uv run -- python -m src.server --config-dir /path/to/config-dir
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
Also configure matching `GRAFANA_SESSION_*` or `GRAFANA_API_KEY_*`
environment variables in the same MCP entry.

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
- `limit` (optional): Maximum results per page (Grafana default 1000, max 5000)
- `page` (optional): Page number (1-indexed)
- `fields` (optional): Subset of Grafana fields to return (e.g., `uid`, `title`, `url`, `type`, `tags`, `folderTitle`, `folderUid`)

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
- `limit` (optional): Maximum results per page
- `page` (optional): Page number
- `fields` (optional): Subset of Grafana fields (e.g., `uid`, `title`, `url`, `tags`, `folderUid`)

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

### `get_alert_rules_with_state`
Get all alert rules with their current evaluation state. This is the same endpoint used by Grafana's Alert List panel - useful for checking if an alert is working after creation.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `state` (optional): Filter by state (e.g., "firing", "pending", "inactive")
- `rule_name` (optional): Filter by rule name (partial match)

**Returns:** Rules organized by namespace with current state (Normal, Pending, Alerting, NoData, Error), health status, and evaluation info

### `get_firing_alerts`
Get currently firing alert instances from Alertmanager. Returns alerts that have transitioned from Pending to Firing state.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `filter_labels` (optional): Label matchers (e.g., `["alertname=HighCPU", "severity=critical"]`)
- `silenced` (optional): Include silenced alerts (default: true)
- `inhibited` (optional): Include inhibited alerts (default: true)
- `active` (optional): Include active alerts (default: true)

**Returns:** List of firing alert instances with labels, annotations, startsAt, and other metadata

### `get_alert_state_history`
Get alert state transition history. Useful for debugging alert behavior and understanding evaluation patterns.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule_uid` (optional): Filter by specific rule UID
- `labels` (optional): Label matchers to filter history
- `from_time` (optional): Start time (ISO 8601 or relative like "now-1h")
- `to_time` (optional): End time (ISO 8601 or relative like "now")
- `limit` (optional): Maximum number of history entries

**Returns:** State history entries with timestamps and state transitions (Normal, Pending, Alerting, NoData, Error)

### `list_provisioned_alert_rules`
Fetch all alert rules through Grafana's provisioning API (`GET /api/v1/provisioning/alert-rules`) to audit provisioned definitions exactly as stored on the server.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Provisioned alert rule payload grouped by folder/namespace and alert rule metadata

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

### `get_current_user`
Return the profile for the currently authenticated Grafana user (name, login, email, role, theme, etc.).

> **Note:** This endpoint only works with session-based authentication. API keys are service account tokens and are not associated with a user profile - calls will return a 404 error when using API key auth.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** User object as provided by `GET /api/user`

### `list_users`
List all users in the organization.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `page` (optional): Page number
- `per_page` (optional): Page size
- `fields` (optional): Subset of Grafana fields (`userId`, `email`, `name`, `login`, `role`, `lastSeenAt`, `lastSeenAtAge`)

**Returns:** User list with IDs, names, emails, and roles

### `list_teams`
List all teams in the organization.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `page` (optional): Page number
- `per_page` (optional): Page size
- `fields` (optional): Subset of Grafana fields (`id`, `uid`, `name`, `email`, `memberCount`)

**Returns:** Team list with IDs, names, and member counts

---

## Admin Tools (requires `--allow-admin`)

The following tools are only available when running the server with `--allow-admin`. They require Grafana admin permissions and enable write operations for alert management.

> **Warning:** These tools can create, modify, and delete Grafana resources. Use with caution.

### Alert Rules

#### `create_alert_rule`
Create a new alert rule via the provisioning API.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule` (required): Alert rule definition (JSON object)

**Returns:** Created alert rule with UID

#### `update_alert_rule`
Update an existing alert rule.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule_uid` (required): UID of the alert rule to update
- `rule` (required): Updated alert rule definition (JSON object)

**Returns:** Updated alert rule

#### `delete_alert_rule`
Delete an alert rule.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule_uid` (required): UID of the alert rule to delete

**Returns:** Confirmation of deletion

#### `update_rule_group`
Update a rule group's interval configuration.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `folder_uid` (required): UID of the folder containing the rule group
- `group_name` (required): Name of the rule group
- `config` (required): Rule group configuration (JSON object with `interval`, etc.)

**Returns:** Updated rule group configuration

### Contact Points

#### `create_contact_point`
Create a new contact point for alert notifications.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `contact_point` (required): Contact point definition (JSON object)

**Returns:** Created contact point with UID

#### `update_contact_point`
Update an existing contact point.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `contact_point_uid` (required): UID of the contact point to update
- `contact_point` (required): Updated contact point definition (JSON object)

**Returns:** Updated contact point

#### `delete_contact_point`
Delete a contact point.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `contact_point_uid` (required): UID of the contact point to delete

**Returns:** Confirmation of deletion

### Notification Policies

#### `set_notification_policies`
Set the entire notification policy tree.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `policies` (required): Notification policy tree (JSON object)

**Returns:** Updated notification policies

#### `delete_notification_policies`
Reset notification policies to default.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection

**Returns:** Confirmation of reset

### Mute Timings

#### `create_mute_timing`
Create a new mute timing for silencing alerts.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `mute_timing` (required): Mute timing definition (JSON object)

**Returns:** Created mute timing

#### `update_mute_timing`
Update an existing mute timing.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `mute_timing_name` (required): Name of the mute timing to update
- `mute_timing` (required): Updated mute timing definition (JSON object)

**Returns:** Updated mute timing

#### `delete_mute_timing`
Delete a mute timing.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `mute_timing_name` (required): Name of the mute timing to delete

**Returns:** Confirmation of deletion

### Notification Templates

#### `set_notification_template`
Create or update a notification template.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `template_name` (required): Name of the template
- `template` (required): Template definition (JSON object with `template` field)

**Returns:** Created/updated template

#### `delete_notification_template`
Delete a notification template.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `template_name` (required): Name of the template to delete

**Returns:** Confirmation of deletion

---

## Configuration Options

### Connection Settings

Each connection in `connections.yaml` supports:

- `connection_name`: Unique identifier (letters, numbers, underscores)
- `url`: Grafana instance URL (without trailing slash)
- `description`: Human-readable description
- `timeout`: Request timeout in seconds (default: 30)
- `verify_ssl`: Verify SSL certificates (default: true)

### Environment Variables

- `GRAFANA_SESSION_<CONNECTION_NAME>`: Session token (optional if API key provided)
- `GRAFANA_API_KEY_<CONNECTION_NAME>`: Grafana API key / service-account token (optional)
- `GRAFANA_TIMEOUT_<CONNECTION_NAME>`: Override timeout for specific connection

## Security

The server implements a **secure-by-default model**:

1. **Read-only by default** - Only GET requests are performed without `--allow-admin`
2. **Opt-in admin mode** - Write operations require explicit `--allow-admin` flag
3. **Timeout protection** - Configurable request timeouts (default: 30s)
4. **SSL verification** - Enabled by default for all connections
5. **Session token security** - Tokens stored only in environment variables, never in code

### Default Mode (Read-Only)

Without `--allow-admin`, the server only performs HTTP GET requests:
- **GET** - Read operations only (dashboards, datasources, alerts, users, teams, etc.)
- **POST** - Limited to read-only query execution (`/api/ds/query` for Explore)

It is **impossible to modify, create, or delete any Grafana resources** in default mode.

### Admin Mode (`--allow-admin`)

When running with `--allow-admin`, additional write operations are enabled:
- **POST** - Create new alert rules, contact points, mute timings
- **PUT** - Update existing alert rules, contact points, notification policies, mute timings, templates
- **DELETE** - Remove alert rules, contact points, notification policies, mute timings, templates

> **Warning:** Admin mode enables destructive operations. Only enable when you need to manage Grafana alerting resources. The API key or session must have Grafana admin permissions.

### Additional Security Considerations

1. **Credentials are sensitive** - Never commit real credentials or `connections.yaml` to version control
2. **Automatic token refresh** - Session tokens are automatically captured and persisted when Grafana rotates them (API keys are static)
3. **Permission scope** - The server inherits the read permissions of the provided session or API key
4. **No credential storage in code** - Tokens live only in explicit environment variables plus the rotated `session_tokens.json` cache

## Troubleshooting

### Session Token Management

**Automatic Token Refresh**: Grafana rotates session tokens every 10 minutes. The server automatically:
- Captures refreshed tokens from Grafana API response headers
- Updates tokens in memory immediately
- Persists new tokens back to `session_tokens.json`
- **No manual token updates needed** - the server keeps itself authenticated!

If you manually need to update a token:
1. Update the `GRAFANA_SESSION_*` value in your MCP client env or current shell
2. Also remove or update the cached value in `session_tokens.json` if one was already persisted
3. No restart is needed once the active credential source has been updated

### Authentication Failed

If you get authentication errors despite automatic refresh:
1. Verify the initial token is valid in your current environment or `session_tokens.json`
2. Check that the state directory is writable (needed for automatic token persistence)
3. Ensure the environment variable name matches the connection name (e.g., `GRAFANA_SESSION_PRODUCTION_GRAFANA` for `connection_name: production_grafana`)

### Connection Timeout

If requests are timing out:
1. Increase the timeout in `connections.yaml`
2. Or set `GRAFANA_TIMEOUT_<CONNECTION_NAME>` in the current environment
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
