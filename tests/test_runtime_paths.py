from src.config import ConfigParser
from src.runtime_paths import resolve_runtime_paths


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
    assert runtime_paths.secrets_file == config_dir / "secrets.env"
    assert runtime_paths.state_file == state_dir / "state.env"


def test_config_parser_reads_secrets_and_state_files(tmp_path):
    config_dir = tmp_path / "config"
    state_dir = tmp_path / "state"
    config_dir.mkdir()
    state_dir.mkdir()

    (config_dir / "connections.yaml").write_text(
        "- connection_name: test_grafana\n"
        "  url: https://grafana.example.com\n",
        encoding="utf-8",
    )
    (config_dir / "secrets.env").write_text(
        "GRAFANA_SESSION_TEST_GRAFANA=secret-session\n"
        "GRAFANA_API_KEY_TEST_GRAFANA=secret-api-key\n",
        encoding="utf-8",
    )
    (state_dir / "state.env").write_text(
        "GRAFANA_SESSION_TEST_GRAFANA=state-session\n",
        encoding="utf-8",
    )

    parser = ConfigParser(
        config_dir / "connections.yaml",
        secrets_path=config_dir / "secrets.env",
        state_path=state_dir / "state.env",
    )
    connections = parser.load_config()

    assert len(connections) == 1
    connection = connections[0]
    assert connection.session_token == "state-session"
    assert connection.api_key == "secret-api-key"

    connection.update_session_token("rotated-session", persist=True)

    assert "GRAFANA_SESSION_TEST_GRAFANA=rotated-session" in (
        state_dir / "state.env"
    ).read_text(encoding="utf-8")
