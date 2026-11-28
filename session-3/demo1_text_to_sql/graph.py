from typing import Annotated

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from common.agents import text_of
from demo1_text_to_sql.tools import TOOLS

MAX_REVISIONS = 2

class SalesState(TypedDict, total=False):
    question: str
    plan: str
    messages: Annotated[list, add_messages]  # the SQL writer's working conversation
    critique: str
    revisions: int
    answer: str


PLANNER = (
    "You are a data analysis planner. Given a business question about a sales database, "
    "write a SHORT plan (max 4 bullets): which entities are involved, which metrics, filters, "
    "grouping and ordering. Do not write SQL."
)
WRITER = (
    "You are a careful SQLite analyst. Use list_tables / describe_table to learn the schema "
    "before writing SQL. Run your query with run_readonly_query. If it errors, read the error and "
    "fix the query. Revenue = sum(order_items.qty * order_items.unit_price) over orders whose status "
    "is 'paid'; round money to 2 decimals. The database is SQLite. When you have the data, reply with the final SQL in a ```sql block followed by the "
    "key rows of the result. Never invent numbers."
)
CRITIC = (
    "You review an analyst's work. Check the SQL and results against the question and plan: right "
    "tables, right filters (paid orders only for revenue), sensible grouping, results actually answer "
    "the question. Reply with exactly 'APPROVE' or 'REVISE: <one concrete fix>'."
)
SUMMARIZER = (
    "Answer the business question in 2-4 plain sentences using ONLY the analyst's results. "
    "Include the key numbers. End with the SQL in a ```sql block."
)


def build_graph(llm, checkpointer=None):

    # llm - Haiku without tools
    # writer_llm - Haiku with tools

    writer_llm = llm.bind_tools(TOOLS)

    def planner(state: SalesState):
        msg = llm.invoke([SystemMessage(content=PLANNER), HumanMessage(content=state["question"])])
        return {
            "plan": text_of(msg),
            "revisions": 0,
            "messages": [HumanMessage(content=f"Question: {state['question']}\n\nPlan:\n{text_of(msg)}")],
        }

    def sql_writer(state: SalesState):
        return {"messages": [writer_llm.invoke([SystemMessage(content=WRITER)] + state["messages"])]}

    def critic(state: SalesState):
        last = state["messages"][-1]
        prompt = f"Question: {state['question']}\n\nPlan:\n{state['plan']}\n\nAnalyst's work:\n{text_of(last)}"
        verdict = text_of(llm.invoke([SystemMessage(content=CRITIC), HumanMessage(content=prompt)])).strip()
        out: dict = {"critique": verdict}
        if not verdict.upper().startswith("APPROVE"):
            out["revisions"] = state.get("revisions", 0) + 1
            out["messages"] = [HumanMessage(content=f"Reviewer feedback - please fix and re-run: {verdict}")]
        return out

    def after_critic(state: SalesState):
        approved = state["critique"].upper().startswith("APPROVE")
        return "summarizer" if approved or state.get("revisions", 0) > MAX_REVISIONS else "sql_writer"

    def summarizer(state: SalesState):
        ai = [m for m in state["messages"] if isinstance(m, AIMessage) and not m.tool_calls]
        work = text_of(ai[-1]) if ai else "(no result)"
        msg = llm.invoke(
            [SystemMessage(content=SUMMARIZER), HumanMessage(content=f"Question: {state['question']}\n\n{work}")]
        )
        return {"answer": text_of(msg)}

    g = StateGraph(SalesState)
    
    g.add_node("planner", planner)
    g.add_node("sql_writer", sql_writer)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_node("critic", critic)
    g.add_node("summarizer", summarizer)


    g.add_edge(START, "planner")
    g.add_edge("planner", "sql_writer")
    g.add_conditional_edges("sql_writer", tools_condition, {"tools": "tools", END: "critic"})
    g.add_edge("tools", "sql_writer")
    g.add_conditional_edges("critic", after_critic, {"sql_writer": "sql_writer", "summarizer": "summarizer"})
    g.add_edge("summarizer", END)
    
    return g.compile(checkpointer=checkpointer)