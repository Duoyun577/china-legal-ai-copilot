# -*- coding: utf-8 -*-
"""Migrate local SQLite data (cases + usage) into a PostgreSQL database.

The target is read from the DATABASE_URL environment variable. Source files are
data/cases.db and data/usage.db. Tables are copied with their original primary
keys so foreign-key links stay intact. Re-running is safe: rows with an
existing primary key are skipped.

Usage (PowerShell, from the project root):
    $env:DATABASE_URL = "postgresql://user:pass@host:5432/dbname"
    .venv\\Scripts\\python.exe tools\\migrate_sqlite_to_postgres.py

If the local SQLite databases hold no data, the script reports that there is
nothing to migrate and exits cleanly (a fresh cloud database is expected).
"""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_URL = os.environ.get("DATABASE_URL", "").strip()
if not DB_URL.startswith(("postgresql://", "postgres://")):
    print("ERROR: set DATABASE_URL to a postgresql:// URL before running.")
    sys.exit(1)

from utils.database import Database

# (source file, ordered tables). Parents before children; PK first column.
PLAN = [
    ("cases.db", ["cases", "case_records", "case_files", "case_events", "case_memories"]),
    ("usage.db", ["user_profiles", "usage_events"]),
]


def sqlite_rows(path: Path, table: str):
    if not path.exists():
        return [], []
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    try:
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        if not cols:
            return [], []
        rows = [tuple(r) for r in con.execute(f"SELECT * FROM {table}")]
        return cols, rows
    finally:
        con.close()


def main():
    db = Database(DB_URL)
    total = 0

    with db.connect() as target:
        for filename, tables in PLAN:
            src = ROOT / "data" / filename
            for table in tables:
                cols, rows = sqlite_rows(src, table)
                if not rows:
                    continue
                col_list = ", ".join(cols)
                placeholder = ", ".join("?" for _ in cols)  # auto-converted to %s for Postgres
                verb = f"INSERT INTO {table} ({col_list}) VALUES ({placeholder}) ON CONFLICT DO NOTHING"
                inserted = 0
                for row in rows:
                    try:
                        db.execute(target, verb, row)
                        inserted += 1
                    except Exception as exc:
                        print(f"  skip row in {table}: {exc}")
                total += inserted
                print(f"  {table}: {inserted} row(s) processed")

    if total == 0:
        print("Local SQLite data is empty - nothing to migrate. The cloud database starts fresh.")
    else:
        print(f"Migration complete: {total} row(s) processed.")


if __name__ == "__main__":
    main()
