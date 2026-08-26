"""File-backed storage for the mock database.

The JSON file is the single source of truth. Only this backend process
writes to it; writes are atomic (temp file + rename) so a crash can never
leave a half-written file behind.
"""

import json
import os
import tempfile
import threading
from pathlib import Path

from models import Course

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "curriculum.json"

_lock = threading.Lock()


def load_course() -> Course:
    with _lock:
        raw = json.loads(DATA_PATH.read_text())
    return Course.model_validate(raw)


def save_course(course: Course) -> None:
    payload = json.dumps(course.model_dump(), indent=2)
    with _lock:
        fd, tmp_path = tempfile.mkstemp(dir=DATA_PATH.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(payload)
            os.replace(tmp_path, DATA_PATH)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
