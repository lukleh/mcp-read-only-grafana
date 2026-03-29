#!/usr/bin/env python3
"""Test Grafana connections."""

import asyncio
import sys
from typing import Optional

from ..config import ConfigParser
from ..grafana_connector import GrafanaConnector
from ..runtime_paths import RuntimePaths, resolve_runtime_paths


async def test_connection(
    runtime_paths: RuntimePaths,
    connection_name: Optional[str] = None,
) -> bool:
    """Test Grafana connection(s)."""
    try:
        parser = ConfigParser(
            runtime_paths.connections_file,
            state_path=runtime_paths.state_file,
        )
        connections = parser.load_config()

        if not connections:
            print("❌ No connections found in configuration")
            return False

        if connection_name:
            connections = [
                connection
                for connection in connections
                if connection.connection_name == connection_name
            ]
            if not connections:
                print(f"❌ Connection not found: {connection_name}")
                print("Available connections:")
                parser_again = ConfigParser(
                    runtime_paths.connections_file,
                    state_path=runtime_paths.state_file,
                )
                all_connections = parser_again.load_config()
                for connection in all_connections:
                    print(f"  - {connection.connection_name}")
                return False

        all_success = True

        for connection in connections:
            print(f"Testing connection: {connection.connection_name}")
            print(f"  URL: {connection.url}")
            print(f"  Description: {connection.description}")

            connector = GrafanaConnector(connection)

            try:
                print("  Testing connection...")
                health = await connector.get_health()

                print("  ✅ Connected successfully")

                if "version" in health:
                    print(f"  Grafana version: {health['version']}")
                if "database" in health:
                    print(f"  Database: {health['database']}")

            except Exception as exc:
                error_msg = str(exc)
                if (
                    "authentication failed" in error_msg.lower()
                    or "session may have expired" in error_msg.lower()
                ):
                    print(
                        "  ❌ Authentication failed - check MCP-injected env or cached session state"
                    )
                    print(f"     Session variable: {connection.get_env_var_name()}")
                    print(
                        f"     API key variable: {connection.get_api_key_env_var_name()}"
                    )
                elif "permission denied" in error_msg.lower():
                    print("  ❌ Permission denied - user may lack read permissions")
                elif "timed out" in error_msg.lower():
                    print("  ❌ Connection timeout - check network or timeout settings")
                elif (
                    "connection" in error_msg.lower() or "connect" in error_msg.lower()
                ):
                    print("  ❌ Cannot connect to server - check URL")
                else:
                    print(f"  ❌ Connection failed: {error_msg[:200]}")
                all_success = False
            finally:
                await connector.close()

            print()

        return all_success

    except FileNotFoundError:
        print(f"❌ Configuration file not found: {runtime_paths.connections_file}")
        return False
    except Exception as exc:
        print(f"❌ Error: {exc}")
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="mcp-read-only-grafana test-connection",
        description="Test MCP Grafana Server connections",
    )
    parser.add_argument(
        "connection",
        nargs="?",
        help="Specific connection name to test (tests all if not specified)",
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

    success = asyncio.run(test_connection(runtime_paths, args.connection))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
