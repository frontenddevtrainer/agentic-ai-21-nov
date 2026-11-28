from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from common.db import fetch
from demo5_procurement.graph import build_graph
from tests.fake_llm import RuleLLM, ai, call, system_of


def fake():
    def fn(msgs):
        s = system_of(msgs)
        n = sum(isinstance(m, ToolMessage) for m in msgs)
        if "inventory checker" in s:
            return ai("", call("low_stock_report")) if n == 0 else ai("1 | NW-100 | ... \n3 | GH-100 | ... \n5 | IN-100 | ...")
        if "demand forecaster" in s:
            ids = [1, 3, 5]
            return ai("", call("forecast_demand", product_id=ids[n], weeks_ahead=6)) if n < 3 else ai("1|1|300|x\n3|2|20|y\n5|3|1000|z")
        po = [call("create_purchase_order", supplier_id=1, lines=[{"product_id": 1, "qty": 300}]),     # 3750  auto
              call("create_purchase_order", supplier_id=2, lines=[{"product_id": 3, "qty": 20}]),      # 12800 human
              call("create_purchase_order", supplier_id=3, lines=[{"product_id": 5, "qty": 1000}])]    # 3200  auto
        return ai("", po[n]) if n < 3 else ai("3 POs drafted")
    return RuleLLM(fn=fn)


def test_forecast_tool_uses_trend():
    from demo5_procurement.tools import forecast_demand
    import json
    f = json.loads(forecast_demand.invoke({"product_id": 1, "weeks_ahead": 6}))
    assert f["trend_per_week"] < 0 or f["trend_per_week"] > 0   # declining/rising history -> non-flat
    assert f["forecast_units_total"] > 0


def test_small_auto_big_waits_for_human():
    g = build_graph(fake(), MemorySaver())
    cfg = {"configurable": {"thread_id": "p1"}}
    g.invoke({}, cfg)
    ask = g.get_state(cfg).tasks[0].interrupts[0].value
    assert [p["supplier"] for p in ask["needs_approval"]] == ["Globex Hardware"]
    st = {r["supplier_id"]: r["status"] for r in fetch("SELECT supplier_id, status FROM inventory.purchase_orders")}
    assert st == {1: "approved", 2: "pending_approval", 3: "approved"}

    big_id = str(ask["needs_approval"][0]["id"])
    out = g.invoke(Command(resume={big_id: False}), cfg)
    assert "rejected (human)" in out["summary"] and "approved (auto)" in out["summary"]
