# Parser Service

## Overview
- API server executes parser jobs directly in-process (no queue/broker required).
- Parser tasks remain reusable (`parser.parse_file_task`, `parser.parse_github_task`, `parser.parse_video_task`) and are called synchronously.
- `/parse/tasks/{task_id}` is kept only for backward compatibility and returns unavailable in direct mode.

## Local Run (Preferred)
Use the same project `.venv` and root `requirements.txt` as other services.

1. Create and activate virtual environment:
   - `py -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Start parser API:
   - Bash: `bash scripts/run_parser.sh`

## Notes
- Direct mode is optimized for hackathon runtime stability.
- Queue-based mode can be restored later if needed.
- YouTube video parser enforces maximum duration of 5 minutes (300 seconds) when duration can be detected.
- Transcript strategy: English YouTube captions first, `faster-whisper` fallback when captions are missing/unusable.
- Optional dependencies for fallback: `faster-whisper`, `yt-dlp`.
- Parser returns extraction features/signals only; scoring formulas are owned by `scoring-service`.

## Endpoints
- `POST /parse`
  - Body:
    - `user_id` (required)
    - `file_id` (optional)
    - `github_url` (optional)
    - `youtube_url` (optional)
  - At least one of `file_id`, `github_url` or `youtube_url` is required.
- `GET /parse/tasks/{task_id}`
  - Returns Celery status and result/error.

## Output
- Processed JSON files are stored in:
  - `data/users/<user_id>/processed/processed_<file_id>.json`
  - `data/users/<user_id>/processed/video_<youtube_video_id>.json`
  - `data/users/<user_id>/links/<github_id>.json`
