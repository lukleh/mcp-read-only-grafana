from mcp_read_only_grafana.config import ConfigParser
from mcp_read_only_grafana.runtime_paths import resolve_runtime_paths


def test_resolve_runtime_paths_env_overrides(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    cache_dir = tmp_path / "cache"

    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("MCP_READ_ONLY_GRAFANA_CACHE_DIR", str(cache_dir))

    runtime_paths = resolve_runtime_paths()

    assert runtime_paths.config_dir == config_dir
    assert runtime_paths.state_dir == state_dir
    assert runtime_paths.cache_dir == cache_dir
    assert runtime_paths.connections_file == config_dir / "connections.yaml"
    assert runtime_paths.state_file == state_dir / "session_tokens.json"


def test_config_parser_reads_runtime_env_and_state_files(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test_grafana\n" "  url: https://grafana.example.com\n",
        encoding="utf-8",
    )
    (state_dir / "session_tokens.json").write_text(
        '{"GRAFANA_SESSION_TEST_GRAFANA": "state-session"}\n',
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
        runtime_env_provider=lambda: {
            "GRAFANA_SESSION_TEST_GRAFANA": "runtime-session",
            "GRAFANA_API_KEY_TEST_GRAFANA": "runtime-api-key",
        },
    )
    connections = parser.load_config()

    assert len(connections) == 1
    connection = connections[0]
    assert connection.session_token == "state-session"
    assert connection.api_key == "runtime-api-key"

    connection.update_session_token("rotated-session", persist=True)

    assert '"GRAFANA_SESSION_TEST_GRAFANA": "rotated-session"' in (
        state_dir / "session_tokens.json"
    ).read_text(encoding="utf-8")


def test_state_file_overrides_runtime_environment_for_session_token(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test_grafana\n" "  url: https://grafana.example.com\n",
        encoding="utf-8",
    )
    (state_dir / "session_tokens.json").write_text(
        '{"GRAFANA_SESSION_TEST_GRAFANA": "state-session"}\n',
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        state_path=state_dir / "session_tokens.json",
        runtime_env_provider=lambda: {
            "GRAFANA_SESSION_TEST_GRAFANA": "runtime-session",
            "GRAFANA_API_KEY_TEST_GRAFANA": "runtime-api-key",
        },
    )

    [connection] = parser.load_config()

    assert connection.session_token == "state-session"
    assert connection.api_key == "runtime-api-key"
