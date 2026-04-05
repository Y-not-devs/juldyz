from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from html import unescape
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from xml.etree import ElementTree

import httpx

from services.parser.storage import setup_user_directories, write_json_file
from services.parser.validation import ensure_safe_identifier, normalize_youtube_video_id

MAX_VIDEO_SECONDS = 300
ENGLISH_CAPTION_PREFERENCES = ("en", "en-US", "en-GB")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _extract_length_seconds_from_watch_html(html: str) -> int | None:
    match = re.search(r'"lengthSeconds":"(\d+)"', html)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _fetch_video_meta(video_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        oembed_resp = client.get(
            "https://www.youtube.com/oembed",
            params={
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "format": "json",
            },
        )

        if oembed_resp.status_code != 200:
            return {
                "available": False,
                "status_code": oembed_resp.status_code,
                "title": None,
                "author_name": None,
                "provider_name": None,
                "duration_seconds": None,
                "duration_hhmmss": None,
                "is_duration_within_limit": None,
                "max_allowed_seconds": MAX_VIDEO_SECONDS,
            }

        payload = oembed_resp.json()

        watch_resp = client.get(f"https://www.youtube.com/watch?v={video_id}")
        duration_seconds = None
        if watch_resp.status_code == 200:
            duration_seconds = _extract_length_seconds_from_watch_html(watch_resp.text)

        duration_hhmmss = None
        duration_ok = None
        if isinstance(duration_seconds, int):
            duration_hhmmss = (
                f"{duration_seconds // 3600:02}:"
                f"{(duration_seconds % 3600) // 60:02}:"
                f"{duration_seconds % 60:02}"
            )
            duration_ok = duration_seconds <= MAX_VIDEO_SECONDS

        return {
            "available": True,
            "status_code": oembed_resp.status_code,
            "title": payload.get("title"),
            "author_name": payload.get("author_name"),
            "provider_name": payload.get("provider_name"),
            "duration_seconds": duration_seconds,
            "duration_hhmmss": duration_hhmmss,
            "is_duration_within_limit": duration_ok,
            "max_allowed_seconds": MAX_VIDEO_SECONDS,
        }


def _fetch_caption_transcript_english(video_id: str) -> dict[str, Any]:
    with httpx.Client(timeout=20.0) as client:
        track_list_resp = client.get(
            "https://video.google.com/timedtext",
            params={"type": "list", "v": video_id},
        )

        if track_list_resp.status_code != 200:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": track_list_resp.status_code,
                "reason": "track_list_unavailable",
                "transcript_text": "",
            }

        try:
            root = ElementTree.fromstring(track_list_resp.text)
        except ElementTree.ParseError:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": 200,
                "reason": "invalid_track_list_xml",
                "transcript_text": "",
            }

        tracks: list[dict[str, str]] = []
        for track in root.findall("track"):
            tracks.append(
                {
                    "lang_code": track.attrib.get("lang_code", ""),
                    "name": track.attrib.get("name", ""),
                    "kind": track.attrib.get("kind", ""),
                }
            )

        if not tracks:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": 200,
                "reason": "no_captions",
                "transcript_text": "",
                "tracks": [],
            }

        selected_track: dict[str, str] | None = None
        by_lang = {t["lang_code"]: t for t in tracks if t.get("lang_code")}
        for lang in ENGLISH_CAPTION_PREFERENCES:
            if lang in by_lang:
                selected_track = by_lang[lang]
                break

        if selected_track is None:
            selected_track = next(
                (track for track in tracks if str(track.get("lang_code", "")).lower().startswith("en")),
                None,
            )

        if selected_track is None:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": 200,
                "reason": "no_english_captions",
                "transcript_text": "",
                "tracks": tracks,
            }

        params = {"v": video_id, "lang": selected_track["lang_code"]}
        if selected_track.get("name"):
            params["name"] = selected_track["name"]
        if selected_track.get("kind"):
            params["kind"] = selected_track["kind"]

        transcript_resp = client.get("https://video.google.com/timedtext", params=params)
        if transcript_resp.status_code != 200:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": transcript_resp.status_code,
                "reason": "transcript_fetch_failed",
                "transcript_text": "",
                "tracks": tracks,
                "selected_track": selected_track,
            }

        try:
            transcript_root = ElementTree.fromstring(transcript_resp.text)
        except ElementTree.ParseError:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": 200,
                "reason": "invalid_transcript_xml",
                "transcript_text": "",
                "tracks": tracks,
                "selected_track": selected_track,
            }

        lines: list[str] = []
        segments = transcript_root.findall("text")
        for segment in segments:
            if segment.text:
                text = unescape(segment.text).replace("\n", " ").strip()
                if text:
                    lines.append(text)

        transcript_text = " ".join(lines).strip()
        if not transcript_text:
            return {
                "available": False,
                "source": "captions_en",
                "status_code": 200,
                "reason": "empty_transcript",
                "transcript_text": "",
                "tracks": tracks,
                "selected_track": selected_track,
            }

        return {
            "available": True,
            "source": "captions_en",
            "status_code": 200,
            "reason": "ok",
            "tracks": tracks,
            "selected_track": selected_track,
            "segment_count": len(segments),
            "line_count": len(lines),
            "transcript_text": transcript_text,
        }


@lru_cache(maxsize=1)
def _load_faster_whisper_model():
    from faster_whisper import WhisperModel

    model_size = os.getenv("FASTER_WHISPER_MODEL_SIZE", "tiny.en")
    device = os.getenv("FASTER_WHISPER_DEVICE", "cpu")
    compute_type = os.getenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")
    return WhisperModel(model_size, device=device, compute_type=compute_type)


def _resolve_downloaded_audio_path(download_root: Path, video_id: str) -> Path | None:
    matches = list(download_root.glob(f"{video_id}.*"))
    return matches[0] if matches else None


def _transcribe_with_faster_whisper(video_id: str) -> dict[str, Any]:
    try:
        import yt_dlp
    except Exception:
        return {
            "available": False,
            "source": "faster_whisper",
            "reason": "missing_dependency_yt_dlp",
            "transcript_text": "",
        }

    try:
        model = _load_faster_whisper_model()
    except Exception as exc:
        return {
            "available": False,
            "source": "faster_whisper",
            "reason": "whisper_model_init_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "transcript_text": "",
        }

    with tempfile.TemporaryDirectory(prefix="juldyz_audio_") as tmp_dir:
        download_root = Path(tmp_dir)
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(download_root / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=True)
                audio_path = None
                requested = info.get("requested_downloads")
                if isinstance(requested, list) and requested:
                    audio_path = requested[0].get("filepath")
                if not audio_path:
                    audio_path = ydl.prepare_filename(info)
        except Exception as exc:
            return {
                "available": False,
                "source": "faster_whisper",
                "reason": "audio_download_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "transcript_text": "",
            }

        audio_file = Path(audio_path) if audio_path else _resolve_downloaded_audio_path(download_root, video_id)
        if not audio_file or not audio_file.exists():
            return {
                "available": False,
                "source": "faster_whisper",
                "reason": "audio_file_not_found",
                "transcript_text": "",
            }

        try:
            segments_iter, info = model.transcribe(
                str(audio_file),
                language="en",
                beam_size=2,
                vad_filter=True,
            )
            segments = list(segments_iter)
            lines = [segment.text.strip() for segment in segments if segment.text and segment.text.strip()]
            transcript_text = " ".join(lines).strip()
        except Exception as exc:
            return {
                "available": False,
                "source": "faster_whisper",
                "reason": "transcription_failed",
                "error": f"{type(exc).__name__}: {exc}",
                "transcript_text": "",
            }

        if not transcript_text:
            return {
                "available": False,
                "source": "faster_whisper",
                "reason": "empty_transcript",
                "transcript_text": "",
            }

        return {
            "available": True,
            "source": "faster_whisper",
            "reason": "ok",
            "line_count": len(lines),
            "segment_count": len(segments),
            "detected_language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "audio_duration_seconds": getattr(info, "duration", None),
            "transcript_text": transcript_text,
        }


def _contains_any(text: str, words: list[str]) -> bool:
    return any(_term_present(text, word) for word in words)


def _term_present(text: str, term: str) -> bool:
    normalized_term = term.strip().lower()
    if not normalized_term:
        return False

    # Multi-word phrases are checked as substring to preserve order.
    if " " in normalized_term or "-" in normalized_term:
        return normalized_term in text

    # Single token: enforce word boundaries and light inflection support.
    pattern = rf"\b{re.escape(normalized_term)}(?:s|es|ed|ing)?\b"
    return re.search(pattern, text) is not None


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _term_present(text, term)]


def _extract_intrinsic_signals(text: str) -> dict[str, Any]:
    # Formula from rubric image:
    # Type I (Intrinsic) = 0..4 points based on mentions of mastery and autonomy.
    mastery_keywords = ["improve", "growth", "learn", "practice", "master", "skill", "develop"]
    autonomy_keywords = ["independent", "ownership", "initiative", "self-driven", "freedom", "autonomy"]

    mastery_hits = [word for word in mastery_keywords if word in text]
    autonomy_hits = [word for word in autonomy_keywords if word in text]

    return {
        "signals": {
            "mastery_mentions": mastery_hits,
            "autonomy_mentions": autonomy_hits,
        },
        "mastery_mention_count": len(mastery_hits),
        "autonomy_mention_count": len(autonomy_hits),
    }


def _extract_mission_alignment_signals(text: str) -> dict[str, Any]:
    buckets = [
        ("community", ["community", "society", "people", "help others", "volunteer"]),
        ("service", ["give back", "contribution", "impact", "solve real problems"]),
        ("education", ["education", "students", "mentor", "teach", "knowledge sharing"]),
        ("values", ["purpose", "mission", "ethics", "responsibility"]),
        ("long_term", ["long-term", "future", "career goal", "vision"]),
        ("calling", ["calling", "meaning", "my life goal", "dream to serve"]),
    ]
    hits = [name for name, words in buckets if _contains_any(text, words)]
    return {
        "signals": hits,
        "signal_count": len(hits),
    }


def _question_coverage(text: str) -> list[dict[str, Any]]:
    # Advanced rule-based matching:
    # 1) Richer keyword groups
    # 2) Sentence-level co-occurrence to reduce false positives
    # 3) coverage_level with confidence score
    checks = [
        {
            "question_id": "q1_why_university",
            "groups": [
                ["apply", "applying", "application", "why", "reason", "chose"],
                ["invision", "university", "study at", "join", "admission", "school"],
            ],
        },
        {
            "question_id": "q2_program_and_why",
            "groups": [
                ["program", "major", "track", "degree", "faculty", "course", "discipline"],
                ["because", "why", "interested", "reason", "fits me", "aligns with"],
            ],
        },
        {
            "question_id": "q3_challenge",
            "groups": [
                ["challenge", "obstacle", "difficulty", "hard time", "setback", "failure", "problem"],
                ["overcome", "helped", "kept me going", "solve", "managed", "handled", "recovered"],
            ],
        },
        {
            "question_id": "q4_long_term_motivation",
            "groups": [
                ["long-term", "future", "in the future", "career", "after graduation", "next years"],
                ["goal", "motivation", "motivates", "dream", "purpose", "aspiration"],
            ],
        },
        {
            "question_id": "q5_leadership",
            "groups": [
                ["leader", "leadership", "led", "lead", "took initiative"],
                ["example", "team", "project", "organized", "managed", "coordinated", "captain"],
            ],
        },
        {
            "question_id": "q6_family_support",
            "groups": [
                ["family", "parents", "mother", "father", "sister", "brother"],
                ["support", "encourage", "encouragement", "backed", "stand by", "approve"],
            ],
        },
        {
            "question_id": "q7_english_progress",
            "groups": [
                ["english", "language"],
                ["learn", "learning", "practice", "improve", "progress", "level", "fluency"],
            ],
        },
    ]

    # Normalize separators for sentence-level evidence extraction.
    normalized = re.sub(r"[\r\n]+", " ", text)
    sentences = [part.strip() for part in re.split(r"[.!?;]+", normalized) if part.strip()]

    results: list[dict[str, Any]] = []
    for check in checks:
        group_hits_global: list[list[str]] = []
        for group in check["groups"]:
            hits = _matched_terms(text, group)
            group_hits_global.append(hits)

        matched = [kw for hits in group_hits_global for kw in hits]
        required_groups_count = len(check["groups"])
        matched_groups_global = sum(1 for hits in group_hits_global if hits)

        # Strong signal: all groups matched inside one sentence.
        sentence_group_coverage_max = 0
        evidence_sentences: list[str] = []
        for sentence in sentences:
            sentence_group_hits = []
            for group in check["groups"]:
                sentence_group_hits.append(_matched_terms(sentence, group))

            sentence_group_count = sum(1 for hits in sentence_group_hits if hits)
            if sentence_group_count > sentence_group_coverage_max:
                sentence_group_coverage_max = sentence_group_count

            if sentence_group_count >= 2:
                evidence_sentences.append(sentence[:220])
            if len(evidence_sentences) >= 2:
                break

        covered = sentence_group_coverage_max >= required_groups_count
        coverage_level = "none"
        confidence_score = 0.0
        if covered:
            coverage_level = "full"
            confidence_score = 1.0
        elif matched_groups_global >= max(1, required_groups_count - 1):
            coverage_level = "partial"
            confidence_score = 0.5

        # Penalize generic low-signal matches.
        if coverage_level != "none" and len(matched) <= 1:
            coverage_level = "none"
            confidence_score = 0.0
            covered = False

        results.append(
            {
                "question_id": check["question_id"],
                "covered": covered,
                "coverage_level": coverage_level,
                "confidence_score": confidence_score,
                "matched_keywords": matched,
                "matched_groups_count": matched_groups_global,
                "required_groups_count": required_groups_count,
                "sentence_group_coverage_max": sentence_group_coverage_max,
                "evidence_sentences": evidence_sentences,
            }
        )
    return results


def parse_video_task(user_id: str, youtube_video_id: str) -> dict[str, Any]:
    safe_user_id = ensure_safe_identifier(user_id, "user_id")
    safe_video_id = normalize_youtube_video_id(youtube_video_id)

    meta = _fetch_video_meta(safe_video_id)
    duration_seconds = meta.get("duration_seconds")
    if isinstance(duration_seconds, int) and duration_seconds > MAX_VIDEO_SECONDS:
        raise ValueError(
            f"Video duration exceeds limit: {duration_seconds}s > {MAX_VIDEO_SECONDS}s (5 minutes)."
        )

    caption_transcript = _fetch_caption_transcript_english(safe_video_id)
    whisper_transcript = None
    transcript = caption_transcript
    if not caption_transcript.get("available", False):
        whisper_transcript = _transcribe_with_faster_whisper(safe_video_id)
        if whisper_transcript.get("available", False):
            transcript = whisper_transcript
        else:
            transcript = {
                "available": False,
                "source": "none",
                "reason": "no_transcript_from_captions_or_whisper",
                "transcript_text": "",
            }

    transcript_text = str(transcript.get("transcript_text", "")).lower()
    intrinsic = (
        _extract_intrinsic_signals(transcript_text)
        if transcript_text
        else {
            "signals": {"mastery_mentions": [], "autonomy_mentions": []},
            "mastery_mention_count": 0,
            "autonomy_mention_count": 0,
        }
    )
    mission = (
        _extract_mission_alignment_signals(transcript_text)
        if transcript_text
        else {"signals": [], "signal_count": 0, "max_signal_count": 6}
    )

    question_analysis = _question_coverage(transcript_text) if transcript_text else []
    covered_questions = sum(1 for q in question_analysis if q["covered"])

    payload = {
        "status": "parsed",
        "type": "video",
        "video_id": safe_video_id,
        "youtube_url": f"https://www.youtube.com/watch?v={safe_video_id}",
        "updated_at": _utc_now_iso(),
        "video_meta": meta,
        "transcript": {
            "available": transcript.get("available", False),
            "source": transcript.get("source"),
            "reason": transcript.get("reason"),
            "selected_track": caption_transcript.get("selected_track"),
            "line_count": transcript.get("line_count", 0),
            "segment_count": transcript.get("segment_count", 0),
            "detected_language": transcript.get("detected_language"),
            "language_probability": transcript.get("language_probability"),
            "preview": str(transcript.get("transcript_text", ""))[:2000],
            "fallback": {
                "captions_en": caption_transcript,
                "faster_whisper": whisper_transcript,
            },
        },
        "analysis": {
            "question_coverage": question_analysis,
            "question_coverage_ratio": round(covered_questions / 7, 3) if question_analysis else 0.0,
            "signals": {
                "intrinsic": intrinsic,
                "mission_alignment": mission,
            },
            "constraints": {
                "max_video_seconds": MAX_VIDEO_SECONDS,
            },
        },
    }

    dirs = setup_user_directories(safe_user_id)
    output_path = dirs["processed"] / f"video_{safe_video_id}.json"
    write_json_file(output_path, payload)

    return {
        "status": "success",
        "user_id": safe_user_id,
        "video_id": safe_video_id,
        "output_path": str(output_path),
        "transcript_available": bool(transcript.get("available", False)),
        "transcript_source": transcript.get("source"),
        "question_covered_count": covered_questions,
        "signal_summary": {
            "mastery_mention_count": intrinsic["mastery_mention_count"],
            "autonomy_mention_count": intrinsic["autonomy_mention_count"],
            "mission_signal_count": mission["signal_count"],
        },
        "finished_at": _utc_now_iso(),
    }
