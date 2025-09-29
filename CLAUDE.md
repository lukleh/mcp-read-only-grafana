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

# Code formatting
uv run black src/
uv run ruff check src/

# Run tests
uv run pytest
```

## Architecture

### Core Components

**src/server.py** - MCP server implementation using FastMCP
- `ReadOnlyGrafanaServer` class manages connections and defines MCP tools
- All tool functions are decorated with `@self.mcp.tool()`
- Error handling: Let exceptions propagate naturally - the MCP framework handles them
- Connection validation: Raise `ValueError` for invalid connection names with available options

**src/config.py** - Configuration management
- `GrafanaConnection` (Pydantic model): Validates connection settings
- `ConfigParser`: Loads connections from YAML and environment variables
- Session token pattern: `GRAFANA_SESSION_<CONNECTION_NAME>` (uppercase, hyphens→underscores)
- **Dynamic token reloading**: `reload_session_token()` reloads .env on every call

**src/grafana_connector.py** - Grafana API client
- `GrafanaConnector` wraps httpx for Grafana API calls
- **Critical**: `_get()` calls `connection.reload_session_token()` before EVERY request
- This allows updating session tokens in .env without restarting the server
- All API methods return formatted dictionaries/lists, not raw responses

### Configuration Flow

1. `ConfigParser.load_config()` reads `connections.yaml`
2. For each connection, `_process_connection()` creates a `GrafanaConnection`
3. Session tokens are loaded from environment variables at startup
4. On each API request, `reload_session_token()` re-reads .env to get fresh tokens

### Error Handling Pattern

Following the mcp-read-only-sql pattern:
- Tool functions raise exceptions (ValueError for connection not found)
- Do NOT catch exceptions and return JSON error objects
- The MCP framework automatically converts exceptions to proper error responses
- This is cleaner and more consistent than manual error handling

### Authentication

Session-based authentication using Grafana session cookies:
- Tokens stored in .env file (never in code or YAML)
- Tokens are reloaded from .env before each request to support token rotation
- Connection name in YAML maps to `GRAFANA_SESSION_<NAME>` in environment

## Key Design Decisions

1. **Read-only by design**: Only GET requests are performed
2. **Session token reload**: Tokens are reloaded from .env on every request to handle expiration gracefully
3. **No credential storage**: Tokens only in environment variables, never in config files
4. **Multiple instance support**: Each connection has its own connector with independent configuration
5. **MCP error handling**: Let exceptions propagate; framework handles them properly