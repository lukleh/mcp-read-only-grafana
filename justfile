# MCP Read-Only Grafana Server
set dotenv-load

# Show available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Run the server
run config="connections.yaml":
    uv run -- python -m src.server {{config}}

# Validate configuration file
validate config="connections.yaml":
    uv run -- python -m src.tools.validate_config {{config}}

# Test Grafana connection(s)
test-connection connection="":
    #!/usr/bin/env bash
    if [ -z "{{connection}}" ]; then
        uv run -- python -m src.tools.test_connection
    else
        uv run -- python -m src.tools.test_connection {{connection}}
    fi

# Run linter
lint:
    uv run ruff check src/

# Auto-fix linting issues
lint-fix:
    uv run ruff check --fix src/

# Format code
format:
    uv run black src/

# Run tests
test:
    uv run pytest