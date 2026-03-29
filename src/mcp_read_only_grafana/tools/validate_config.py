#!/usr/bin/env python3
"""Validate Grafana connections configuration."""

import sys

from ..config import ConfigParser
from ..runtime_paths import RuntimePaths, resolve_runtime_paths


def validate_config(runtime_paths: RuntimePaths) -> bool:
    """Validate configuration file."""
    try:
        parser = ConfigParser(
            runtime_paths.connections_file,
            state_path=runtime_paths.state_file,
        )
        connections = parser.load_config()

        if not connections:
            print("❌ No connections found in configuration")
            return False

        print("✅ Configuration is valid")
        print(f"Found {len(connections)} connection(s):\n")

        for conn in connections:
            print(f"  ✓ {conn.connection_name}")
            print(f"    URL: {conn.url}")
            print(f"    Description: {conn.description}")
            print(f"    Timeout: {conn.timeout}s")
            print(f"    Verify SSL: {conn.verify_ssl}")
            print(f"    Session variable: {conn.get_env_var_name()}")
            print(f"    API key variable: {conn.get_api_key_env_var_name()}")
            print()

        return True

    except FileNotFoundError:
        print(f"❌ Configuration file not found: {runtime_paths.connections_file}")
        return False
    except ValueError as exc:
        print(f"❌ Configuration error: {exc}")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="mcp-read-only-grafana validate-config",
        description="Validate MCP Grafana Server configuration",
    )
    parser.add_argument(
        "--config-dir",
        help="Directory containing connections.yaml",
    )
    parser.add_argument(
        "--state-dir",
        help="Directory containing session_tokens.json",
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory reserved for cache files",
    )
    parser.add_argument(
        "--print-paths",
        action="store_true",
        help="Print resolved config/state/cache paths and exit",
    )

    args = parser.parse_args()
    runtime_paths = resolve_runtime_paths(
        config_dir=args.config_dir,
        state_dir=args.state_dir,
        cache_dir=args.cache_dir,
    )

    if args.print_paths:
        print(runtime_paths.render())
        return

    success = validate_config(runtime_paths)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
