import re

from langchain_core.messages import HumanMessage, ToolMessage

from common.db import fetch
from demo4_pipeline_ops.graph import build_graph
from tests.fake_llm import RuleLLM, ai, call, system_of


def fake():
    def fn(msgs):
        s = system_of(msgs)
        human = str(next(m for m in msgs if isinstance(m, HumanMessage)).content)
        if "diagnoser" in s:
            jid = int(re.search(r"job (\d+)", human).group(1))
            if not any(isinstance(m, ToolMessage) for m in msgs):
                return ai("", call("read_logs", job_id=jid))
            verdict = "RETRY" if jid == 2 else "ESCALATE"
            return ai(f"JOB {jid} x\nCAUSE: c\nVERDICT: {verdict}")
        if "fixer" in s:
            if any(isinstance(m, ToolMessage) for m in msgs):
                return ai("fixed")
            calls = [call("retry_job", job_id=2),
                     call("retry_job", job_id=4),   # guard should refuse: attempts exhausted
                     call("write_incident", job_id=3, severity="medium", summary="schema drift"),
                     call("write_incident", job_id=4, severity="high", summary="OOM")]
            return ai("", *calls)
        return ai("Handoff: 3 failed, 1 auto-fixed, 2 escalated.")
    return RuleLLM(fn=fn)


def test_parallel_diagnose_then_fix():
    out = build_graph(fake()).invoke({"diagnoses": []})
    assert len(out["failed"]) == 3 and len(out["diagnoses"]) == 3   # 3 branches merged by the reducer
    status = {r["id"]: r["status"] for r in fetch("SELECT id, status FROM ops.jobs")}
    assert status[2] == "succeeded"           # retried
    assert status[4] == "failed"              # retry refused by the tool, not by the prompt
    assert len(fetch("SELECT * FROM ops.incidents")) == 2
    actions = [r["action"] for r in fetch("SELECT action FROM ops.audit_log")]
    assert actions.count("read_logs") == 3 and "retry_refused" in actions
    assert "Handoff" in out["report"]
