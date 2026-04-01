"""Tests for configuration parsing"""

import pytest
import tempfile
from pathlib import Path
from mcp_read_only_grafana.config import ConfigParser, GrafanaConnection


def test_connection_name_validation():
    """Test connection name validation"""
    # Valid names
    valid_names = ["prod", "prod_grafana", "grafana-ha", "grafana123"]
    for name in valid_names:
        conn = GrafanaConnection(
            connection_name=name,
            url="https://example.com",
        )
        assert conn.connection_name == name

    # Invalid names
    invalid_names = ["prod@grafana", "grafana!", "test grafana"]
    for name in invalid_names:
        with pytest.raises(ValueError):
            GrafanaConnection(
                connection_name=name,
                url="https://example.com",
            )


def test_env_var_name_generation():
    """Test environment variable name generation"""
    test_cases = [
        ("production", "GRAFANA_SESSION_PRODUCTION"),
        ("prod-grafana", "GRAFANA_SESSION_PROD_GRAFANA"),
        ("grafana-ha", "GRAFANA_SESSION_GRAFANA_HA"),
        ("grafana_test", "GRAFANA_SESSION_GRAFANA_TEST"),
    ]

    for conn_name, expected_env_var in test_cases:
        conn = GrafanaConnection(
            connection_name=conn_name,
            url="https://example.com",
        )
        assert conn.get_env_var_name() == expected_env_var
        assert conn.get_api_key_env_var_name() == expected_env_var.replace(
            "SESSION", "API_KEY"
        )


def test_url_trailing_slash_removed():
    """Test that trailing slashes are removed from URLs"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com/",
    )
    assert str(conn.url) == "https://grafana.example.com"


def test_config_parser_valid_yaml():
    """Test parsing valid YAML configuration"""
    yaml_content = """
- connection_name: test_grafana
  url: https://grafana.example.com
  description: Test instance
  timeout: 60
  verify_ssl: false
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        # Set environment variable for the test
        import os

        os.environ["GRAFANA_SESSION_TEST_GRAFANA"] = "test_token_123"
        os.environ["GRAFANA_API_KEY_TEST_GRAFANA"] = "api_key_abc"

        parser = ConfigParser(config_path)
        connections = parser.load_config()

        assert len(connections) == 1
        conn = connections[0]
        assert conn.connection_name == "test_grafana"
        assert str(conn.url) == "https://grafana.example.com"
        assert conn.description == "Test instance"
        assert conn.timeout == 60
        assert conn.verify_ssl is False
        assert conn.session_token == "test_token_123"
        # API key takes precedence for storage but both values should be loaded
        assert conn.api_key == "api_key_abc"

        # Cleanup
        del os.environ["GRAFANA_SESSION_TEST_GRAFANA"]
        del os.environ["GRAFANA_API_KEY_TEST_GRAFANA"]
    finally:
        Path(config_path).unlink()


def test_config_parser_missing_env_var():
    """Test that missing environment variables raise error when no credentials provided"""
    yaml_content = """
- connection_name: test_grafana
  url: https://grafana.example.com
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        import os

        # Make sure env var doesn't exist
        os.environ.pop("GRAFANA_SESSION_TEST_GRAFANA", None)
        os.environ.pop("GRAFANA_API_KEY_TEST_GRAFANA", None)

        parser = ConfigParser(config_path)
        with pytest.raises(ValueError, match="Missing credentials"):
            parser.load_config()
    finally:
        Path(config_path).unlink()


def test_config_parser_api_key_only():
    """Test parsing config when only API key is provided"""
    yaml_content = """
- connection_name: test_grafana
  url: https://grafana.example.com
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        import os

        os.environ.pop("GRAFANA_SESSION_TEST_GRAFANA", None)
        os.environ["GRAFANA_API_KEY_TEST_GRAFANA"] = "only_api_key"

        parser = ConfigParser(config_path)
        connections = parser.load_config()

        assert len(connections) == 1
        conn = connections[0]
        assert conn.session_token is None
        assert conn.api_key == "only_api_key"
    finally:
        os.environ.pop("GRAFANA_API_KEY_TEST_GRAFANA", None)
        Path(config_path).unlink()


def test_config_parser_yaml_credentials_without_env():
    """YAML-declared credentials should be accepted without env vars."""
    yaml_content = """
- connection_name: test_grafana
  url: https://grafana.example.com
  session_token: yaml_session_token
  api_key: yaml_api_key
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        parser = ConfigParser(config_path, runtime_env_provider=lambda: {})
        [conn] = parser.load_config()

        assert conn.session_token == "yaml_session_token"
        assert conn.api_key == "yaml_api_key"
    finally:
        Path(config_path).unlink()


def test_config_parser_runtime_env_overrides_yaml_credentials():
    """Runtime env should override YAML defaults when both are present."""
    yaml_content = """
- connection_name: test_grafana
  url: https://grafana.example.com
  session_token: yaml_session_token
  api_key: yaml_api_key
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        config_path = f.name

    try:
        parser = ConfigParser(
            config_path,
            runtime_env_provider=lambda: {
                "GRAFANA_SESSION_TEST_GRAFANA": "runtime_session_token",
                "GRAFANA_API_KEY_TEST_GRAFANA": "runtime_api_key",
            },
        )
        [conn] = parser.load_config()

        assert conn.session_token == "runtime_session_token"
        assert conn.api_key == "runtime_api_key"
    finally:
        Path(config_path).unlink()


def test_config_parser_missing_file():
    """Test that missing config file raises FileNotFoundError"""
    parser = ConfigParser("nonexistent.yaml")
    with pytest.raises(FileNotFoundError):
        parser.load_config()


def test_default_values():
    """Test default configuration values"""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://example.com",
    )
    assert conn.description == ""
    assert conn.timeout == 30
    assert conn.verify_ssl is True
    assert conn.session_token is None
    assert conn.api_key is None


def test_direct_connection_reload_uses_runtime_environment(monkeypatch):
    """Direct GrafanaConnection instances should read credentials from os.environ."""
    monkeypatch.setenv("GRAFANA_SESSION_TEST", "runtime-session")
    monkeypatch.setenv("GRAFANA_API_KEY_TEST", "runtime-api-key")

    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
    )

    assert conn.reload_session_token() == "runtime-session"
    assert conn.reload_api_key() == "runtime-api-key"


def test_direct_connection_reload_uses_configured_credentials_without_env():
    """Direct GrafanaConnection instances should fall back to configured credentials."""
    conn = GrafanaConnection(
        connection_name="test",
        url="https://grafana.example.com",
        session_token="configured-session",
        api_key="configured-api-key",
    )

    assert conn.reload_session_token() == "configured-session"
    assert conn.reload_api_key() == "configured-api-key"
