#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir"

if [[ ! -f .venv/bin/activate ]]; then
    uv sync
fi
source .venv/bin/activate

exec uv run drive-tui.py -c sqlite "$@"
