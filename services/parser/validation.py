import re
from urllib.parse import urlparse
from urllib.parse import parse_qs

SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z\d](?:[A-Za-z\d]|-(?=[A-Za-z\d])){0,38}$")
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def ensure_safe_identifier(value: str, field_name: str) -> str:
    if not value or not SAFE_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"Invalid {field_name}. Use only letters, digits, '_' or '-' (1-128 chars)."
        )
    return value


def normalize_github_username(value: str) -> str:
    username = value.strip().strip("/")
    if not GITHUB_USERNAME_RE.fullmatch(username):
        raise ValueError("Invalid GitHub username format.")
    return username


def extract_github_username(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"github.com", "www.github.com"}:
        raise ValueError("github_url must use github.com domain.")

    path = parsed.path.strip("/")
    if not path:
        raise ValueError("github_url must include a profile username.")

    path_parts = [part for part in path.split("/") if part]
    if len(path_parts) != 1:
        raise ValueError("github_url must point to a user profile, e.g. github.com/username.")

    if parsed.query or parsed.fragment:
        raise ValueError("github_url must not contain query parameters or fragments.")

    return normalize_github_username(path_parts[0])


def normalize_youtube_video_id(value: str) -> str:
    video_id = value.strip()
    if not YOUTUBE_VIDEO_ID_RE.fullmatch(video_id):
        raise ValueError("Invalid YouTube video id format.")
    return video_id


def extract_youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()

    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/")
        if not video_id:
            raise ValueError("youtube_url must include video id in path.")
        if parsed.query:
            query = parse_qs(parsed.query)
            if "v" in query:
                video_id = query["v"][0]
        return normalize_youtube_video_id(video_id)

    if host not in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        raise ValueError("youtube_url must use youtube.com or youtu.be domain.")

    query = parse_qs(parsed.query)
    if parsed.path == "/watch":
        video_id = (query.get("v") or [""])[0]
        if not video_id:
            raise ValueError("youtube_url must include ?v=<video_id>.")
        return normalize_youtube_video_id(video_id)

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) >= 2 and path_parts[0] in {"shorts", "embed", "live"}:
        return normalize_youtube_video_id(path_parts[1])

    raise ValueError("Unsupported youtube_url format.")
