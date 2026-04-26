from __future__ import annotations
from urllib.parse import urlparse

def normalize_bind_host(value: str) -> str:
    raw = str(value).strip()
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        return parsed.hostname or "127.0.0.1"
    return raw

def build_service_base_url(value: str, port: int) -> str:
    raw = str(value).strip()
    if raw.startswith("http://"):
        scheme = "http://"
        host = raw[len("http://") :]
    elif raw.startswith("https://"):
        scheme = "https://"
        host = raw[len("https://") :]
    else:
        scheme = "http://"
        host = raw

    if host == "0.0.0.0":
        host = "127.0.0.1"

    return f"{scheme}{host}:{int(port)}"
