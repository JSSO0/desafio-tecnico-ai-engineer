"""Reconstroi a base SQLite a partir dos CSVs e das politicas em Markdown.

Uso:
    python scripts/build_db.py                 # usa os caminhos de app.core.config
    python scripts/build_db.py --db /tmp/x.db --data data
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from app.core.config import get_settings  # noqa: E402
from app.db.build import build_database  # noqa: E402


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Constroi a base operacional da Emporio da Musica")
    parser.add_argument("--db", type=Path, default=settings.database_path)
    parser.add_argument("--data", type=Path, default=settings.data_dir)
    parser.add_argument("--policies", type=Path, default=None)
    args = parser.parse_args()

    policies_dir = args.policies or args.data / "policies"
    report = build_database(args.db, args.data, policies_dir)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
