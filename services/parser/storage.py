import json
from pathlib import Path
from typing import Any


def setup_user_directories(user_id: str) -> dict[str, Path]:
    current_dir = Path(__file__).resolve().parent
    root_dir = current_dir.parent.parent

    global_files_dir = root_dir / "data" / "files"
    global_files_dir.mkdir(parents=True, exist_ok=True)

    user_dir = root_dir / "data" / "users" / user_id
    links_dir = user_dir / "links"
    processed_dir = user_dir / "processed"
    links_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    return {
        "links": links_dir,
        "files": global_files_dir,
        "processed": processed_dir,
    }


def write_json_file(path: Path, payload: Any) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=4, ensure_ascii=False)


def read_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as input_file:
        return json.load(input_file)


def write_binary_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as output_file:
        output_file.write(content)

