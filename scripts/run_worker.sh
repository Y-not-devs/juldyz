#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# shellcheck disable=SC1091
source "$SCRIPT_DIR/celery_common.sh"

enter_project_root
load_celery_env
VENV_PYTHON="$(resolve_venv_python)"

"$VENV_PYTHON" -m celery -A core.celery_app:celery worker --loglevel=info -Q parser,llm
