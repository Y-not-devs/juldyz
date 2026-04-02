#!/usr/bin/env bash
set -euo pipefail

# shellcheck disable=SC1091
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_common.sh"

load_parser_env() {
  load_project_env

  # Backward compatibility for old parser-specific env names.
  if [[ -z "${CELERY_BROKER_URL:-}" && -n "${PARSER_CELERY_BROKER_URL:-}" ]]; then
    CELERY_BROKER_URL="$PARSER_CELERY_BROKER_URL"
  fi

  : "${CELERY_BROKER_URL:=redis://localhost:6379/0}"
  : "${CELERY_RESULT_BACKEND:=redis://localhost:6379/1}"
}

