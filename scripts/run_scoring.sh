#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/run_common.sh"

enter_project_root
load_project_env
VENV_PYTHON="$(resolve_venv_python)"

"$VENV_PYTHON" -m services.scoring.main
