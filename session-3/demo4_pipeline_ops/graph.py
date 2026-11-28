"""Demo 4 - Data pipeline ops crew.

    monitor --(Send per failed job)--> diagnoser x N   (run in PARALLEL)
                                             |  (results merged by a reducer)
                                           fixer  --> reporter --> END

monitor   plain Python node: finds failed jobs (no LLM needed for that)
diagnoser LLM + read-only tools: reads logs, classifies RETRY or ESCALATE
fixer     LLM + write tools: retries or opens incidents (tools enforce the rules)
reporter  LLM: writes the shift summary

Every tool call lands in ops.audit_log, so there is a full audit trail.
"""
import operator
from typing import Annotated

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import NotRequired, TypedDict

from common.agents import react_subgraph, text_of
from demo4_pipeline_ops.tools import DIAGNOSE_TOOLS, FIX_TOOLS, failed_jobs


class State(TypedDict):
    failed: NotRequired[list[dict]]
    diagnoses: Annotated[list[str], operator.add]  # reducer: parallel branches append here
    actions: NotRequired[str]
    report: NotRequired[str]


class JobInput(TypedDict):
    job: dict


DIAGNOSER = (
    "You are a pipeline diagnoser. Use read_logs (and check_job_status) for the job, find the root "
    "cause, and answer in exactly this format:\n"
    "JOB <id> <name>\nCAUSE: <one sentence>\nVERDICT: RETRY or ESCALATE\n"
    "Choose RETRY only for transient problems (timeouts, brief outages) when attempts remain. "
    "Choose ESCALATE for code/schema/data problems, resource exhaustion, or when attempts are used up."
)
FIXER = (
    "You are the pipeline fixer. For each diagnosis: if VERDICT is RETRY call retry_job; if ESCALATE "
    "call write_incident (severity high for exhausted attempts or data loss risk, otherwise medium) "
    "with a clear summary of the cause. If retry_job is refused, open an incident instead. "
    "When done, list what you did per job, one line each."
)
REPORTER = (
    "You write the on-call handoff note. In under 120 words: how many jobs failed, what was fixed "
    "automatically, what needs a human and why. Use plain language."
)


def build_graph(llm, checkpointer=None):
    diagnoser_agent = react_subgraph(llm, DIAGNOSE_TOOLS, DIAGNOSER)
    fixer_agent = react_subgraph(llm, FIX_TOOLS, FIXER)

    def monitor(state: State):
        return {"failed": failed_jobs()}

    def fan_out(state: State):
        if not state["failed"]:
            return "reporter"
        return [Send("diagnoser", {"job": j}) for j in state["failed"]]

    def diagnoser(state: JobInput):
        j = state["job"]
        out = diagnoser_agent.invoke(
            {"messages": [HumanMessage(content=f"Diagnose job {j['id']} ({j['name']}), "
                                                f"attempt {j['attempts']} of {j['max_attempts']}.")]}
        )
        return {"diagnoses": [text_of(out["messages"][-1])]}

    def fixer(state: State):
        brief = "\n\n".join(sorted(state["diagnoses"]))
        out = fixer_agent.invoke({"messages": [HumanMessage(content=f"Diagnoses:\n{brief}")]})
        return {"actions": text_of(out["messages"][-1])}

    def reporter(state: State):
        if not state["failed"]:
            return {"report": "All pipelines healthy - nothing failed this shift."}
        prompt = f"Failed jobs: {len(state['failed'])}\n\nDiagnoses:\n" + "\n\n".join(state["diagnoses"]) \
                 + f"\n\nActions taken:\n{state['actions']}"
        return {"report": text_of(llm.invoke([HumanMessage(content=REPORTER + "\n\n" + prompt)]))}

    g = StateGraph(State)
    g.add_node("monitor", monitor)
    g.add_node("diagnoser", diagnoser)
    g.add_node("fixer", fixer)
    g.add_node("reporter", reporter)
    g.add_edge(START, "monitor")
    g.add_conditional_edges("monitor", fan_out, ["diagnoser", "reporter"])
    g.add_edge("diagnoser", "fixer")  # waits for ALL parallel diagnosers
    g.add_edge("fixer", "reporter")
    g.add_edge("reporter", END)
    return g.compile(checkpointer=checkpointer)
