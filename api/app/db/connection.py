from __future__ import annotations

import sqlite3
from pathlib import Path


def connect(path: Path, *, readonly: bool = True) -> sqlite3.Connection:
    """Conexao SQLite. Por padrao, somente leitura: as ferramentas do agente nao escrevem."""
    if readonly:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, check_same_thread=False)
    else:
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
