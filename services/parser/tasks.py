from datetime import UTC, datetime

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.parser.celery_app import celery_app
from services.parser.storage import setup_user_directories, write_json_file


class RetryableGitHubError(Exception):
    pass


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _is_rate_limited(response: httpx.Response) -> bool:
    return response.status_code == 429 or (
        response.status_code == 403
        and response.headers.get("X-RateLimit-Remaining") == "0"
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(4),
    wait=wait_exponential_jitter(initial=1, max=20),
    retry=retry_if_exception_type(RetryableGitHubError),
)
def _fetch_github_profile(profile_url: str) -> dict:
    username = profile_url.rstrip("/").split("/")[-1]
    api_url = f"https://api.github.com/users/{username}"

    with httpx.Client(timeout=20.0) as client:
        response = client.get(api_url)

    if response.status_code == 200:
        return response.json()

    if _is_rate_limited(response) or response.status_code >= 500:
        raise RetryableGitHubError(
            f"GitHub temporary error {response.status_code} for user {username}"
        )

    return {
        "error": "User not found",
        "status": response.status_code,
        "username": username,
    }


@celery_app.task(name="parser.parse_github_task")
def parse_github_task(user_id: str, profile_url: str) -> dict:
    profile_data = _fetch_github_profile(profile_url)
    username = profile_url.rstrip("/").split("/")[-1]
    github_id = str(profile_data.get("id", f"error_{username}"))

    dirs = setup_user_directories(user_id)
    output_path = dirs["links"] / f"{github_id}.json"
    write_json_file(output_path, profile_data)

    return {
        "status": "success",
        "user_id": user_id,
        "github_id": github_id,
        "output_path": str(output_path),
        "finished_at": _utc_now_iso(),
    }


@celery_app.task(name="parser.parse_file_task")
def parse_file_task(user_id: str, file_id: str) -> dict:
    dirs = setup_user_directories(user_id)
    pdf_path = dirs["files"] / f"{file_id}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"File {pdf_path} not found")

    processed_path = dirs["processed"] / f"processed_{file_id}.json"
    payload = {
        "status": "pending_llm_integration",
        "file_id": file_id,
        "source_pdf": str(pdf_path),
        "updated_at": _utc_now_iso(),
    }
    write_json_file(processed_path, payload)

    return {
        "status": "success",
        "user_id": user_id,
        "file_id": file_id,
        "output_path": str(processed_path),
        "finished_at": _utc_now_iso(),
    }

