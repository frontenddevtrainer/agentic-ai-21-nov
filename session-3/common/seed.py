"""Create and seed the demo databases.   python -m common.seed [--reset] [name ...]

Data is generated with a fixed random seed, so every machine gets the same rows.
"""
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

from common.db import DATABASES, ROOT, db_path

SCHEMA = ROOT / "db" / "schema"


def ensure_seeded() -> None:
    for name in DATABASES:
        if not db_path(name).exists():
            build(name)


def build(name: str) -> None:
    """(Re)create one database file from db/schema/<name>.sql plus its seed data."""
    path = db_path(name)
    for suffix in ("", "-wal", "-shm", "-journal"):
        Path(str(path) + suffix).unlink(missing_ok=True)
    tmp = path.with_suffix(".building")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript((SCHEMA / f"{name}.sql").read_text())
        SEEDERS[name](conn)
        conn.commit()
    finally:
        conn.close()
    tmp.rename(path)  # appears atomically, never half-built


def _many(conn, sql, rows):
    conn.executemany(sql, rows)


def seed_sales(conn):
    rnd = random.Random(42)
    countries = ["US", "UK", "DE", "IN", "AU", "CA"]
    segments = ["consumer", "consumer", "smb", "smb", "enterprise"]
    _many(conn, "INSERT INTO customers (name, country, segment, created_at) VALUES (?,?,?,?)",
          [(f"Customer {i}", rnd.choice(countries), rnd.choice(segments),
            (date(2025, 1, 1) + timedelta(days=rnd.randrange(300))).isoformat()) for i in range(1, 61)])
    products = [("Agent Starter Kit", "software", 49), ("Vector DB Pro (annual)", "software", 299),
                ("Prompt Library", "software", 19), ("GPU Credits 100h", "compute", 150),
                ("GPU Credits 1000h", "compute", 1300), ("Workshop Seat", "training", 500),
                ("Team Training Day", "training", 4000), ("Support Plan", "services", 900)]
    _many(conn, "INSERT INTO products (name, category, price) VALUES (?,?,?)", products)
    statuses = ["paid"] * 7 + ["refunded", "cancelled"]
    for oid in range(1, 401):
        conn.execute("INSERT INTO orders (customer_id, ordered_at, status) VALUES (?,?,?)",
                     (rnd.randint(1, 60), (date(2025, 6, 1) + timedelta(days=rnd.randrange(180))).isoformat(),
                      rnd.choice(statuses)))
        for pid in rnd.sample(range(1, 9), 1 + oid % 3):
            conn.execute("INSERT INTO order_items VALUES (?,?,?,?)",
                         (oid, pid, rnd.randint(1, 3), products[pid - 1][2]))


def seed_support(conn):
    today = date.today()
    d = lambda n: (today - timedelta(days=n)).isoformat()  # noqa: E731
    _many(conn, "INSERT INTO customers (email, name, plan) VALUES (?,?,?)",
          [("asha@example.com", "Asha Rao", "pro"), ("ben@example.com", "Ben Carter", "free"),
           ("chloe@example.com", "Chloe Dubois", "enterprise"), ("dev@example.com", "Dev Patel", "pro")])
    _many(conn, "INSERT INTO orders (customer_id, item, total, status, placed_at, tracking) VALUES (?,?,?,?,?,?)",
          [(1, "Mechanical Keyboard", 129.00, "delivered", d(20), "TRK1001"),
           (1, "USB-C Dock", 89.50, "shipped", d(3), "TRK1002"),
           (2, "Webcam 4K", 199.00, "lost", d(15), "TRK2001"),
           (2, "Desk Mat", 25.00, "delivered", d(40), "TRK2002"),
           (3, "Monitor Arm x10", 1450.00, "delivered", d(12), "TRK3001"),
           (3, "Headsets x10", 2200.00, "processing", d(1), None),
           (4, "Laptop Stand", 59.00, "delivered", d(8), "TRK4001")])


SOURCES = [
 ("What is an agent loop?", "https://example.org/agent-loop",
  "An agent loop alternates between a model call and tool execution. The model decides whether to call a tool or answer; tool results are appended to the message history and the model is called again. The loop ends when the model answers without requesting a tool. Guard rails include a maximum step count and per-tool timeouts."),
 ("LangGraph state and reducers", "https://example.org/langgraph-state",
  "LangGraph models an agent as a graph over a typed state. Each node returns a partial state update and reducers decide how updates merge, for example add_messages appends to a message list. Conditional edges route between nodes, which makes loops, retries and branches explicit instead of hidden in prompt text."),
 ("Checkpointing and persistence", "https://example.org/checkpointing",
  "A checkpointer saves the graph state after every super-step, keyed by thread id. With a database-backed checkpointer a run can be stopped and resumed later, a conversation can continue across processes, and any past step can be replayed or forked for debugging."),
 ("Human-in-the-loop with interrupts", "https://example.org/hitl",
  "The interrupt function pauses a graph and surfaces a payload to a human. When the run is resumed with a Command carrying the human decision, execution continues from the same node. Use it for approvals on irreversible actions such as refunds, deployments and purchase orders."),
 ("Multi-agent patterns", "https://example.org/multi-agent",
  "Common multi-agent topologies are supervisor, where one agent routes work to specialists; pipeline, where agents hand off in sequence; and debate or critic loops, where a reviewer sends drafts back for revision. Specialists with small tool sets are more reliable than one agent with every tool."),
 ("Tool design for agents", "https://example.org/tool-design",
  "Good tools have narrow purposes, descriptive names, typed arguments and errors that explain how to fix the call. Read-only tools should be separated from tools that change state, and state-changing tools should be idempotent or gated behind approval. Return concise structured results rather than raw dumps."),
 ("Text-to-SQL safety", "https://example.org/text-to-sql",
  "Letting a model write SQL is safe only with layers: a read-only database connection, a statement timeout, a row limit, and a validator that rejects anything but SELECT. Give the model schema introspection tools so it can inspect columns before writing queries, and feed SQL errors back so it can self-correct."),
 ("Evaluating agents", "https://example.org/evals",
  "Evaluate agents on trajectories as well as final answers: which tools were called, in what order, with what arguments. Keep a regression set of tasks, run it on every prompt or model change, and store traces so failures can be replayed from a checkpoint."),
]


def seed_research(conn):
    for i, (title, url, body) in enumerate(SOURCES, 1):
        conn.execute("INSERT INTO sources (id, title, url, body) VALUES (?,?,?,?)", (i, title, url, body))
        conn.execute("INSERT INTO sources_fts (rowid, title, body) VALUES (?,?,?)", (i, title, body))


def seed_ops(conn):
    _many(conn, "INSERT INTO jobs (id, name, status, attempts, max_attempts, will_succeed_on_retry) VALUES (?,?,?,?,?,?)",
          [(1, "ingest_orders", "succeeded", 1, 3, 0),
           (2, "ingest_clickstream", "failed", 1, 3, 1),      # transient: safe to retry
           (3, "build_customer_360", "failed", 1, 3, 0),      # schema drift: needs a human
           (4, "train_churn_model", "failed", 3, 3, 0),       # out of memory, retries exhausted
           (5, "export_finance_report", "succeeded", 1, 3, 0),
           (6, "refresh_dashboards", "running", 1, 3, 0),
           (7, "sync_crm", "succeeded", 1, 3, 0)])
    _many(conn, "INSERT INTO job_logs (job_id, level, message) VALUES (?,?,?)", [
        (1, "INFO", "ingest_orders finished: 15210 rows"),
        (2, "INFO", "Starting ingest_clickstream batch 2026-11-27"),
        (2, "WARN", "Connection to kafka-broker-3 slow (4200ms)"),
        (2, "ERROR", "ReadTimeout: broker kafka-broker-3:9092 did not respond within 30s"),
        (2, "ERROR", "Job aborted before any rows were committed (transaction rolled back)"),
        (3, "INFO", "Starting build_customer_360"),
        (3, "ERROR", 'UndefinedColumn: column "loyalty_tier" of relation "customers" does not exist'),
        (3, "ERROR", "Upstream table crm.customers changed shape; mapping needs updating by a data engineer"),
        (4, "INFO", "Starting train_churn_model (attempt 3 of 3)"),
        (4, "ERROR", "MemoryError: unable to allocate 38.2 GiB for array with shape (9100000, 4500)"),
        (4, "ERROR", "Retrying will fail the same way: dataset has grown past worker memory"),
        (5, "INFO", "export_finance_report finished"),
        (7, "INFO", "sync_crm finished: 311 contacts")])


def seed_inventory(conn):
    _many(conn, "INSERT INTO suppliers (name, lead_time_days, min_order_value) VALUES (?,?,?)",
          [("Northwind Components", 7, 500), ("Globex Hardware", 14, 2000), ("Initech Cables", 3, 100)])
    _many(conn, "INSERT INTO products (sku, name, unit_cost, supplier_id, stock_on_hand, on_order, reorder_point) "
                "VALUES (?,?,?,?,?,?,?)",
          [("NW-100", "Sensor board", 12.50, 1, 40, 0, 120),     # low
           ("NW-200", "Controller", 48.00, 1, 300, 0, 100),      # fine
           ("GH-100", "Server chassis", 640.00, 2, 6, 0, 15),    # low and expensive -> needs approval
           ("GH-200", "Rack rails", 35.00, 2, 90, 50, 60),       # covered by an open order
           ("IN-100", "Power cable", 3.20, 3, 150, 0, 400),      # low and cheap -> auto-approve
           ("IN-200", "Ethernet cable", 2.10, 3, 900, 0, 300)])  # fine
    monday = date.today() - timedelta(days=date.today().weekday())
    base = {1: lambda w: 55 - w * 2, 2: lambda w: 20, 3: lambda w: 8 - w * 0.3,
            4: lambda w: 18, 5: lambda w: 130 - w * 4, 6: lambda w: 60}  # product id -> weekly demand (with a trend)
    for pid, f in base.items():
        for w in range(1, 13):
            conn.execute("INSERT INTO demand_history VALUES (?,?,?)",
                         (pid, (monday - timedelta(weeks=w)).isoformat(), max(1, round(f(w) + w % 3))))


SEEDERS = {"sales": seed_sales, "support": seed_support, "research": seed_research,
           "ops": seed_ops, "inventory": seed_inventory}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")] or DATABASES
    force = "--reset" in sys.argv
    for n in args:
        if force or not db_path(n).exists():
            build(n)
            print(f"seeded {db_path(n)}")
        else:
            print(f"{db_path(n)} exists (use --reset to rebuild)")