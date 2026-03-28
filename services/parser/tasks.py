from datetime import UTC, datetime
from pathlib import Path
import re
from typing import Any

import httpx
from pypdf import PdfReader
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from services.parser.celery_app import celery_app
from services.parser.storage import setup_user_directories, write_json_file
from services.parser.validation import ensure_safe_identifier, normalize_github_username

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:(?:\+|00)\d[\d\s().-]{7,}\d|\b\d[\d\s().-]{8,}\d\b)")
GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/[A-Za-z\d](?:[A-Za-z\d]|-(?=[A-Za-z\d])){0,38}",
    re.IGNORECASE,
)
LINKEDIN_URL_RE = re.compile(
    r"https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[A-Za-z0-9_-]+",
    re.IGNORECASE,
)
SKILL_KEYWORDS = [
    # --- Языки программирования ---
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "c",
    "go",
    "rust",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "scala",
    "r",
    "dart",
    "bash",
    "powershell",

    # --- Фронтенд и мобильная разработка ---
    "html",
    "css",
    "react",
    "angular",
    "vue.js",
    "svelte",
    "next.js",
    "react native",
    "flutter",
    "tailwind css",

    # --- Бэкенд и фреймворки ---
    "node.js",
    "express",
    "fastapi",
    "django",
    "flask",
    "spring boot",
    "asp.net",
    "ruby on rails",
    "graphql",
    "rest api",
    "grpc",

    # --- Базы данных и брокеры сообщений ---
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "sqlite",
    "oracle",
    "cassandra",
    "elasticsearch",
    "dynamodb",
    "firebase",
    "rabbitmq",
    "apache kafka",

    # --- DevOps, Облака и Инфраструктура ---
    "docker",
    "kubernetes",
    "git",
    "linux",
    "aws",
    "azure",
    "gcp",
    "terraform",
    "ansible",
    "jenkins",
    "ci/cd",
    "github actions",
    "gitlab ci",
    "nginx",
    "prometheus",
    "grafana",

    # --- Data Science, Machine Learning и Big Data ---
    "machine learning",
    "data analysis",
    "deep learning",
    "nlp",
    "computer vision",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "apache spark",
    "hadoop",
    "apache airflow",

    # --- Архитектура и методологии ---
    "microservices",
    "agile",
    "scrum",
    "jira",
    "system design"
]


class RetryableGitHubError(Exception):
    pass


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _guess_candidate_name(lines: list[str]) -> str | None:
    for line in lines[:20]:
        if "@" in line or any(ch.isdigit() for ch in line):
            continue
        normalized = re.sub(r"\s+", " ", line).strip()
        words = normalized.split()
        if 2 <= len(words) <= 5 and all(any(ch.isalpha() for ch in w) for w in words):
            return normalized
    return None


def _extract_candidate_profile(pages: list[dict[str, Any]]) -> dict[str, Any]:
    page_texts = [str(page.get("text", "")).strip() for page in pages]
    page_texts = [text for text in page_texts if text]
    full_text = "\n".join(page_texts)
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    normalized_text = re.sub(r"[ \t]+", " ", full_text)
    lowered = normalized_text.lower()

    emails = _unique_preserve_order(EMAIL_RE.findall(full_text))

    phones_raw = PHONE_RE.findall(full_text)
    phones: list[str] = []
    for phone in phones_raw:
        digits = re.sub(r"\D", "", phone)
        if 10 <= len(digits) <= 15:
            phones.append(re.sub(r"\s+", " ", phone).strip())
    phones = _unique_preserve_order(phones)

    github_urls = _unique_preserve_order(GITHUB_URL_RE.findall(full_text))
    linkedin_urls = _unique_preserve_order(LINKEDIN_URL_RE.findall(full_text))

    detected_skills: list[str] = []
    for skill in SKILL_KEYWORDS:
        pattern = rf"(?<!\w){re.escape(skill.lower())}(?!\w)"
        if re.search(pattern, lowered):
            detected_skills.append(skill)

    return {
        "detected_name": _guess_candidate_name(lines),
        "primary_email": emails[0] if emails else None,
        "emails": emails,
        "primary_phone": phones[0] if phones else None,
        "phones": phones,
        "github_urls": github_urls,
        "linkedin_urls": linkedin_urls,
        "skills": detected_skills,
        "full_text_preview": normalized_text[:1500],
    }


def _serialize_pdf_metadata(pdf_reader: PdfReader) -> dict[str, Any]:
    metadata = pdf_reader.metadata or {}
    serialized: dict[str, Any] = {}
    for key, value in metadata.items():
        clean_key = str(key).lstrip("/")
        if isinstance(value, (str, int, float, bool)) or value is None:
            serialized[clean_key] = value
        else:
            serialized[clean_key] = str(value)
    return serialized


def _extract_pdf_payload(pdf_path: Path) -> dict[str, Any]:
    pdf_reader = PdfReader(str(pdf_path))

    if pdf_reader.is_encrypted and pdf_reader.decrypt("") == 0:
        raise ValueError(f"File {pdf_path} is encrypted and requires a password")

    pages: list[dict[str, Any]] = []
    empty_pages = 0
    failed_pages = 0
    total_char_count = 0

    for page_index, page in enumerate(pdf_reader.pages, start=1):
        try:
            text = (page.extract_text() or "").strip()
        except Exception as exc:
            failed_pages += 1
            pages.append(
                {
                    "page": page_index,
                    "char_count": 0,
                    "text": "",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue

        if not text:
            empty_pages += 1

        char_count = len(text)
        total_char_count += char_count
        pages.append(
            {
                "page": page_index,
                "char_count": char_count,
                "text": text,
            }
        )

    page_count = len(pages)
    return {
        "summary": {
            "page_count": page_count,
            "non_empty_page_count": page_count - empty_pages - failed_pages,
            "empty_page_count": empty_pages,
            "failed_page_count": failed_pages,
            "total_char_count": total_char_count,
        },
        "metadata": _serialize_pdf_metadata(pdf_reader),
        "pages": pages,
    }


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
def _fetch_github_profile(github_username: str) -> dict:
    username = normalize_github_username(github_username)
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
def parse_github_task(user_id: str, github_username: str) -> dict:
    safe_user_id = ensure_safe_identifier(user_id, "user_id")
    safe_username = normalize_github_username(github_username)

    profile_data = _fetch_github_profile(safe_username)
    github_id = str(profile_data.get("id", f"error_{safe_username}"))
    result_status = "success" if "id" in profile_data else "not_found"

    dirs = setup_user_directories(safe_user_id)
    output_path = dirs["links"] / f"{github_id}.json"
    write_json_file(output_path, profile_data)

    return {
        "status": result_status,
        "user_id": safe_user_id,
        "github_username": safe_username,
        "github_id": github_id,
        "output_path": str(output_path),
        "source_status_code": profile_data.get("status", 200),
        "finished_at": _utc_now_iso(),
    }


@celery_app.task(name="parser.parse_file_task")
def parse_file_task(user_id: str, file_id: str) -> dict:
    safe_user_id = ensure_safe_identifier(user_id, "user_id")
    safe_file_id = ensure_safe_identifier(file_id, "file_id")

    dirs = setup_user_directories(safe_user_id)
    pdf_path = dirs["files"] / f"{safe_file_id}.pdf"
    if not pdf_path.exists():
        raise FileNotFoundError(f"File {pdf_path} not found")

    extracted_pdf = _extract_pdf_payload(pdf_path)
    extracted_profile = _extract_candidate_profile(extracted_pdf["pages"])
    processed_path = dirs["processed"] / f"processed_{safe_file_id}.json"
    payload = {
        "status": "parsed",
        "file_id": safe_file_id,
        "source_pdf": str(pdf_path),
        "updated_at": _utc_now_iso(),
        "pdf": extracted_pdf,
        "extracted_profile": extracted_profile,
    }
    write_json_file(processed_path, payload)

    return {
        "status": "success",
        "user_id": safe_user_id,
        "file_id": safe_file_id,
        "output_path": str(processed_path),
        "page_count": extracted_pdf["summary"]["page_count"],
        "total_char_count": extracted_pdf["summary"]["total_char_count"],
        "detected_email_count": len(extracted_profile["emails"]),
        "detected_phone_count": len(extracted_profile["phones"]),
        "finished_at": _utc_now_iso(),
    }
