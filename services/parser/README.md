# Parser Service

## Overview
- API server only accepts requests and queues Celery jobs.
- Parsing runs in Celery worker (`parser.parse_file_task`, `parser.parse_github_task`).
- Redis/Celery config is shared from `core` (`core/celery_app.py`, `core/config.py`).

## Local Run (Preferred)
Use the same project `.venv` and root `requirements.txt` as other services.

1. Create and activate virtual environment:
   - `py -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Make sure Redis is already running externally (local service/container/remote host).
   - Example (Linux/macOS): `redis-server`
   - Example (Windows, if Redis installed as service): `redis-server`
4. Set env in `.env`:
   - `CELERY_BROKER_URL=redis://localhost:6379/0`
   - `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
5. Start parser API:
   - Bash: `bash scripts/run_parser.sh`
6. Start worker:
   - Bash: `bash scripts/run_worker.sh`

## Notes
- Docker files/scripts for parser local stack were removed temporarily.
- Celery + Redis are still required and fully supported.

## Endpoints
- `POST /parse`
  - Body:
    - `user_id` (required)
    - `file_id` (optional)
    - `github_url` (optional)
  - At least one of `file_id` or `github_url` is required.
- `GET /parse/tasks/{task_id}`
  - Returns Celery status and result/error.

## Output
- Processed JSON files are stored in:
  - `data/users/<user_id>/processed/processed_<file_id>.json`
  - `data/users/<user_id>/links/<github_id>.json`
