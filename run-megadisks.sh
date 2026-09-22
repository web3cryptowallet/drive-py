#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir"

exec "$script_dir/.venv/bin/python" drive-tui.py -d log-megadisks "$@"
