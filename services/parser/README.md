# Parser Service


## docker compose -f docker-compose.parser.yml up --build -d
command for run parser-service with docker(with redis)

## What Changed
- API server no longer executes parsing inside `BackgroundTasks`.
- Parsing is now executed by Celery workers through Redis queue.
- `POST /parse` returns queue identifiers (`task_id`) immediately.

## Why This Is Standard
- API stays responsive under parallel uploads.
- Heavy jobs are isolated from HTTP request lifecycle.
- Workers can be scaled independently from the FastAPI app.

## Task ID
- Every queued job receives a unique `task_id` (UUID from Celery).
- Use `task_id` to poll execution status and final result.

## Endpoints
- `POST /parse`
  - Body:
    - `user_id` (required)
    - `file_id` (optional)
    - `github_url` (optional)
  - At least one of `file_id` or `github_url` must be provided.
  - Response includes `github_task_id` and/or `file_task_id`.
- `GET /parse/tasks/{task_id}`
  - Returns Celery status: `PENDING`, `STARTED`, `SUCCESS`, `FAILURE`.
  - On `SUCCESS` includes `result`.
  - On `FAILURE` includes `error`.

## Retry / Rate Limit Handling
- GitHub fetch uses `tenacity`.
- Automatic retry is enabled for temporary failures:
  - `429`
  - rate-limited `403` (`X-RateLimit-Remaining=0`)
  - `5xx`

## Run Locally
1. Install parser dependencies:
   - `pip install -r services/parser/requirements.txt`
2. Install Docker Desktop and make sure daemon is running.
3. Start API:
   - `bash scripts/run_parser.sh`
4. Start worker:
   - `bash scripts/run_parser_worker.sh`

## Run With Docker (Recommended)
This mode starts only parser components (`parser-api`, `parser-worker`, `parser-redis`).

1. Build and start:
   - `docker compose -f docker-compose.parser.yml up --build -d`
   - or shortcut: `bash scripts/run_parser_stack.sh`
2. Check status:
   - `docker compose -f docker-compose.parser.yml ps`
3. Check logs:
   - `docker compose -f docker-compose.parser.yml logs -f parser-api`
   - `docker compose -f docker-compose.parser.yml logs -f parser-worker`
4. Stop:
   - `docker compose -f docker-compose.parser.yml down`
   - or shortcut: `bash scripts/stop_parser_stack.sh`

If you want to remove Redis persisted volume too:
- `docker compose -f docker-compose.parser.yml down -v`

## Redis Startup Behavior
- `run_parser.sh` and `run_parser_worker.sh` auto-manage local Redis in Docker.
- If Redis container exists, script starts it.
- If container is missing, script creates it.
- If broker URL points to non-local Redis, docker autostart is skipped.

## Optional Env
- `PARSER_CELERY_BROKER_URL` (default: `redis://localhost:6379/0`)
- `PARSER_CELERY_RESULT_BACKEND` (default: same as broker)
- `PARSER_REDIS_CONTAINER_NAME` (default: `juldyz-parser-redis`)
- `PARSER_REDIS_IMAGE` (default: `redis:7-alpine`)

## Notes For Next Developer
- Parser output is still file-based JSON in `data/users/<user_id>/...`.
- `parse_file_task` currently writes a placeholder payload (`pending_llm_integration`).
- When real PDF parsing is added, keep it inside Celery tasks, not in FastAPI handlers.
