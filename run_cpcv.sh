#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="/Users/nongo/Documents/Patacon"
exec /Users/nongo/Documents/Patacon/SopaDeOtoe/.venv/bin/python3 -m SopaDeOtoe.launchers.run_cpcv_validation --n-jobs 3 "$@"
