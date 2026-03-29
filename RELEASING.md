# Releasing `mcp-read-only-grafana`

This project is set up for tag-driven PyPI releases with GitHub Actions and PyPI trusted publishing.

Current package status:
- Not published to PyPI yet

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
- Publish workflow: present on this branch
- GitHub `pypi` environment: not configured yet
- Required reviewer: not configured yet
- Self-review: not configured yet

## Release steps

1. Update `version` in `pyproject.toml`.
2. Commit the release changes to `main`.
3. Create and push a matching version tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

4. GitHub Actions will start the `Publish` workflow.
5. The workflow will:
   - run tests
   - build the wheel and sdist
   - smoke test both artifacts with `uvx`
6. Once those checks pass, the workflow will pause at the `pypi` environment for approval.
7. Approve the deployment in the GitHub Actions UI.
8. After approval, GitHub Actions will publish to PyPI.

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
- The smoke tests exercise the packaged CLI by writing a sample config plus schema and printing runtime paths from the built artifacts.
- Document both read-only mode and `--allow-admin` mode in the public package docs before the first release.
