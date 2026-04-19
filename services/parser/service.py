from typing import Optional
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

import httpx

from core.config import (
    GOOGLE_DRIVE_BEARER_TOKEN,
    GOOGLE_DRIVE_COOKIE,
    GOOGLE_DRIVE_DOWNLOAD_TIMEOUT_SECONDS,
)
from core.db import db
from services.parser.storage import read_json_file, setup_user_directories
from services.parser.tasks import parse_file_task, parse_github_task
from services.parser.tasks_essay import parse_essay_task
from services.parser.tasks_video import parse_video_task
from services.parser.validation import (
    ensure_safe_identifier,
    extract_github_username,
    extract_youtube_video_id,
)


class ParserService:
    """Core parser logic, separate from FastAPI routes."""

    GOOGLE_DRIVE_HOSTS = {
        "drive.google.com",
        "www.drive.google.com",
        "docs.google.com",
        "www.docs.google.com",
        "drive.usercontent.google.com",
    }

    @staticmethod
    def _load_json_if_exists(path: Path) -> dict | None:
        if not path.exists():
            return None
        payload = read_json_file(path)
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _failure_payload(exc: Exception) -> dict:
        return {
            "status": "FAILURE",
            "error": str(exc),
            "error_type": type(exc).__name__,
        }

    @staticmethod
    def _build_download_url(file_url: str) -> str:
        parsed = urlparse(file_url)
        host = (parsed.hostname or "").lower()

        if host not in ParserService.GOOGLE_DRIVE_HOSTS:
            return file_url

        file_id = ParserService._extract_drive_file_id(file_url)
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"

        return file_url

    @staticmethod
    def _extract_drive_file_id(file_url: str) -> str | None:
        parsed = urlparse(file_url)
        host = (parsed.hostname or "").lower()
        if host not in ParserService.GOOGLE_DRIVE_HOSTS:
            return None

        path_parts = [part for part in parsed.path.split("/") if part]
        if "file" in path_parts and "d" in path_parts:
            try:
                file_id = path_parts[path_parts.index("d") + 1]
                if file_id:
                    return file_id
            except Exception:
                return None

        if len(path_parts) >= 3 and path_parts[0] == "u" and path_parts[2] == "folders":
            return None

        query = parse_qs(parsed.query)
        file_id = (query.get("id") or [""])[0]
        return file_id or None

    @staticmethod
    def _google_drive_headers(authenticated: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/pdf,application/octet-stream,text/html;q=0.9,*/*;q=0.8",
        }
        if authenticated and GOOGLE_DRIVE_COOKIE:
            headers["Cookie"] = GOOGLE_DRIVE_COOKIE
        return headers

    @staticmethod
    def _response_is_pdf(response: httpx.Response) -> bool:
        content_type = str(response.headers.get("Content-Type", "")).lower()
        return "pdf" in content_type or response.content.startswith(b"%PDF")

    @staticmethod
    def _response_requires_google_auth(response: httpx.Response) -> bool:
        final_host = (urlparse(str(response.url)).hostname or "").lower()
        if "accounts.google.com" in final_host:
            return True

        content_type = str(response.headers.get("Content-Type", "")).lower()
        if "html" not in content_type:
            return False

        body = response.text[:5000].lower()
        return (
            "servicelogin" in body
            or "accounts.google.com" in body
            or "signin/identifier" in body
            or "to continue to google drive" in body
        )

    @staticmethod
    def _extract_drive_confirm_token(response: httpx.Response) -> str | None:
        cookie_token = response.cookies.get("download_warning")
        if cookie_token:
            return cookie_token

        body = response.text
        patterns = (
            r'name="confirm"\s+value="([^"]+)"',
            r"confirm=([0-9A-Za-z_-]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, body)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _download_google_drive_pdf(file_id: str) -> bytes:
        clean_file_id = ensure_safe_identifier(file_id, "file_id")
        errors: list[str] = []

        if GOOGLE_DRIVE_BEARER_TOKEN:
            api_url = f"https://www.googleapis.com/drive/v3/files/{clean_file_id}?alt=media&supportsAllDrives=true"
            with httpx.Client(
                timeout=GOOGLE_DRIVE_DOWNLOAD_TIMEOUT_SECONDS,
                follow_redirects=True,
                headers={
                    **ParserService._google_drive_headers(authenticated=False),
                    "Authorization": f"Bearer {GOOGLE_DRIVE_BEARER_TOKEN}",
                },
            ) as client:
                response = client.get(api_url)
            if response.status_code == 200 and ParserService._response_is_pdf(response):
                return response.content
            errors.append(f"drive_api:{response.status_code}")

        anonymous_urls = [
            f"https://drive.usercontent.google.com/download?id={clean_file_id}&export=download",
            f"https://drive.google.com/uc?export=download&id={clean_file_id}",
            f"https://docs.google.com/uc?export=download&id={clean_file_id}",
        ]

        with httpx.Client(
            timeout=GOOGLE_DRIVE_DOWNLOAD_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=ParserService._google_drive_headers(authenticated=True),
        ) as client:
            for candidate_url in anonymous_urls:
                response = client.get(candidate_url)
                if response.status_code >= 400:
                    errors.append(f"download:{response.status_code}")
                    continue
                if ParserService._response_is_pdf(response):
                    return response.content
                if ParserService._response_requires_google_auth(response):
                    errors.append("drive_auth_required")
                    continue

                confirm_token = ParserService._extract_drive_confirm_token(response)
                if confirm_token:
                    confirmed = client.get(
                        f"https://drive.usercontent.google.com/download?id={clean_file_id}&export=download&confirm={confirm_token}"
                    )
                    if confirmed.status_code < 400 and ParserService._response_is_pdf(confirmed):
                        return confirmed.content
                    if ParserService._response_requires_google_auth(confirmed):
                        errors.append("drive_auth_required")
                    else:
                        errors.append(f"confirm_download:{confirmed.status_code}")
                    continue

                errors.append("not_pdf_response")

        if "drive_auth_required" in errors:
            raise PermissionError(
                "Google Drive file requires authentication or sharing permissions. "
                "Provide GOOGLE_DRIVE_BEARER_TOKEN/GOOGLE_DRIVE_COOKIE or make the file accessible to the backend."
            )
        raise ValueError("file_url did not return a PDF document")

    @staticmethod
    def _prepare_pdf_file(
        user_id: str,
        file_id: Optional[str] = None,
        file_url: Optional[str] = None,
    ) -> Optional[str]:
        if not file_id and not file_url:
            return None

        safe_file_id = ensure_safe_identifier(file_id, "file_id") if file_id else None
        dirs = setup_user_directories(user_id)
        files_dir = dirs["files"]

        if safe_file_id:
            pdf_path = files_dir / f"{safe_file_id}.pdf"
            if pdf_path.exists():
                db.ensure_file(int(user_id), safe_file_id, "pdf")
                return safe_file_id

        if not file_url:
            return safe_file_id

        raw_file_url = str(file_url).strip()
        drive_file_id = ParserService._extract_drive_file_id(raw_file_url)
        download_url = ParserService._build_download_url(raw_file_url)
        derived_file_id = safe_file_id or drive_file_id or f"upload_{hashlib.sha1(download_url.encode('utf-8')).hexdigest()[:16]}"
        derived_file_id = ensure_safe_identifier(derived_file_id, "file_id")
        pdf_path = files_dir / f"{derived_file_id}.pdf"
        if pdf_path.exists():
            db.ensure_file(int(user_id), derived_file_id, "pdf")
            return derived_file_id

        if drive_file_id:
            content = ParserService._download_google_drive_pdf(drive_file_id)
        else:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(download_url)
            response.raise_for_status()
            content_type = str(response.headers.get("Content-Type", "")).lower()
            if "pdf" not in content_type and not response.content.startswith(b"%PDF"):
                raise ValueError("file_url did not return a PDF document")
            content = response.content

        pdf_path.write_bytes(content)
        db.ensure_file(int(user_id), derived_file_id, "pdf")
        return derived_file_id

    @staticmethod
    def _run_task_sync(task_callable, *args) -> dict:
        try:
            result = task_callable(*args)
            return {"status": "SUCCESS", "result": result}
        except Exception as exc:
            return {
                "status": "FAILURE",
                "error": str(exc),
                "error_type": type(exc).__name__,
            }

    @staticmethod
    def _load_cached_file_task(user_id: str, file_id: str) -> dict | None:
        safe_user_id = ensure_safe_identifier(user_id, "user_id")
        safe_file_id = ensure_safe_identifier(file_id, "file_id")
        dirs = setup_user_directories(safe_user_id)
        cached = ParserService._load_json_if_exists(dirs["processed"] / f"processed_{safe_file_id}.json")
        if not cached:
            return None

        extracted_pdf = cached.get("pdf", {}) if isinstance(cached.get("pdf"), dict) else {}
        extracted_profile = cached.get("extracted_profile", {}) if isinstance(cached.get("extracted_profile"), dict) else {}
        summary = extracted_pdf.get("summary", {}) if isinstance(extracted_pdf.get("summary"), dict) else {}
        return {
            "status": "success",
            "user_id": safe_user_id,
            "file_id": safe_file_id,
            "pdf_summary": summary,
            "extracted_profile": extracted_profile,
            "output_path": str(dirs["processed"] / f"processed_{safe_file_id}.json"),
            "page_count": int(summary.get("page_count", 0) or 0),
            "total_char_count": int(summary.get("total_char_count", 0) or 0),
            "detected_email_count": len(extracted_profile.get("emails", [])) if isinstance(extracted_profile.get("emails"), list) else 0,
            "detected_phone_count": len(extracted_profile.get("phones", [])) if isinstance(extracted_profile.get("phones"), list) else 0,
            "finished_at": cached.get("updated_at"),
        }

    @staticmethod
    def _load_cached_video_task(user_id: str, youtube_video_id: str) -> dict | None:
        safe_user_id = ensure_safe_identifier(user_id, "user_id")
        safe_video_id = extract_youtube_video_id(f"https://www.youtube.com/watch?v={youtube_video_id}")
        dirs = setup_user_directories(safe_user_id)
        cached = ParserService._load_json_if_exists(dirs["processed"] / f"video_{safe_video_id}.json")
        if not cached:
            return None

        transcript = cached.get("transcript", {}) if isinstance(cached.get("transcript"), dict) else {}
        analysis = cached.get("analysis", {}) if isinstance(cached.get("analysis"), dict) else {}
        intrinsic = (
            analysis.get("signals", {}).get("intrinsic", {})
            if isinstance(analysis.get("signals"), dict)
            else {}
        )
        mission = (
            analysis.get("signals", {}).get("mission_alignment", {})
            if isinstance(analysis.get("signals"), dict)
            else {}
        )
        question_analysis = analysis.get("question_coverage", []) if isinstance(analysis.get("question_coverage"), list) else []
        covered_questions = sum(1 for item in question_analysis if isinstance(item, dict) and item.get("covered"))

        return {
            "status": "success",
            "user_id": safe_user_id,
            "video_id": safe_video_id,
            "video_meta": cached.get("video_meta", {}),
            "transcript": transcript,
            "analysis": analysis,
            "output_path": str(dirs["processed"] / f"video_{safe_video_id}.json"),
            "transcript_available": bool(transcript.get("available", False)),
            "transcript_source": transcript.get("source"),
            "question_covered_count": covered_questions,
            "signal_summary": {
                "mastery_mention_count": int(intrinsic.get("mastery_mention_count", 0) or 0),
                "autonomy_mention_count": int(intrinsic.get("autonomy_mention_count", 0) or 0),
                "mission_signal_count": int(mission.get("signal_count", 0) or 0),
            },
            "finished_at": cached.get("updated_at"),
        }

    @staticmethod
    def _load_cached_essay_task(user_id: str, essay_text: str) -> dict | None:
        safe_user_id = ensure_safe_identifier(user_id, "user_id")
        essay = (essay_text or "").strip()
        if not essay:
            return None

        essay_sha256 = hashlib.sha256(essay.encode("utf-8")).hexdigest()
        essay_char_count = len(essay)
        dirs = setup_user_directories(safe_user_id)
        candidates = sorted(
            dirs["processed"].glob("essay_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            cached = ParserService._load_json_if_exists(path)
            if not cached:
                continue
            if str(cached.get("user_id", "")) != safe_user_id:
                continue
            cached_hash = str(cached.get("essay_sha256", "")).strip()
            cached_char_count = int(cached.get("essay_char_count", 0) or 0)
            if cached_hash:
                if cached_hash != essay_sha256:
                    continue
            elif cached_char_count != essay_char_count:
                continue

            llm = cached.get("llm", {}) if isinstance(cached.get("llm"), dict) else {}
            parsed = llm.get("parsed", {}) if isinstance(llm.get("parsed"), dict) else {}
            return {
                "status": "success",
                "user_id": safe_user_id,
                "essay_char_count": essay_char_count,
                "llm_parsed_ok": bool(parsed.get("parsed_ok")),
                "analysis": parsed.get("analysis"),
                "raw_response": str(llm.get("raw_response", "")),
                "output_path": str(path),
                "finished_at": cached.get("updated_at"),
            }
        return None

    @staticmethod
    def queue_tasks(
        user_id: str,
        file_id: Optional[str] = None,
        file_url: Optional[str] = None,
        github_url: Optional[str] = None,
        youtube_url: Optional[str] = None,
        essay_text: Optional[str] = None,
    ) -> dict:
        # Validate identifiers
        user_id = ensure_safe_identifier(user_id, "user_id")
        github_username = extract_github_username(str(github_url)) if github_url else None
        youtube_video_id = extract_youtube_video_id(str(youtube_url)) if youtube_url else None
        essay_text_safe = essay_text.strip() if isinstance(essay_text, str) else None
        file_id_safe = None
        file_task_failure = None
        file_requested = bool(file_id or file_url)
        if file_requested:
            try:
                file_id_safe = ParserService._prepare_pdf_file(
                    user_id=user_id,
                    file_id=file_id,
                    file_url=str(file_url).strip() if file_url else None,
                )
            except Exception as exc:
                file_task_failure = ParserService._failure_payload(exc)

        # Run tasks directly (no queue, no broker).
        results: dict[str, dict] = {}
        submitted_tasks: list[tuple[str, tuple]] = []
        if github_username:
            submitted_tasks.append(("github_task", (parse_github_task, user_id, github_username)))
        if file_id_safe:
            cached_file = ParserService._load_cached_file_task(user_id, file_id_safe)
            if cached_file is not None:
                results["file_task"] = {"status": "SUCCESS", "result": cached_file}
            else:
                submitted_tasks.append(("file_task", (parse_file_task, user_id, file_id_safe)))
        elif file_task_failure:
            results["file_task"] = file_task_failure
        if youtube_video_id:
            cached_video = ParserService._load_cached_video_task(user_id, youtube_video_id)
            if cached_video is not None:
                results["video_task"] = {"status": "SUCCESS", "result": cached_video}
            else:
                submitted_tasks.append(("video_task", (parse_video_task, user_id, youtube_video_id)))
        if essay_text_safe:
            cached_essay = ParserService._load_cached_essay_task(user_id, essay_text_safe)
            if cached_essay is not None:
                results["essay_task"] = {"status": "SUCCESS", "result": cached_essay}
            else:
                submitted_tasks.append(("essay_task", (parse_essay_task, user_id, essay_text_safe)))

        if submitted_tasks:
            max_workers = min(4, len(submitted_tasks))
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="parser-task") as executor:
                future_map = {}
                for task_name, task_bundle in submitted_tasks:
                    task_callable = task_bundle[0]
                    task_args = task_bundle[1:]
                    future = executor.submit(ParserService._run_task_sync, task_callable, *task_args)
                    future_map[future] = task_name
                for future in as_completed(future_map):
                    results[future_map[future]] = future.result()

        success_count = sum(1 for item in results.values() if item.get("status") == "SUCCESS")
        failure_count = sum(1 for item in results.values() if item.get("status") == "FAILURE")

        return {
            "status": "completed" if failure_count == 0 else "completed_with_errors",
            "mode": "direct",
            "user_id": user_id,
            "file_id": file_id_safe,
            "file_url": str(file_url) if file_url else None,
            "github_url": str(github_url) if github_url else None,
            "github_username": github_username,
            "youtube_url": str(youtube_url) if youtube_url else None,
            "youtube_video_id": youtube_video_id,
            "essay_text_provided": bool(essay_text_safe),
            "github_task_id": None,
            "file_task_id": None,
            "video_task_id": None,
            "essay_task_id": None,
            "summary": {
                "requested_tasks": len(results),
                "success_count": success_count,
                "failure_count": failure_count,
            },
            "results": results,
        }

    @staticmethod
    def get_task_status(task_id: str) -> dict:
        safe_task_id = ensure_safe_identifier(task_id, "task_id")
        return {
            "status": "UNAVAILABLE",
            "mode": "direct",
            "task_id": safe_task_id,
            "detail": "Direct mode executes parser tasks immediately and does not create queued task IDs.",
        }
