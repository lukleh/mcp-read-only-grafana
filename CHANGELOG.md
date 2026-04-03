# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
