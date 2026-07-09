#!/usr/bin/env bash
# Launch route-finder on macOS.
# Usage: scripts/run.sh [width height]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHONPATH="src" python3 -m route_finder "$@"
