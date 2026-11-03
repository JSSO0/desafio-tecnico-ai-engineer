from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.text import normalize


def connect(path: Path, *, readonly: bool = True) -> sqlite3.Connection:
    """SQLite connection. Read-only by default: the agent tools never write."""
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # free-text comparison without relying on accents: 'violao' finds 'Violão'
    conn.create_function("unaccent", 1, lambda value: normalize(value or ""), deterministic=True)
    return conn
