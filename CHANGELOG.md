# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Root CLI subcommands for `mcp-read-only-grafana validate-config` and `mcp-read-only-grafana test-connection`.

### Changed

- Standardized maintainer and smoke-test paths on the single public root command.

## [0.1.0] - 2026-03-29

### Added

- Initial PyPI release for `uvx mcp-read-only-grafana`.
- Canonical `src/mcp_read_only_grafana` package layout and metadata-backed `__version__`.
- Package-native bootstrap commands for `--write-sample-config`, `--overwrite`, and `--print-paths`.
- Optional admin mode with `--allow-admin` for provisioning endpoints.
- Trusted PyPI publishing with a gated GitHub Actions release workflow and manual `pypi` approval.

### Fixed

- Packaged bootstrap now writes both `connections.yaml` and `connections.schema.json` for editor schema support.
