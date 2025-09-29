#!/usr/bin/env python3
"""Test Grafana connections"""

import sys
import asyncio
from pathlib import Path
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import ConfigParser
from src.grafana_connector import GrafanaConnector


async def test_connection(config_path: str, connection_name: Optional[str] = None) -> bool:
    """Test Grafana connection(s)"""

    try:
        parser = ConfigParser(config_path)
        connections = parser.load_config()

        if not connections:
            print("❌ No connections found in configuration")
            return False

        # Filter to specific connection if requested
        if connection_name:
            connections = [c for c in connections if c.connection_name == connection_name]
            if not connections:
                print(f"❌ Connection not found: {connection_name}")
                print("Available connections:")
                parser_again = ConfigParser(config_path)
                all_conns = parser_again.load_config()
                for conn in all_conns:
                    print(f"  - {conn.connection_name}")
                return False

        all_success = True

        for connection in connections:
            name = connection.connection_name
            url = connection.url

            print(f"Testing connection: {name}")
            print(f"  URL: {url}")
            print(f"  Description: {connection.description}")

            connector = GrafanaConnector(connection)

            try:
                # Test with health check
                print("  Testing connection...")
                health = await connector.get_health()

                print("  ✅ Connected successfully")

                # Show version if available
                if 'version' in health:
                    print(f"  Grafana version: {health['version']}")

                # Show database status if available
                if 'database' in health:
                    print(f"  Database: {health['database']}")

            except Exception as e:
                error_msg = str(e)
                # Clean up error messages
                if "authentication failed" in error_msg.lower() or "session may have expired" in error_msg.lower():
                    print("  ❌ Authentication failed - check session token in .env")
                    env_var = connection.get_env_var_name()
                    print(f"     Environment variable: {env_var}")
                elif "permission denied" in error_msg.lower():
                    print("  ❌ Permission denied - user may lack read permissions")
                elif "timed out" in error_msg.lower():
                    print("  ❌ Connection timeout - check network or timeout settings")
                elif "connection" in error_msg.lower() or "connect" in error_msg.lower():
                    print("  ❌ Cannot connect to server - check URL")
                else:
                    print(f"  ❌ Connection failed: {error_msg[:200]}")
                all_success = False
            finally:
                await connector.close()

            print()

        return all_success

    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Test MCP Grafana Server connections")
    parser.add_argument(
        "connection",
        nargs="?",
        help="Specific connection name to test (tests all if not specified)"
    )
    parser.add_argument(
        "--config",
        default="connections.yaml",
        help="Path to configuration file (default: connections.yaml)"
    )

    args = parser.parse_args()

    success = asyncio.run(test_connection(args.config, args.connection))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()