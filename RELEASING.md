# Releasing `mcp-read-only-grafana`

This project is set up for tag-driven PyPI releases with GitHub Actions and PyPI trusted publishing.

Current package status:
- Published to PyPI as `0.1.0`
- Next planned release from current branch: `0.1.5`

## Changelog policy

- Keep upcoming user-visible changes under `## [Unreleased]` in `CHANGELOG.md`.
- On release, move those entries into a dated version section such as `## [0.1.5] - 2026-03-29`.
- Prefer concise bullets grouped under `Added`, `Changed`, and `Fixed`.
- When creating GitHub release notes, reuse the matching `CHANGELOG.md` section instead of writing a second summary from scratch.

## CLI convention

- The public interface starts with the package command: `mcp-read-only-grafana`.
- Repository-facing docs should prefer the root command plus flags, not extra top-level helper scripts.
- This repo uses root subcommands for auxiliary operations:
  - `mcp-read-only-grafana validate-config`
  - `mcp-read-only-grafana test-connection`
- Future auxiliary operations should follow that same pattern rather than introducing new public console entry points.

## One-time PyPI setup

1. In PyPI, add a trusted publisher for this repository.
   For a brand-new package, use the account-level `Publishing` page to create a pending publisher.
   If the project already exists, use the project's `Manage -> Publishing` page instead.
   - Owner: `lukleh`
   - Repository: `mcp-read-only-grafana`
   - Workflow: `publish.yml`
   - Environment: `pypi`
2. In GitHub, create an environment named `pypi`.
3. Add required reviewers to the `pypi` environment if you want a manual approval gate before publishing.

Current repository setup:
- Environment: `pypi`
- Required reviewer: `lukleh`
- Self-review: allowed

## Release steps

1. Update `CHANGELOG.md` for the release.
2. Update `version` in `pyproject.toml`.
3. Commit the release changes to `main`.
4. Create and push a matching version tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

5. GitHub Actions will start the `Publish` workflow.
6. The workflow will:
   - run tests
   - build the wheel and sdist
   - smoke test both artifacts with `uvx`
7. Once those checks pass, the workflow will pause at the `pypi` environment for approval.
8. Approve the deployment in the GitHub Actions UI.
9. After approval, GitHub Actions will publish to PyPI.

## Prereleases

Use a PEP 440 prerelease version in `pyproject.toml`, for example:
- `0.2.0a1`
- `0.2.0b1`
- `0.2.0rc1`

Push the matching tag:

```bash
git tag v0.2.0a1
git push origin v0.2.0a1
```

The same `Publish` workflow and manual approval gate should handle the prerelease.

## Notes

- The publish workflow validates that the Git tag matches `pyproject.toml`.
- The smoke tests exercise the packaged CLI by writing a sample config plus schema, printing runtime paths, and running the root subcommands from the built artifacts.
- Because `prevent_self_review` is currently disabled, `lukleh` can approve their own release.
