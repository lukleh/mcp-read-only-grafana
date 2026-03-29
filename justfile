# MCP Read-Only Grafana Server
# Show available commands
default:
    @just --list

# Install dependencies
install:
    uv sync --extra dev

# Run the server
run:
    @uv run mcp-read-only-grafana

# Run the server with admin endpoints enabled
run-admin:
    @uv run mcp-read-only-grafana --allow-admin

# Validate configuration file
validate:
    uv run python -m mcp_read_only_grafana.tools.validate_config

# Show resolved paths
print-paths:
    uv run mcp-read-only-grafana --print-paths

# Write the default sample config
write-sample-config:
    uv run mcp-read-only-grafana --write-sample-config

# Test Grafana connection(s)
test-connection connection="":
    #!/usr/bin/env bash
    if [ -z "{{connection}}" ]; then
        uv run python -m mcp_read_only_grafana.tools.test_connection
    else
        uv run python -m mcp_read_only_grafana.tools.test_connection {{connection}}
    fi

# Run linter
lint:
    uv run ruff check src/mcp_read_only_grafana/ tests/

# Auto-fix linting issues
lint-fix:
    uv run ruff check --fix src/mcp_read_only_grafana/ tests/

# Format code
format:
    uv run black src/mcp_read_only_grafana/ tests/

# Run tests
test:
    uv run pytest -q
