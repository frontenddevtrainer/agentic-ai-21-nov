import re

from langchain_core.tools import tool

from common.db import as_json, fetch

MAX_ROWS = 50
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|attach|detach|pragma|vacuum|reindex)\b", re.I
)


def q(sql: str, params=()):
    """Every query in this demo goes through a READ-ONLY connection to the sales database only."""
    return fetch(sql, params, readonly=True, only=["sales"])


def _guard(sql: str) -> str | None:
    """Layer 1: reject anything that isn't a single SELECT/WITH statement."""
    s = sql.strip().rstrip(";")
    if ";" in s:
        return "Only one statement is allowed."
    if not re.match(r"^(select|with)\b", s, re.I):
        return "Only SELECT queries are allowed."
    if _FORBIDDEN.search(s):
        return "Query contains a forbidden keyword; only read-only SELECTs are allowed."
    return None


@tool
def list_tables() -> str:
    """List every table in the sales database with its row count."""
    names = [r["name"] for r in q("SELECT name FROM sales.sqlite_master WHERE type='table' ORDER BY name")]
    return as_json([{"table": n, "rows": q(f'SELECT count(*) AS n FROM sales."{n}"')[0]["n"]} for n in names])


@tool
def describe_table(table: str) -> str:
    """Show columns, types and three sample rows for one table (e.g. 'orders')."""
    exists = q("SELECT 1 FROM sales.sqlite_master WHERE type='table' AND name=?", (table,))
    if not exists:
        return f"No table named '{table}'. Call list_tables to see what exists."
    cols = q("SELECT name AS column_name, type AS data_type FROM pragma_table_info(?, 'sales')", (table,))
    sample = q(f'SELECT * FROM sales."{table}" LIMIT 3')
    return as_json({"columns": cols, "sample_rows": sample})


@tool
def run_readonly_query(sql: str) -> str:
    """Run one read-only SELECT against the sales database (use plain table names like orders,
    customers). At most 50 rows are returned. On error the message explains what to fix."""
    problem = _guard(sql)
    if problem:
        return f"REJECTED: {problem}"
    try:
        # Layer 2+3: read-only connection with a 5 second timeout (see common/db.py).
        rows = q(f"SELECT * FROM ({sql.strip().rstrip(';')}) LIMIT {MAX_ROWS}")
    except Exception as e:  # fed back to the model so it can fix its own SQL
        return f"SQL ERROR: {e}"
    return as_json({"row_count": len(rows), "rows": rows})


TOOLS = [list_tables, describe_table, run_readonly_query]
