"""SQLite helpers shared by every demo's tools.

Each demo owns one SQLite file in data/ (sales.db, support.db, ...). A connection
ATTACHes them under their own names, so SQL reads like a multi-schema database:
`support.orders`, `ops.jobs`, ... The files are created and seeded automatically the
first time they are needed - there is nothing to install or start.
"""
import json
import os
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATABASES = ["sales", "support", "research", "ops", "inventory"]
ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    d = Path(os.environ.get("DEMO_DATA_DIR", ROOT / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path(name: str) -> Path:
    return data_dir() / f"{name}.db"


def checkpoint_path() -> Path:
    """LangGraph checkpoints (graph state per thread) live in their own file."""
    return data_dir() / "checkpoints.db"


def _connect(readonly: bool = False, only: list[str] | None = None) -> sqlite3.Connection:
    from common.seed import ensure_seeded

    ensure_seeded()
    conn = sqlite3.connect(":memory:", uri=True, isolation_level=None)  # autocommit per statement
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    for name in only or DATABASES:
        uri = db_path(name).resolve().as_uri() + ("?mode=ro" if readonly else "")
        conn.execute(f"ATTACH DATABASE '{uri}' AS {name}")
    if readonly:
        conn.execute("PRAGMA query_only = ON")  # layer 2: the connection itself refuses writes
        deadline = time.monotonic() + 5.0  # layer 3: statement timeout

        def too_slow() -> int:
            return 1 if time.monotonic() > deadline else 0

        conn.set_progress_handler(too_slow, 10_000)
    return conn


def fetch(sql: str, params=(), *, readonly: bool = False, only: list[str] | None = None) -> list[dict]:
    """Run one statement, return rows as dicts (works for INSERT ... RETURNING too)."""
    conn = _connect(readonly, only)
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []
    finally:
        conn.close()


def placeholders(n: int) -> str:
    return ",".join("?" * n)


def as_json(obj) -> str:
    """Tool results go back to the model as text."""
    return json.dumps(obj, default=str)
