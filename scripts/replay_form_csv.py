from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import db


def _read_csv_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))

    if not rows:
        raise ValueError(f"CSV is empty: {path}")
    if len(rows) < 2:
        raise ValueError(f"CSV has header only and no data rows: {path}")

    header = rows[0]
    data_rows = rows[1:]
    return header, data_rows


def _build_payload_map(header: list[str], row: list[str]) -> dict[str, str]:
    payload: dict[str, str] = {}
    seen: Counter[str] = Counter()

    for key, value in zip(header, row):
        key = str(key)
        value = str(value).strip()
        seen[key] += 1
        if seen[key] == 1:
            payload[key] = value
        else:
            payload[f"{key} [{seen[key]}]"] = value

    return payload


def _select_row(data_rows: list[list[str]], row_index: int | None) -> list[str]:
    if row_index is None:
        return data_rows[-1]

    if row_index < 1 or row_index > len(data_rows):
        raise ValueError(f"row_index must be between 1 and {len(data_rows)}")

    return data_rows[row_index - 1]


def _extract_tg_id(payload: dict[str, str]) -> str:
    candidates = (
        payload.get("UID", "").strip(),
        payload.get("tg_id", "").strip(),
        payload.get("Telegram ID", "").strip(),
    )
    for candidate in candidates:
        if candidate:
            return candidate
    raise ValueError("CSV row does not contain UID/tg_id")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay a Google Form CSV response into form-service.",
    )
    parser.add_argument("csv_path", help="Path to the exported Google Form CSV file")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:8000/api/form-service/form-submit",
        help="form-service endpoint URL",
    )
    parser.add_argument(
        "--row-index",
        type=int,
        default=None,
        help="1-based data row index to replay; default is the last row",
    )
    parser.add_argument(
        "--no-ensure-user",
        action="store_true",
        help="Do not create the user in local DB before submit",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path).expanduser()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    header, data_rows = _read_csv_rows(csv_path)
    selected_row = _select_row(data_rows, args.row_index)
    payload_map = _build_payload_map(header, selected_row)
    tg_id = _extract_tg_id(payload_map)

    if not args.no_ensure_user:
        user_id = db.upsert_user(tg_id)
        print(f"Ensured user in DB: tg_id={tg_id}, user_id={user_id}")

    request_payload: dict[str, Any] = {
        "tg_id": tg_id,
        "data": payload_map,
    }

    print(f"Submitting row to {args.endpoint}")
    print(f"CSV rows: {len(data_rows)}, selected: {args.row_index or len(data_rows)}")
    print(f"Name: {payload_map.get('Name', '')} {payload_map.get('Surname', '')}".strip())
    print(f"Program: {payload_map.get('  Which program are you applying for?  ', '')}")

    with httpx.Client(timeout=60.0) as client:
        response = client.post(args.endpoint, json=request_payload)

    print(f"HTTP {response.status_code}")
    try:
        body = response.json()
    except Exception:
        body = {"raw": response.text}

    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0 if response.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
