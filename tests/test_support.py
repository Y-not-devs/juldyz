from __future__ import annotations

import gc
import sys
import tempfile
import time
from contextlib import ExitStack, contextmanager
from importlib import import_module
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
project_root_str = str(PROJECT_ROOT)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

from core.db import Database


@contextmanager
def temp_database() -> Iterator[Database]:
    tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = Path(tmpdir.name) / "test.db"
    database = Database(db_path)
    try:
        yield database
    finally:
        del database
        gc.collect()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{db_path}{suffix}")
            if not candidate.exists():
                continue
            for _ in range(20):
                try:
                    candidate.unlink()
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(0.1)
                except FileNotFoundError:
                    break
        try:
            tmpdir.cleanup()
        except PermissionError:
            pass


@contextmanager
def patch_module_dbs(database: Database, *module_names: str):
    with ExitStack() as stack:
        for module_name in module_names:
            module = import_module(module_name)
            if hasattr(module, "db"):
                stack.enter_context(patch.object(module, "db", database))
        yield
