import os
import tempfile
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, HttpUrl, PrivateAttr, field_validator


def _copy_runtime_env() -> dict[str, str]:
    return dict(os.environ)


def _read_state_file(state_path: Path | None) -> dict[str, str]:
    if state_path is None or not state_path.exists():
        return {}

    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw_data, dict):
        raise ValueError(f"State file must contain a JSON object: {state_path}")

    return {
        key: value
        for key, value in raw_data.items()
        if isinstance(key, str) and isinstance(value, str)
    }


def _merge_credential_sources(
    state_path: Path | None,
    runtime_env: Mapping[str, str] | None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    if runtime_env:
        merged.update(runtime_env)
    merged.update(_read_state_file(state_path))
    return merged


def _persist_state_value(state_path: Path, key: str, new_value: str) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)

    current_values = _read_state_file(state_path) if state_path.exists() else {}
    current_values[key] = new_value

    temp_fd, temp_path = tempfile.mkstemp(
        dir=state_path.parent,
        prefix=f".{state_path.name}_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as handle:
            json.dump(current_values, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_path, state_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


class GrafanaConnection(BaseModel):
    """Configuration for a single Grafana connection."""

    connection_name: str = Field(
        ..., description="Unique identifier for this connection"
    )
    url: HttpUrl = Field(..., description="Grafana instance URL")
    description: str = Field("", description="Description of this Grafana instance")
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    session_token: str | None = Field(
        None,
        description="Deprecated Grafana session token fallback",
    )
    api_key: str | None = Field(
        None,
        description="Preferred Grafana API key (Bearer token)",
    )

    _state_path: Path | None = PrivateAttr(default=None)
    _configured_session_token: str | None = PrivateAttr(default=None)
    _configured_api_key: str | None = PrivateAttr(default=None)
    _runtime_env_provider: Callable[[], Mapping[str, str]] = PrivateAttr(
        default_factory=lambda: _copy_runtime_env
    )

    def model_post_init(self, __context: Any) -> None:
        """Preserve credentials explicitly declared in the YAML config."""
        self._configured_session_token = self.session_token
        self._configured_api_key = self.api_key

    @field_validator("connection_name")
    @classmethod
    def validate_connection_name(cls, value: str) -> str:
        """Ensure connection name is valid for environment variable naming."""
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Connection name must contain only letters, numbers, underscores, and hyphens"
            )
        return value

    @field_validator("url")
    @classmethod
    def remove_trailing_slash(cls, value: HttpUrl) -> str:
        """Remove trailing slash from URL if present."""
        return str(value).rstrip("/")

    def configure_credential_sources(
        self,
        state_path: Path | None,
        runtime_env_provider: Callable[[], Mapping[str, str]] | None = None,
    ) -> None:
        self._state_path = state_path
        if runtime_env_provider is not None:
            self._runtime_env_provider = runtime_env_provider

    def get_env_var_name(self) -> str:
        return f"GRAFANA_SESSION_{self.connection_name.upper().replace('-', '_')}"

    def get_api_key_env_var_name(self) -> str:
        return f"GRAFANA_API_KEY_{self.connection_name.upper().replace('-', '_')}"

    def get_timeout_env_var_name(self) -> str:
        return f"GRAFANA_TIMEOUT_{self.connection_name.upper().replace('-', '_')}"

    def _load_credential_values(self) -> dict[str, str]:
        configured_values: dict[str, str] = {}
        if self._configured_session_token:
            configured_values[self.get_env_var_name()] = self._configured_session_token
        if self._configured_api_key:
            configured_values[self.get_api_key_env_var_name()] = (
                self._configured_api_key
            )

        merged = configured_values
        runtime_env = self._runtime_env_provider()
        if runtime_env:
            merged.update(runtime_env)
        merged.update(_read_state_file(self._state_path))
        return merged

    def reload_session_token(self) -> str:
        """Reload deprecated session-token fallback from YAML, env, and state."""
        session_token = self._load_credential_values().get(self.get_env_var_name())
        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{self.connection_name}'. "
                f"Please provide {self.get_env_var_name()} in the environment "
                "or set session_token in connections.yaml."
            )
        self.session_token = session_token
        return session_token

    def reload_api_key(self) -> str:
        """Reload preferred API key from YAML config, env, and state."""
        api_key = self._load_credential_values().get(self.get_api_key_env_var_name())
        if not api_key:
            raise ValueError(
                f"Missing API key for connection '{self.connection_name}'. "
                f"Please provide {self.get_api_key_env_var_name()} in the "
                "environment or set api_key in connections.yaml."
            )
        self.api_key = api_key
        return api_key

    def update_session_token(self, new_token: str, persist: bool = True) -> None:
        """Update session token in memory and optionally persist to cached state."""
        self.session_token = new_token
        if persist:
            self._persist_token_to_state(new_token)

    def _persist_token_to_state(self, new_token: str) -> None:
        state_path = self._state_path
        if state_path is None:
            return
        _persist_state_value(state_path, self.get_env_var_name(), new_token)


class ConfigParser:
    """Parser for Grafana connections configuration."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        state_path: str | Path | None = None,
        runtime_env_provider: Callable[[], Mapping[str, str]] | None = None,
    ):
        self.config_path = Path(config_path).expanduser()
        self.state_path = Path(state_path).expanduser() if state_path else None
        self.runtime_env_provider = runtime_env_provider or _copy_runtime_env

    def load_config(self) -> list[GrafanaConnection]:
        """Load and parse connection configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with self.config_path.open("r", encoding="utf-8") as handle:
            raw_config = yaml.safe_load(handle) or []

        return [self._process_connection(conn_data) for conn_data in raw_config]

    def _process_connection(self, conn_data: dict[str, Any]) -> GrafanaConnection:
        """Process a single connection configuration."""
        connection = GrafanaConnection(**conn_data)
        connection.configure_credential_sources(
            self.state_path,
            self.runtime_env_provider,
        )

        env_values = connection._load_credential_values()
        session_token = env_values.get(connection.get_env_var_name())
        api_key = env_values.get(connection.get_api_key_env_var_name())

        if session_token:
            connection.session_token = session_token
        if api_key:
            connection.api_key = api_key

        if not (session_token or api_key):
            raise ValueError(
                f"Missing credentials for connection '{connection.connection_name}'. "
                f"Please set {connection.get_env_var_name()} or "
                f"{connection.get_api_key_env_var_name()} in the environment, "
                "or configure session_token/api_key in connections.yaml."
            )

        timeout_override = env_values.get(connection.get_timeout_env_var_name())
        if timeout_override:
            try:
                connection.timeout = int(timeout_override)
            except ValueError:
                pass

        return connection
