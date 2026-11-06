import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json_file(path: Path, default_value: Any) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        return default_value


def write_json_file_atomically(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(data))
    temporary_path.replace(path)


def generate_id() -> str:
    return str(uuid.uuid4())


def current_utc_timestamp() -> str:
    """ISO 8601 in UTC, such as 2026-11-05T09:30:00.123456Z. Sorts chronologically as text."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
