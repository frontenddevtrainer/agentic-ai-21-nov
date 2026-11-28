"""Demo 3 - Research & report team with long-term memory.

    researcher (tools: recall / search / save notes)
        -> writer -> reviewer --revise--> writer     (max 2 rounds)
                         |
                      publish (saves the report to SQLite)

Two kinds of SQLite persistence:
  * research.notes / research.reports   - the team's long-term memory (your tables)
  * the checkpointer                    - per-run state, so you can stop after the
                                          researcher and resume the same thread later.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import NotRequired, TypedDict

from common.agents import react_subgraph, text_of
from common.db import fetch
from demo3_research_team.tools import RESEARCH_TOOLS

MAX_ROUNDS = 2


class State(TypedDict):
    topic: str
    findings: NotRequired[str]
    draft: NotRequired[str]
    feedback: NotRequired[str]
    rounds: NotRequired[int]
    report_id: NotRequired[int]


RESEARCHER = (
    "You are a research agent. First call recall_notes for the topic - reuse what we already know. "
    "Then call search_sources (try 1-3 queries) to fill gaps. For every NEW fact worth keeping call "
    "save_note with a one-or-two sentence finding and the source_id. Finish with a bullet list of the "
    "findings, each ending with [source <id>]. Do not invent facts that are not in the tools' output."
)
WRITER = (
    "You are a technical writer. Write a clear 250-400 word briefing in Markdown on the topic using "
    "ONLY the findings provided. Cite sources inline like [source 3]. If reviewer feedback is "
    "given, address every point."
)
REVIEWER = (
    "You are a strict editor. Check the draft against the findings: every claim supported and cited, "
    "nothing invented, clear structure. Reply with exactly 'APPROVE' or 'REVISE: <specific fixes>'."
)


def build_graph(llm, checkpointer=None, interrupt_after=None):
    researcher_agent = react_subgraph(llm, RESEARCH_TOOLS, RESEARCHER)

    def researcher(state: State):
        # The sub-agent keeps its own private message history; only its final text escapes.
        out = researcher_agent.invoke({"messages": [HumanMessage(content=f"Topic: {state['topic']}")]})
        return {"findings": text_of(out["messages"][-1]), "rounds": 0}

    def writer(state: State):
        prompt = f"Topic: {state['topic']}\n\nFindings:\n{state['findings']}"
        if state.get("feedback"):
            prompt += f"\n\nPrevious draft:\n{state['draft']}\n\nReviewer feedback:\n{state['feedback']}"
        return {"draft": text_of(llm.invoke([SystemMessage(content=WRITER), HumanMessage(content=prompt)]))}

    def reviewer(state: State):
        prompt = f"Findings:\n{state['findings']}\n\nDraft:\n{state['draft']}"
        verdict = text_of(llm.invoke([SystemMessage(content=REVIEWER), HumanMessage(content=prompt)])).strip()
        return {"feedback": "" if verdict.upper().startswith("APPROVE") else verdict,
                "rounds": state.get("rounds", 0) + 1}

    def after_review(state: State):
        return "publish" if not state["feedback"] or state["rounds"] > MAX_ROUNDS else "writer"

    def publish(state: State):
        row = fetch(
            "INSERT INTO research.reports (topic, body, review_rounds) VALUES (?,?,?) RETURNING id",
            (state["topic"], state["draft"], state["rounds"]),
        )[0]
        return {"report_id": row["id"]}

    g = StateGraph(State)
    g.add_node("researcher", researcher)
    g.add_node("writer", writer)
    g.add_node("reviewer", reviewer)
    g.add_node("publish", publish)
    g.add_edge(START, "researcher")
    g.add_edge("researcher", "writer")
    g.add_edge("writer", "reviewer")
    g.add_conditional_edges("reviewer", after_review, {"writer": "writer", "publish": "publish"})
    g.add_edge("publish", END)
    return g.compile(checkpointer=checkpointer, interrupt_after=interrupt_after)
