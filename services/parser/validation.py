import re
from urllib.parse import urlparse

SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
GITHUB_USERNAME_RE = re.compile(r"^[A-Za-z\d](?:[A-Za-z\d]|-(?=[A-Za-z\d])){0,38}$")


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
