#!/usr/bin/env bash
# LAUNCH THE FILE BROWSER WITH THE MEGADISKS CATALOG [
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir"

exec uv run drive-tui.py -d log-megadisks "$@"
# LAUNCH THE FILE BROWSER WITH THE MEGADISKS CATALOG ]
