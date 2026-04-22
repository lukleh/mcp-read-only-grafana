# MCP Read-Only Grafana Server

[![Tests](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml/badge.svg)](https://github.com/lukleh/mcp-read-only-grafana/actions/workflows/test.yml)

A secure MCP (Model Context Protocol) server for Grafana with a read-only default and a separate `mcp-grafana-write` command for write-capable workflows.

> Default layout:
> - Live config: `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
> - Credentials: injected via the MCP client or shell environment
> - Rotated session state: `~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json`
> - Cache: `~/.cache/lukleh/mcp-read-only-grafana/`

**Compatibility:** Targeted and tested against Grafana 9.5.x. Newer versions (e.g., 10.x) should work for read-only endpoints but may expose extra fields not covered here.

## Features

- **Read-only by default** - `mcp-read-only-grafana` exposes the safe default surface
- **Separate write command** - `mcp-grafana-write` enables dashboard saves, alerting writes, folders, and related mutations from the same package
- **API key first authentication** - Prefers Grafana API keys or service-account tokens for stable machine access
- **Deprecated session-cookie fallback** - Still supports Grafana session cookies, including automatic capture of rotated cookies in `session_tokens.json`
- **Hierarchical dashboard navigation** - Handle large dashboards efficiently with lightweight metadata queries and per-panel detail fetching
- **Multiple instances** - Support for multiple Grafana connections
- **Comprehensive API coverage** - Access dashboards, panels, folders, datasources, and alerts
- **Security focused** - Timeouts, SSL verification, and secure token storage

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv)
- Grafana credentials for at least one instance
- an MCP client such as Claude Code or Codex

## Quick Start

### 1. Install the Server

```bash
# Run the published package without cloning the repository
uvx mcp-read-only-grafana@latest --write-sample-config

# Or install it once and reuse the command directly
uv tool install mcp-read-only-grafana
mcp-read-only-grafana --write-sample-config

# The same install also provides the separate write-capable command
mcp-grafana-write --print-paths
```

When using `uvx`, prefer `mcp-read-only-grafana@latest` in user-facing docs and
MCP client configs. This avoids reusing a stale cached tool environment after a
new release is published. For the separate write-capable command, use
`uvx --from mcp-read-only-grafana@latest mcp-grafana-write`.

The command above writes a starter config and matching schema to:

- `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
- `~/.config/lukleh/mcp-read-only-grafana/connections.schema.json`

The live runtime config file used by the installed server is
`~/.config/lukleh/mcp-read-only-grafana/connections.yaml`.

### 2. Confirm Runtime Paths

```bash
uvx mcp-read-only-grafana@latest --print-paths
```

### Where `connections.yaml` Lives

By default, the server reads the live runtime config from:

- `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`

On this machine, that expands to:

- `/Users/<your-user>/.config/lukleh/mcp-read-only-grafana/connections.yaml`

Important distinction:

- The live runtime file is `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`
- The checked-in repo sample is [`connections.yaml.sample`](connections.yaml.sample)

The sample file documents the format, but it is not the file the installed
server reads unless you explicitly copy or generate it into the runtime config
directory.

### 3. Edit the Connections File

Edit `~/.config/lukleh/mcp-read-only-grafana/connections.yaml` with your Grafana instances:

```yaml
- connection_name: production_grafana
  url: https://grafana.example.com
  description: Production Grafana instance
  api_key: glsa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

- connection_name: staging_grafana
  url: https://staging-grafana.example.com
  description: Staging Grafana instance
```

### 4. Set Up Authentication

You can keep credentials either directly in `connections.yaml` or in the
environment used to launch the server. Prefer `api_key` for normal use. For
local shell testing you can export credentials directly; for normal MCP use,
inject them through the client config when you want runtime overrides.

YAML credentials:

```yaml
- connection_name: production_grafana
  url: https://grafana.example.com
  api_key: glsa_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

You can authenticate with either a Grafana API key or a deprecated session
cookie fallback:

- API key or service-account token:

  ```bash
  export GRAFANA_API_KEY_PRODUCTION_GRAFANA=your_api_key_here
  ```

- Deprecated session cookie fallback:

  ```bash
  export GRAFANA_SESSION_PRODUCTION_GRAFANA=your_session_token_here
  ```

Precedence is:
- Rotated session cookies in `session_tokens.json`
- Runtime environment variables
- Credentials declared in `connections.yaml`

If both a session token and an API key are available for the same connection,
the server prefers the API key.

#### Deprecated: How to Get a Grafana Session Token

1. Log in to Grafana in a web browser
2. Open developer tools
3. Go to Application/Storage -> Cookies
4. Find the cookie named `grafana_session` or `grafana_sess`
5. Copy the value and export or inject it as `GRAFANA_SESSION_<CONNECTION_NAME>`

Use this only as a temporary fallback. Browser session cookies rotate and
expire quickly, so they are less reliable than API keys for MCP usage.

#### How to Get a Grafana API Key

1. In Grafana, go to **Administration -> Service Accounts** or **Configuration -> API Keys**
2. Create a key with the minimum required permissions
3. Export or inject it as `GRAFANA_API_KEY_<CONNECTION_NAME>`

If you start with a session cookie, the server will keep refreshed cookies in
`~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json`. On later
requests, that persisted state file takes precedence over the live
`GRAFANA_SESSION_*` environment value and any static `session_token` in
`connections.yaml` until you update or remove it.

### 5. Configure Your MCP Client

**Claude Code**

```bash
claude mcp add mcp-read-only-grafana \
  --scope user \
  -e GRAFANA_API_KEY_PRODUCTION_GRAFANA=your_api_key_here \
  -- uvx mcp-read-only-grafana@latest
```

**Codex**

```bash
codex mcp add mcp-read-only-grafana \
  --env GRAFANA_API_KEY_PRODUCTION_GRAFANA=your_api_key_here \
  -- uvx mcp-read-only-grafana@latest
```

If you absolutely need the deprecated session-cookie fallback, swap
`GRAFANA_API_KEY_*` for `GRAFANA_SESSION_*` in the MCP client config.

If you want the write-capable endpoints, launch the separate write command from
the same package:

```bash
uvx --from mcp-read-only-grafana@latest mcp-grafana-write
```

For a persistent install created with `uv tool install mcp-read-only-grafana`,
run `mcp-grafana-write` directly.

### 6. Restart and Test

Restart your MCP client and try a simple query such as:

```text
List all dashboards in the production Grafana instance.
```

## Command Line Testing

```bash
# Show the resolved runtime paths
uvx mcp-read-only-grafana@latest --print-paths

# Write or refresh the default connections.yaml
uvx mcp-read-only-grafana@latest --write-sample-config
uvx mcp-read-only-grafana@latest --write-sample-config --overwrite

# Run the server with the default home-directory config
uvx mcp-read-only-grafana@latest

# Run the separate write-capable command from the same package
uvx --from mcp-read-only-grafana@latest mcp-grafana-write

# Point the server at a different config root
uvx mcp-read-only-grafana@latest --config-dir /path/to/config-dir

# Validate the generated configuration
uvx mcp-read-only-grafana@latest validate-config

# Test all configured Grafana connections
uvx mcp-read-only-grafana@latest test-connection

# Test one specific connection
uvx mcp-read-only-grafana@latest test-connection production_grafana
```

## Local Development

If you want to work on the repository itself:

```bash
git clone https://github.com/lukleh/mcp-read-only-grafana.git
cd mcp-read-only-grafana
uv sync --extra dev
uv run pytest -q
uv run mcp-read-only-grafana --print-paths
uv run mcp-grafana-write --print-paths
```

The checked-in sample file remains available at [connections.yaml.sample](connections.yaml.sample) for documentation and review, but package users should prefer `--write-sample-config`.

Even during local development, the server still uses the resolved runtime
config path by default. It does not automatically read the repo's
`connections.yaml.sample`.

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

### `get_datasource_health`
Run the datasource-specific Grafana health check when the datasource plugin supports it.

> **Note:** Not every datasource plugin implements `GET /api/datasources/uid/:uid/health`. When Grafana returns `404`, the MCP returns a structured `unsupported` or `not_found` result instead of surfacing the raw error.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `datasource_uid` (required): UID of the datasource

**Returns:** Health information for supported datasources, or a structured explanation when the health endpoint is unavailable

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

> **Note:** This endpoint only works with session-based authentication. API keys are service account tokens and are not associated with a user profile. When API key auth is in use, the MCP returns a structured `unavailable` result instead of surfacing Grafana's raw `404` response.

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

## Write Tools (requires `mcp-grafana-write`)

The following tools are only available when running the separate
`mcp-grafana-write` command. They enable write operations for dashboards,
folders, and Grafana alerting resources. The required Grafana permission scope
depends on the specific endpoint.

> **Warning:** These tools can create, modify, and delete Grafana resources. Use with caution.

### Dashboards

#### `save_dashboard`
Create or update a dashboard using raw Grafana dashboard JSON.

When the dashboard UID already exists, the server first fetches the live dashboard and reuses its current `id` and `version`. If you do not pass `folder_uid` or `folder_id`, it also preserves the current folder so updates do not accidentally move the dashboard to the root level.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `dashboard` (required): Raw Grafana dashboard model JSON object
- `folder_uid` (optional): Folder UID override for the save target
- `folder_id` (optional): Folder ID override for the save target
- `message` (optional): Dashboard version history message
- `overwrite` (optional): Set to `true` to overwrite an existing dashboard with the same UID

**Returns:** Grafana's save-dashboard response with `id`, `uid`, `url`, `status`, and `version`

### Folders

#### `create_folder`
Create a new folder in Grafana.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `title` (required): Folder title
- `uid` (optional): Explicit folder UID
- `parent_uid` (optional): Parent folder UID for nested folders

**Returns:** Created folder details including UID and URL

### Alert Rules

#### `create_alert_rule`
Create a new alert rule via the provisioning API.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule` (required): Alert rule definition (JSON object)
- `disable_provenance` (optional): Defaults to `true` and sends `X-Disable-Provenance: true` so Grafana keeps the alert editable in the UI. Set to `false` to keep Grafana's provisioned behavior

**Returns:** Created alert rule with UID

#### `update_alert_rule`
Update an existing alert rule.

**Parameters:**
- `connection_name` (required): Name of the Grafana connection
- `rule_uid` (required): UID of the alert rule to update
- `rule` (required): Updated alert rule definition (JSON object)
- `disable_provenance` (optional): Defaults to `true` and sends `X-Disable-Provenance: true` so Grafana keeps the alert editable in the UI. Set to `false` to keep Grafana's provisioned behavior

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
- `disable_provenance` (optional): Defaults to `true` and sends `X-Disable-Provenance: true` so Grafana keeps the rule group and its alerts editable in the UI. Set to `false` to keep Grafana's provisioned behavior

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

- `GRAFANA_API_KEY_<CONNECTION_NAME>`: Preferred Grafana API key / service-account token
- `GRAFANA_SESSION_<CONNECTION_NAME>`: Deprecated session-token fallback
- `GRAFANA_TIMEOUT_<CONNECTION_NAME>`: Override timeout for specific connection

## Security

The server implements a **secure-by-default model**:

1. **Read-only by default** - `mcp-read-only-grafana` only performs safe read operations
2. **Separate write command** - `mcp-grafana-write` exposes write-capable tools when you intentionally opt into that command
3. **Timeout protection** - Configurable request timeouts (default: 30s)
4. **SSL verification** - Enabled by default for all connections
5. **Credential security** - Keep API keys or fallback session tokens in local config, env, or MCP-managed state only

### Default Mode (Read-Only)

When launched via `mcp-read-only-grafana`, the server only performs HTTP GET requests:
- **GET** - Read operations only (dashboards, datasources, alerts, users, teams, etc.)
- **POST** - Limited to read-only query execution (`/api/ds/query` for Explore)

It is **impossible to modify, create, or delete any Grafana resources** in default mode.

### Write Mode (`mcp-grafana-write`)

When running via `mcp-grafana-write`, additional write operations are enabled:
- **POST** - Save dashboards, create folders, create new alert rules, contact points, mute timings
- **PUT** - Update existing alert rules, contact points, notification policies, mute timings, templates
- **DELETE** - Remove alert rules, contact points, notification policies, mute timings, templates

> **Warning:** The write command enables destructive operations. Only use it when you need write-capable Grafana access. The API key or deprecated session fallback must have the Grafana permissions required by the endpoints you plan to call.

### Additional Security Considerations

1. **Credentials are sensitive** - Never commit real credentials or your local `connections.yaml` to version control
2. **Automatic fallback refresh** - Deprecated session tokens are automatically captured and persisted when Grafana rotates them (API keys are static)
3. **Permission scope** - The server inherits the read permissions of the provided API key or deprecated session fallback
4. **Prefer local-only secret storage** - Keep secrets in local `connections.yaml`, MCP-injected env, or the rotated `session_tokens.json` cache, never in source-controlled config

## Troubleshooting

### Session Token Management

Session tokens are deprecated and should be used only as a temporary fallback.

**Automatic Token Refresh**: Grafana rotates session tokens every 10 minutes. When you are using the deprecated session-cookie fallback, the server automatically:
- Captures refreshed tokens from Grafana API response headers
- Updates tokens in memory immediately
- Persists new tokens back to `session_tokens.json`
- Reuses those rotated tokens on later requests

If you manually need to update a fallback session token:
1. Update the `session_token` in `connections.yaml` or the `GRAFANA_SESSION_*` value in your MCP client env/current shell
2. Also remove or update the cached value in `session_tokens.json` if one was already persisted
3. No restart is needed once the active credential source has been updated

### Authentication Failed

If you get authentication errors despite automatic refresh:
1. Prefer switching to an API key if you are still using the deprecated session fallback
2. Verify the current token or API key is valid in `connections.yaml`, your current environment, or `session_tokens.json`
3. Check that the state directory is writable (needed for automatic token persistence)
4. Ensure the environment variable name matches the connection name (e.g., `GRAFANA_SESSION_PRODUCTION_GRAFANA` for `connection_name: production_grafana`)

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
uv run black src/mcp_read_only_grafana/
uv run ruff check src/mcp_read_only_grafana/ tests/
uv run mcp-read-only-grafana validate-config
uv run mcp-read-only-grafana test-connection
```

## License

MIT License - See LICENSE file for details
