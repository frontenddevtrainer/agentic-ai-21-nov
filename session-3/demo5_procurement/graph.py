"""Demo 5 - Inventory & procurement, with agents as sub-graphs and an approval gate.

    checker -> forecaster -> buyer -> approver -> END

Each of the first three stages is a tool-using agent sub-graph with PRIVATE messages;
the parent state only carries the small hand-off values (low_stock, forecast, po_ids).
`approver` is plain code: POs <= 5000 are approved automatically, bigger ones pause with
interrupt() for a human, and the decision is written back to SQLite.
"""
import re

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import NotRequired, TypedDict

from common.agents import react_subgraph, text_of
from common.db import fetch, placeholders
from demo5_procurement.tools import AUTO_APPROVE_LIMIT, BUYER_TOOLS, CHECKER_TOOLS, FORECASTER_TOOLS


class State(TypedDict):
    low_stock: NotRequired[str]
    forecast: NotRequired[str]
    po_ids: NotRequired[list[int]]
    buyer_notes: NotRequired[str]
    summary: NotRequired[str]


CHECKER = (
    "You are an inventory checker. Call low_stock_report and list each product that needs "
    "restocking as: id | sku | name | supplier_id | unit_cost | stock_on_hand | on_order | reorder_point. "
    "Output only that list."
)
FORECASTER = (
    "You are a demand forecaster. For EVERY product in the list call forecast_demand with weeks_ahead=6. "
    "Then for each product recommend an order quantity = forecast_units_total + reorder_point - "
    "(stock_on_hand + on_order), rounded up to a multiple of 10, minimum 10. "
    "Output one line per product: product_id | supplier_id | qty | reasoning."
)
BUYER = (
    "You are a buyer. Group the recommended lines by supplier_id and create ONE draft purchase order "
    "per supplier with create_purchase_order. If a tool says the minimum order value is not met, raise "
    "quantities and retry. Finish with one line per PO: 'PO <id> | supplier | total'."
)


def build_graph(llm, checkpointer=None):
    checker_agent = react_subgraph(llm, CHECKER_TOOLS, CHECKER)
    forecaster_agent = react_subgraph(llm, FORECASTER_TOOLS, FORECASTER)
    buyer_agent = react_subgraph(llm, BUYER_TOOLS, BUYER)

    def run(agent, prompt: str) -> str:
        return text_of(agent.invoke({"messages": [HumanMessage(content=prompt)]})["messages"][-1])

    def checker(state: State):
        return {"low_stock": run(checker_agent, "Which products need restocking?")}

    def forecaster(state: State):
        return {"forecast": run(forecaster_agent, f"Products:\n{state['low_stock']}")}

    def buyer(state: State):
        notes = run(buyer_agent, f"Recommended order lines:\n{state['forecast']}")
        # Source of truth is the database, not the model's prose: pick up the drafts it created.
        ids = [r["id"] for r in fetch("SELECT id FROM inventory.purchase_orders WHERE status='pending_approval' ORDER BY id")]
        return {"buyer_notes": notes, "po_ids": ids}

    def approver(state: State):
        ids = state.get("po_ids", [])
        pos = fetch(
            "SELECT po.id, po.total, s.name AS supplier FROM inventory.purchase_orders po "
            "JOIN inventory.suppliers s ON s.id=po.supplier_id WHERE po.id IN (" + placeholders(len(ids)) + ") AND po.status='pending_approval'",
            ids,
        )
        small = [p for p in pos if float(p["total"]) <= AUTO_APPROVE_LIMIT]
        big = [p for p in pos if float(p["total"]) > AUTO_APPROVE_LIMIT]

        for p in small:
            fetch("UPDATE inventory.purchase_orders SET status='approved', decided_by='auto' WHERE id=?", (p["id"],))

        decisions: dict = {}
        if big:
            # Pauses here. Resume with Command(resume={"<po_id>": True/False, ...}).
            decisions = interrupt({"needs_approval": [{**p, "total": float(p["total"])} for p in big],
                                   "limit": AUTO_APPROVE_LIMIT})
        for p in big:
            ok = bool(decisions.get(str(p["id"]), False))
            fetch("UPDATE inventory.purchase_orders SET status=?, decided_by='human' WHERE id=?",
                  ("approved" if ok else "rejected", p["id"]))

        rows = fetch("SELECT id, status, total, decided_by FROM inventory.purchase_orders WHERE id IN (" + placeholders(len(ids)) + ") ORDER BY id", ids)
        lines = [f"PO #{r['id']}: {r['status']} ({r['decided_by']}), total {float(r['total']):.2f}" for r in rows]
        return {"summary": "\n".join(lines) or "No purchase orders were needed."}

    g = StateGraph(State)
    g.add_node("checker", checker)
    g.add_node("forecaster", forecaster)
    g.add_node("buyer", buyer)
    g.add_node("approver", approver)
    g.add_edge(START, "checker")
    g.add_edge("checker", "forecaster")
    g.add_edge("forecaster", "buyer")
    g.add_edge("buyer", "approver")
    g.add_edge("approver", END)
    return g.compile(checkpointer=checkpointer)
