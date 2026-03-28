import json
import socket
import os
from pathlib import Path
from datetime import datetime
from threading import Lock

RUNTIME_DIR = Path(__file__).parent.parent / "runtime"
HUB_FILE = RUNTIME_DIR / "hub.json"
LOCK = Lock()


class Hub:
    def __init__(self):
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        if not HUB_FILE.exists():
            self._write({})

    def register(self, name: str, port: int):
        with LOCK:
            data = self._read()
            data[name] = {
                "port": port,
                "pid": os.getpid(),
                "registered_at": datetime.now().isoformat(),
                "status": "ok"
            }
            self._write(data)

    def unregister(self, name: str):
        with LOCK:
            data = self._read()
            data.pop(name, None)
            self._write(data)

    def locate(self, name: str) -> str | None:
        entry = self._read().get(name)
        if not entry:
            return None
        return f"http://localhost:{entry['port']}"

    def all(self) -> dict:
        return self._read()

    def free_port(self, start: int = 8000) -> int:
        used = {v["port"] for v in self._read().values()}
        port = start
        while True:
            if port not in used and self._is_port_free(port):
                return port
            port += 1

    def _is_port_free(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("localhost", port)) != 0

    def _read(self) -> dict:
        try:
            return json.loads(HUB_FILE.read_text())
        except Exception:
            return {}

    def _write(self, data: dict):
        HUB_FILE.write_text(json.dumps(data, indent=2))


hub = Hub()