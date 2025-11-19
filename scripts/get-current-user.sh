#!/usr/bin/env bash

set -euo pipefail

CONNECTION_NAME="${1:-grafana-ha}"
CONNECTIONS_FILE="${CONNECTIONS_FILE:-connections.yaml}"
ENV_FILE="${ENV_FILE:-.env}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -x "$(pwd)/.venv/bin/python" ]]; then
    PYTHON_BIN="$(pwd)/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "python interpreter not found. Set PYTHON_BIN to a valid executable." >&2
    exit 1
  fi
fi

if [[ ! -f "${CONNECTIONS_FILE}" ]]; then
  echo "connections file not found: ${CONNECTIONS_FILE}" >&2
  exit 1
fi

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

upper_name=$(printf '%s' "${CONNECTION_NAME}" | tr '[:lower:]' '[:upper:]')
upper_name="${upper_name//-/_}"
upper_name="${upper_name//./_}"
session_var="GRAFANA_SESSION_${upper_name}"

session_token="${!session_var-}"
if [[ -z "${session_token}" ]]; then
  echo "environment variable ${session_var} is not set" >&2
  exit 1
fi

base_url=$(CONNECTIONS_FILE="${CONNECTIONS_FILE}" CONNECTION_NAME="${CONNECTION_NAME}" "${PYTHON_BIN}" <<'PY'
import os
import sys
from pathlib import Path

connections_file = Path(os.environ["CONNECTIONS_FILE"])
connection_name = os.environ["CONNECTION_NAME"]
candidates = []
if connection_name:
    candidates.append(connection_name)
    alt = connection_name.replace("_", "-")
    if alt not in candidates:
        candidates.append(alt)

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover - handled at runtime
    sys.stderr.write("PyYAML is required to parse connections.yaml. Activate the project venv or set PYTHON_BIN.\n")
    sys.exit(2)

if not connections_file.exists():
    sys.stderr.write(f"connections file not found: {connections_file}\n")
    sys.exit(3)

data = yaml.safe_load(connections_file.read_text()) or []
for candidate in candidates:
    for conn in data:
        if conn.get("connection_name") == candidate:
            print(conn.get("url", "").rstrip("/"))
            sys.exit(0)

sys.stderr.write(
    f"connection '{connection_name}' not found in {connections_file}. Checked aliases: {', '.join(candidates)}\n"
)
sys.exit(4)
PY
)

if [[ -z "${base_url}" ]]; then
  echo "connection '${CONNECTION_NAME}' not found in ${CONNECTIONS_FILE}" >&2
  exit 1
fi

curl -sSf \
  -H "Cookie: grafana_session=${session_token}" \
  "${base_url}/api/user"
