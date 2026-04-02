#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

enter_project_root() {
  cd "$PROJECT_ROOT"
}

load_project_env() {
  if [[ -f "$PROJECT_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_ROOT/.env"
    set +a
  fi
}

resolve_venv_python() {
  local venv_python_win="$PROJECT_ROOT/.venv/Scripts/python.exe"
  local venv_python_posix="$PROJECT_ROOT/.venv/bin/python"

  if [[ -x "$venv_python_win" ]]; then
    printf "%s\n" "$venv_python_win"
    return 0
  fi

  if [[ -x "$venv_python_posix" ]]; then
    printf "%s\n" "$venv_python_posix"
    return 0
  fi

  echo "[scripts] .venv python not found. Create it first: py -m venv .venv"
  exit 1
}
