"""The real thing the demos use: SqliteSaver. Pause in one 'process', resume in another."""
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from common.checkpoint import sqlite_saver
from common.db import fetch
from demo2_support_desk.graph import build_graph
from tests.test_demo2 import fake


def test_pause_survives_restart():
    cfg = {"configurable": {"thread_id": "restart-test"}}
    with sqlite_saver() as saver:                         # "process 1"
        g = build_graph(fake(), saver)
        g.invoke({"messages": [HumanMessage(content="ben@example.com refund my webcam")]}, cfg)
        assert g.get_state(cfg).tasks[0].interrupts
    with sqlite_saver() as saver:                         # "process 2" - fresh connection, fresh graph
        g = build_graph(fake(), saver)
        assert g.get_state(cfg).tasks[0].interrupts[0].value["amount"] == 199.0
        g.invoke(Command(resume={"approved": True, "by": "tester"}), cfg)
    assert fetch("SELECT count(*) AS n FROM support.refunds")[0]["n"] == 1
