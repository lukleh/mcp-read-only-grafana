from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ORG_NAMESPACE = "lukleh"
APP_NAME = "mcp-read-only-grafana"
ENV_PREFIX = "MCP_READ_ONLY_GRAFANA"


@dataclass(frozen=True)
class RuntimePaths:
    config_dir: Path
    state_dir: Path
    cache_dir: Path

    @property
    def connections_file(self) -> Path:
        return self.config_dir / "connections.yaml"

    @property
    def secrets_file(self) -> Path:
        return self.config_dir / "secrets.env"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.env"

    def ensure_directories(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def render(self) -> str:
        return "\n".join(
            [
                f"config_dir={self.config_dir}",
                f"state_dir={self.state_dir}",
                f"cache_dir={self.cache_dir}",
                f"connections_file={self.connections_file}",
                f"secrets_file={self.secrets_file}",
                f"state_file={self.state_file}",
            ]
        )


def _expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def _default_config_dir() -> Path:
    return Path.home() / ".config" / ORG_NAMESPACE / APP_NAME


def _default_state_dir() -> Path:
    return Path.home() / ".local" / "state" / ORG_NAMESPACE / APP_NAME


def _default_cache_dir() -> Path:
    return Path.home() / ".cache" / ORG_NAMESPACE / APP_NAME


def resolve_runtime_paths(
    config_dir: str | Path | None = None,
    state_dir: str | Path | None = None,
    cache_dir: str | Path | None = None,
) -> RuntimePaths:
    resolved_config_dir = _expand_path(
        config_dir
        or os.getenv(f"{ENV_PREFIX}_CONFIG_DIR")
        or _default_config_dir()
    )
    resolved_state_dir = _expand_path(
        state_dir
        or os.getenv(f"{ENV_PREFIX}_STATE_DIR")
        or _default_state_dir()
    )
    resolved_cache_dir = _expand_path(
        cache_dir
        or os.getenv(f"{ENV_PREFIX}_CACHE_DIR")
        or _default_cache_dir()
    )

    return RuntimePaths(
        config_dir=resolved_config_dir,
        state_dir=resolved_state_dir,
        cache_dir=resolved_cache_dir,
    )
