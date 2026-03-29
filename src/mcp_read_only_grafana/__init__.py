from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-read-only-grafana")
except PackageNotFoundError:
    __version__ = "0+unknown"
