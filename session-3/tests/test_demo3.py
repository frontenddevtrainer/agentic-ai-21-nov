from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import MemorySaver

from common.db import fetch
from demo3_research_team.graph import build_graph
from tests.fake_llm import RuleLLM, ai, call, system_of


def fake():
    def fn(msgs):
        s = system_of(msgs)
        if "research agent" in s:
            n = sum(isinstance(m, ToolMessage) for m in msgs)
            plan = [call("recall_notes", topic="checkpointing"),
                    call("search_sources", query="checkpointing sqlite resume"),
                    call("save_note", topic="checkpointing", content="Checkpointers save state per super-step.", source_id=3)]
            return ai("", plan[n]) if n < 3 else ai("- Checkpointers save state per step [source 3]")
        if "technical writer" in s:
            return ai("DRAFT v2 [source 3]" if "Reviewer feedback" in str(msgs[-1].content) else "DRAFT v1")
        return ai("APPROVE" if "DRAFT v2" in str(msgs[-1].content) else "REVISE: add citation")
    return RuleLLM(fn=fn)


def test_pause_resume_and_memory():
    cp = MemorySaver()
    cfg = {"configurable": {"thread_id": "r1"}}
    g = build_graph(fake(), cp, interrupt_after=["researcher"])
    g.invoke({"topic": "checkpointing"}, cfg)
    assert g.get_state(cfg).next == ("writer",)            # paused after research
    assert fetch("SELECT count(*) AS n FROM research.notes")[0]["n"] == 1   # memory written

    g2 = build_graph(fake(), cp, interrupt_after=["researcher"])  # "new process", same checkpoints
    out = g2.invoke(None, cfg)
    assert out["draft"] == "DRAFT v2 [source 3]" and out["rounds"] == 2
    rep = fetch("SELECT * FROM research.reports WHERE id=?", (out["report_id"],))[0]
    assert rep["review_rounds"] == 2

    # long-term memory: a later run's recall tool sees the earlier note
    from demo3_research_team.tools import recall_notes
    assert "Checkpointers save state" in recall_notes.invoke({"topic": "checkpointing"})
