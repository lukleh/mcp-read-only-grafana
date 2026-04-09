# Repository Guidelines

## Project Structure & Module Organization
`src/mcp_read_only_grafana/server.py` boots the MCP server, runtime-path helpers, and root management subcommands. The Grafana API client lives in `grafana_connector.py`; connection parsing and credential precedence live in `config.py`; typed errors are in `exceptions.py`; and validation helpers are in `validation.py`. Tool registration is split by domain under `src/mcp_read_only_grafana/tools/` (`dashboard`, `datasource`, `alert`, `user`, `admin`, plus core helpers). Tests live in `tests/`, and `connections.schema.json` plus `connections.yaml.sample` document the config surface.

## Build, Test, and Development Commands
- `uv sync --extra dev` installs runtime and development dependencies.
- `uv run mcp-read-only-grafana --print-paths` shows the resolved config, state, and cache locations.
- `uv run mcp-read-only-grafana --write-sample-config` writes the default config files; add `--overwrite` only when replacing them intentionally.
- `uv run mcp-read-only-grafana validate-config` validates `connections.yaml` against the packaged schema.
- `uv run mcp-read-only-grafana test-connection` checks all configured connections; pass a connection name to scope it.
- `uv run pytest -q` runs the full test suite.
- `uv run pytest tests/test_server.py -q` is a fast focused iteration loop.
- `RUN_WRITE_TESTS=1 uv run pytest tests/test_integration_all_endpoints.py -v -m integration` runs the write-capable integration coverage.
- `uv run ruff check src/mcp_read_only_grafana tests` lints, `uv run black src/mcp_read_only_grafana tests` formats, and `uv run ty check` type-checks `src/`.

## Coding Style & Naming Conventions
Target Python 3.11+ with four-space indentation, explicit type hints, and concise docstrings when behavior is not obvious. Use `snake_case` for modules, functions, tests, and config keys; use `PascalCase` for classes and Pydantic models. Keep domain logic in the existing tool modules rather than collapsing it back into `server.py`, and preserve the shared connector and validation helpers instead of duplicating request or auth checks.

## Testing Guidelines
Pytest uses `unit` and `integration` markers from `pyproject.toml`. Add or update tests for any change to credential precedence, session refresh, pagination, dashboard traversal, or write-capable endpoint gating. When touching write functionality, keep both the default read-only behavior and the `mcp-grafana-write` path covered, and only rely on `RUN_WRITE_TESTS=1` for cases that truly need privileged live credentials.

## Commit & Pull Request Guidelines
Follow the current history style with short imperative commit subjects and small focused diffs. Pull requests should explain whether the change affects the read-only command, the write command, or both, and should list the exact local commands you ran, including any integration coverage.

## Security & Configuration Tips
Prefer API keys or service-account tokens over the deprecated session-cookie fallback. Do not weaken the separation between the default read-only command and the write-capable command. Treat rotated session state in `~/.local/state/lukleh/mcp-read-only-grafana/session_tokens.json` as sensitive local data.
