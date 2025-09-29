import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, field_validator


class GrafanaConnection(BaseModel):
    """Configuration for a single Grafana connection"""
    connection_name: str = Field(..., description="Unique identifier for this connection")
    url: HttpUrl = Field(..., description="Grafana instance URL")
    description: str = Field("", description="Description of this Grafana instance")
    timeout: int = Field(30, description="Request timeout in seconds")
    verify_ssl: bool = Field(True, description="Verify SSL certificates")
    session_token: Optional[str] = Field(None, description="Grafana session token")

    @field_validator('connection_name')
    def validate_connection_name(cls, v):
        """Ensure connection name is valid for environment variable naming"""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Connection name must contain only letters, numbers, underscores, and hyphens")
        return v

    @field_validator('url')
    def remove_trailing_slash(cls, v):
        """Remove trailing slash from URL if present"""
        url_str = str(v)
        return url_str.rstrip('/')

    def get_env_var_name(self) -> str:
        """Get the environment variable name for this connection's session token"""
        return f"GRAFANA_SESSION_{self.connection_name.upper().replace('-', '_')}"

    def reload_session_token(self) -> str:
        """Reload session token from .env file and return it"""
        load_dotenv(override=True)
        env_var_name = self.get_env_var_name()
        session_token = os.getenv(env_var_name)

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{self.connection_name}'. "
                f"Please set environment variable: {env_var_name}"
            )

        self.session_token = session_token
        return session_token

    def update_session_token(self, new_token: str, persist: bool = True) -> None:
        """
        Update session token in memory and optionally persist to .env file

        Args:
            new_token: New session token value
            persist: If True, write the new token back to .env file
        """
        self.session_token = new_token

        if persist:
            self._persist_token_to_env(new_token)

    def _persist_token_to_env(self, new_token: str) -> None:
        """Write updated token back to .env file"""
        env_var_name = self.get_env_var_name()
        env_file = Path(".env")

        if not env_file.exists():
            return

        # Read current .env content
        lines = env_file.read_text().splitlines()
        updated = False

        # Update the specific token line
        for i, line in enumerate(lines):
            if line.startswith(f"{env_var_name}="):
                lines[i] = f"{env_var_name}={new_token}"
                updated = True
                break

        # Write back if updated
        if updated:
            env_file.write_text("\n".join(lines) + "\n")


class ConfigParser:
    """Parser for Grafana connections configuration"""

    def __init__(self, config_path: str = "connections.yaml"):
        self.config_path = Path(config_path)

    def load_config(self) -> List[GrafanaConnection]:
        """Load and parse connection configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            raw_config = yaml.safe_load(f) or []

        connections = []
        for conn_data in raw_config:
            connection = self._process_connection(conn_data)
            connections.append(connection)

        return connections

    def _process_connection(self, conn_data: Dict[str, Any]) -> GrafanaConnection:
        """Process a single connection configuration"""
        # Load .env at startup
        load_dotenv()

        # Create connection model
        connection = GrafanaConnection(**conn_data)

        # Load session token from environment
        env_var_name = connection.get_env_var_name()
        session_token = os.getenv(env_var_name)

        if not session_token:
            raise ValueError(
                f"Missing session token for connection '{connection.connection_name}'. "
                f"Please set environment variable: {env_var_name}"
            )

        connection.session_token = session_token

        # Load optional timeout override from environment
        timeout_env_var = f"GRAFANA_TIMEOUT_{connection.connection_name.upper().replace('-', '_')}"
        timeout_override = os.getenv(timeout_env_var)
        if timeout_override:
            try:
                connection.timeout = int(timeout_override)
            except ValueError:
                pass  # Keep default if invalid

        return connection