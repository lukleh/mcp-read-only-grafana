# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.2] - 2026-04-22

### Changed

- Alert provisioning tools now keep alert rules and rule groups editable in the Grafana UI by default.
- Write-capable alert tools now expose an `editable_in_ui` MCP parameter so callers can opt out of that behavior without dealing with Grafana's raw provenance-header semantics.

## [0.2.1] - 2026-04-22

### Fixed

- Reloaded connections now keep serving the last successful configuration when a config edit is invalid instead of partially mutating reused connectors.
- Reused connectors now clear stale auth state when switching between API key and session-based authentication.
- Retired connectors from replaced or removed connections are now closed after subsequent successful reloads instead of accumulating for the lifetime of the process.

### Changed

- Clarified across maintainer docs that the live packaged runtime config lives at `~/.config/lukleh/mcp-read-only-grafana/connections.yaml`, while `connections.yaml.sample` in the repo is only a sample/source file.
- Removed the hardcoded `grafana-ha` integration-test fixture name and now default to `grafana` with `GRAFANA_TEST_CONNECTION_NAME` as an override.

## [0.2.0] - 2026-04-09

### Added

- Added `mcp-grafana-write` as a separate public command for write-capable Grafana operations while keeping `mcp-read-only-grafana` as the default read-only entrypoint.

### Changed

- This release changes the public CLI flow for write-capable usage.
- Removed the `--allow-writes` and legacy `--allow-admin` flags in favor of command-based mode selection.
- Reworded package metadata and user docs around a read-only default plus a separate write-capable command from the same package.

## [0.1.6] - 2026-04-09

### Added

- Added `save_dashboard` as a write-capable MCP tool for creating or updating Grafana dashboards from raw dashboard JSON.
- Dashboard saves now sync against the live Grafana dashboard revision by UID, reusing the current dashboard `id` and `version` while preserving the existing folder unless explicitly overridden.

### Changed

- Renamed the public write-enablement flag from `--allow-admin` to `--allow-writes`.
- Kept `--allow-admin` as a legacy alias for compatibility while shifting docs and release smoke tests to `--allow-writes`.

## [0.1.5] - 2026-04-03

### Added

- Added `ty` as a supported development check for the packaged `src/` tree.
- Added a repo-specific `AGENTS.md` contributor guide covering layout, commands, admin-mode guardrails, and security expectations.

### Changed

- Tightened dashboard search and folder-list parameter typing in the Grafana connector to keep the `src/` package clean under static analysis.
- Reworked `RELEASING.md` into an evergreen release checklist with explicit validation, tagging, and publish steps.

## [0.1.4] - 2026-04-01

### Changed

- Marked `session_token` as a deprecated fallback across the README, sample config, generated bootstrap config, and JSON schema, and now recommend `api_key` / service-account tokens as the primary auth path.
- Clarified README examples to prefer `uvx mcp-read-only-grafana@latest` in user-facing install and MCP client setup docs.

## [0.1.3] - 2026-04-01

### Added

- Support for storing Grafana `session_token` and `api_key` credentials directly in `connections.yaml`, matching the MCP-owned connection model used by the SQL server.
- Coverage for YAML-backed credentials, environment overrides, and state-file precedence in config/runtime tests.

### Changed

- Configuration validation, sample config, schema, and server-generated bootstrap files now document and surface YAML-provided credentials.

## [0.1.2] - 2026-04-01

### Added

- Root CLI subcommands for `mcp-read-only-grafana validate-config` and `mcp-read-only-grafana test-connection`.

### Changed

- Standardized maintainer and smoke-test paths on the single public root command.

### Fixed

- `get_current_user` now returns a structured `unavailable` result for API-key auth instead of surfacing Grafana's raw `404` response.
- `get_datasource_health` now returns structured `unsupported` or `not_found` results when a datasource plugin does not implement the Grafana health endpoint.

## [0.1.0] - 2026-03-29

### Added

- Initial PyPI release for `uvx mcp-read-only-grafana`.
- Canonical `src/mcp_read_only_grafana` package layout and metadata-backed `__version__`.
- Package-native bootstrap commands for `--write-sample-config`, `--overwrite`, and `--print-paths`.
- Optional admin mode with `--allow-admin` for provisioning endpoints.
- Trusted PyPI publishing with a gated GitHub Actions release workflow and manual `pypi` approval.

### Fixed

- Packaged bootstrap now writes both `connections.yaml` and `connections.schema.json` for editor schema support.
