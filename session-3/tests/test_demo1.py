from langchain_core.messages import HumanMessage, ToolMessage

from demo1_text_to_sql.graph import build_graph
from demo1_text_to_sql.tools import run_readonly_query
from tests.fake_llm import RuleLLM, ai, call, system_of

GOOD = ("SELECT c.country, sum(oi.qty*oi.unit_price) AS revenue FROM orders o "
        "JOIN customers c ON c.id=o.customer_id JOIN order_items oi ON oi.order_id=o.id "
        "WHERE o.status='paid' GROUP BY 1 ORDER BY 2 DESC LIMIT 3")


def test_guard_blocks_writes():
    assert "REJECTED" in run_readonly_query.invoke({"sql": "DELETE FROM orders"})
    assert "REJECTED" in run_readonly_query.invoke({"sql": "SELECT 1; DROP TABLE orders"})
    assert "SQL ERROR" in run_readonly_query.invoke({"sql": "SELECT nope FROM orders"})
    assert '"row_count"' in run_readonly_query.invoke({"sql": "SELECT 1 AS x"})


def test_connection_is_read_only_even_without_guard():
    # bypass _guard entirely: the connection itself must refuse writes (last line of defence)
    import sqlite3

    from common.db import fetch

    for sql in ("DELETE FROM sales.orders", "DROP TABLE sales.orders", "UPDATE sales.products SET price=0"):
        try:
            fetch(sql, readonly=True, only=["sales"])
            assert False, f"{sql} should have failed"
        except sqlite3.OperationalError:
            pass
    assert fetch("SELECT count(*) AS n FROM sales.orders", only=["sales"])[0]["n"] == 400  # still intact


def test_slow_query_is_cut_off():
    out = run_readonly_query.invoke({"sql": "WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM r) SELECT count(*) FROM r"})
    assert "SQL ERROR" in out and "interrupt" in out.lower()


def test_writer_self_corrects_and_critic_loop():
    def fn(msgs):
        s = system_of(msgs)
        if "planner" in s:
            return ai("- revenue by country, paid only")
        if "SQLite analyst" in s:
            tool_msgs = [m for m in msgs if isinstance(m, ToolMessage)]
            revised = any(isinstance(m, HumanMessage) and "Reviewer feedback" in str(m.content) for m in msgs)
            if not tool_msgs:
                return ai("", call("list_tables"))
            if len(tool_msgs) == 1:
                return ai("", call("run_readonly_query", sql="SELECT country_name FROM customers"))  # wrong column
            if len(tool_msgs) == 2:
                return ai("", call("run_readonly_query", sql=GOOD))
            return ai(f"```sql\n{GOOD}\n```\nrows ok" + (" (revised)" if revised else ""))
        if "review" in s:
            seen = sum(1 for m in msgs if "revised" in str(m.content))
            return ai("APPROVE" if seen else "REVISE: also state the number of orders")
        return ai("Top countries are X, Y, Z.")

    g = build_graph(RuleLLM(fn=fn))
    out = g.invoke({"question": "Top 3 countries by revenue?"})
    assert out["answer"].startswith("Top countries")
    assert out["revisions"] == 1
    tool_results = [m.content for m in out["messages"] if isinstance(m, ToolMessage)]
    assert any("SQL ERROR" in t for t in tool_results)  # it saw the error and corrected itself
    assert any('"row_count": 3' in t for t in tool_results)
