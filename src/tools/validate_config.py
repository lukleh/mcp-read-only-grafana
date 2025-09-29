#!/usr/bin/env python3
"""Validate Grafana connections configuration"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import ConfigParser


def validate_config(config_path: str) -> bool:
    """Validate configuration file"""
    try:
        parser = ConfigParser(config_path)
        connections = parser.load_config()

        if not connections:
            print("❌ No connections found in configuration")
            return False

        print(f"✅ Configuration is valid")
        print(f"Found {len(connections)} connection(s):\n")

        for conn in connections:
            print(f"  ✓ {conn.connection_name}")
            print(f"    URL: {conn.url}")
            print(f"    Description: {conn.description}")
            print(f"    Timeout: {conn.timeout}s")
            print(f"    Verify SSL: {conn.verify_ssl}")
            env_var = conn.get_env_var_name()
            print(f"    Environment variable: {env_var}")
            print()

        return True

    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        return False
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Validate MCP Grafana Server configuration")
    parser.add_argument(
        "config",
        nargs="?",
        default="connections.yaml",
        help="Path to configuration file (default: connections.yaml)"
    )

    args = parser.parse_args()

    success = validate_config(args.config)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()