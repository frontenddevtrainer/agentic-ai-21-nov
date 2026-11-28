from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from common.db import fetch
from demo2_support_desk.graph import build_graph
from tests.fake_llm import RuleLLM, ai, call, system_of


def order_id():
    return fetch("SELECT id FROM support.orders WHERE item='Webcam 4K'")[0]["id"]


def fake():
    oid = order_id()

    def fn(msgs):
        s = system_of(msgs)
        if "triage" in s:
            return ai("BILLING")
        n = sum(isinstance(m, ToolMessage) for m in msgs)
        if n == 0:
            return ai("", call("lookup_customer", email="ben@example.com"))
        if n == 1:
            return ai("", call("issue_refund", order_id=oid, amount=199.0, reason="lost in transit"))
        return ai("Done: " + str(msgs[-1].content))
    return RuleLLM(fn=fn)


def run(approved: bool, thread: str):
    g = build_graph(fake(), MemorySaver())
    cfg = {"configurable": {"thread_id": thread}}
    g.invoke({"messages": [HumanMessage(content="ben@example.com webcam never arrived, refund me")]}, cfg)
    task = g.get_state(cfg).tasks[0]
    assert task.interrupts[0].value["amount"] == 199.0  # graph is paused waiting for a human
    assert fetch("SELECT count(*) AS n FROM support.refunds")[0]["n"] == 0  # nothing happened yet
    out = g.invoke(Command(resume={"approved": approved, "by": "tester"}), cfg)
    return out["messages"][-1].content


def test_refund_approved():
    assert "approved and recorded" in run(True, "t-ok")
    assert fetch("SELECT count(*) AS n FROM support.refunds")[0]["n"] == 1
    assert fetch("SELECT status FROM support.orders WHERE item='Webcam 4K'")[0]["status"] == "refunded"


def test_refund_rejected():
    assert "NOT approved" in run(False, "t-no")
    assert fetch("SELECT count(*) AS n FROM support.refunds")[0]["n"] == 0
