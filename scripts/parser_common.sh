#!/usr/bin/env bash
set -euo pipefail

load_parser_env() {
  if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source ".env"
    set +a
  fi

  if [[ -z "${CELERY_BROKER_URL:-}" && -n "${PARSER_CELERY_BROKER_URL:-}" ]]; then
    CELERY_BROKER_URL="$PARSER_CELERY_BROKER_URL"
  fi

  : "${CELERY_BROKER_URL:=redis://localhost:6379/0}"
  : "${PARSER_REDIS_CONTAINER_NAME:=juldyz-parser-redis}"
  : "${PARSER_REDIS_IMAGE:=redis:7-alpine}"
}

parse_redis_url() {
  local url="$1"
  local rest hostport host port

  rest="${url#redis://}"
  rest="${rest##*@}"
  hostport="${rest%%/*}"

  if [[ "$hostport" == *":"* ]]; then
    host="${hostport%%:*}"
    port="${hostport##*:}"
  else
    host="$hostport"
    port="6379"
  fi

  printf "%s %s\n" "$host" "$port"
}

ensure_parser_redis() {
  local host port
  read -r host port < <(parse_redis_url "$CELERY_BROKER_URL")

  if [[ "$host" != "localhost" && "$host" != "127.0.0.1" ]]; then
    echo "[parser] Using external Redis at $host:$port (docker autostart skipped)."
    return 0
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "[parser] Docker is required for local Redis autostart. Install Docker or set CELERY_BROKER_URL to external Redis."
    exit 1
  fi

  if ! docker info >/dev/null 2>&1; then
    echo "[parser] Docker daemon is not running. Start Docker Desktop and retry."
    exit 1
  fi

  if docker ps --format '{{.Names}}' | grep -Fxq "$PARSER_REDIS_CONTAINER_NAME"; then
    echo "[parser] Redis container '$PARSER_REDIS_CONTAINER_NAME' is already running."
    return 0
  fi

  if docker ps -a --format '{{.Names}}' | grep -Fxq "$PARSER_REDIS_CONTAINER_NAME"; then
    echo "[parser] Starting existing Redis container '$PARSER_REDIS_CONTAINER_NAME'..."
    docker start "$PARSER_REDIS_CONTAINER_NAME" >/dev/null
  else
    echo "[parser] Creating Redis container '$PARSER_REDIS_CONTAINER_NAME' on localhost:$port..."
    docker run -d \
      --name "$PARSER_REDIS_CONTAINER_NAME" \
      --restart unless-stopped \
      -p "$port:6379" \
      "$PARSER_REDIS_IMAGE" >/dev/null
  fi

  for _ in {1..20}; do
    if docker exec "$PARSER_REDIS_CONTAINER_NAME" redis-cli ping >/dev/null 2>&1; then
      echo "[parser] Redis is ready."
      return 0
    fi
    sleep 0.5
  done

  echo "[parser] Redis container started but health check failed."
  exit 1
}

