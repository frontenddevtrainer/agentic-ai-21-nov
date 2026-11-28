"""Demo 2 - Customer support desk.

    triage --> orders_agent ----\
           --> billing_agent ----+--> END
           --> escalation_agent -/

Each specialist is its own compiled sub-graph (agent <-> tools) with a small tool
set. `issue_refund` calls interrupt(), so refunds wait for a human decision, and
the SQLite checkpointer lets that wait survive a process restart.
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from typing_extensions import NotRequired

from common.agents import react_subgraph, text_of
from demo2_support_desk.tools import BILLING_TOOLS, ESCALATION_TOOLS, ORDER_TOOLS


class State(MessagesState):
    route: NotRequired[str]


TRIAGE = (
    "You are a support triage agent. Read the customer's latest message and reply with exactly one "
    "word: ORDERS (order status, tracking, delivery questions), BILLING (refunds, charges, payments), "
    "or ESCALATE (angry customer, legal threats, safety issues, or anything else)."
)
ORDERS = (
    "You are the orders specialist for an online store. Look customers up by email, then answer "
    "using real data from the tools. If an order is lost or badly late, open a ticket (category "
    "'orders'). If you need an email or order id, ask for it. Be concise and friendly."
)
BILLING = (
    "You are the billing specialist. Verify the customer and order with tools first. Only request a "
    "refund for a 'lost' order or one the customer clearly has grounds on, never more than the order "
    "total. issue_refund pauses for human approval - after it returns, tell the customer exactly what "
    "happened. Be concise."
)
ESCALATION = (
    "You handle escalations. Apologise sincerely, open a HIGH priority ticket (category 'other') "
    "summarising the problem, and tell the customer a senior agent will contact them. Ask for their "
    "email first if you don't have it."
)


def build_graph(llm, checkpointer=None):
    def triage(state: State):
        msg = llm.invoke([SystemMessage(content=TRIAGE)] + state["messages"][-6:])
        word = text_of(msg).strip().upper()
        route = "billing" if "BILLING" in word else "orders" if "ORDERS" in word else "escalation"
        return {"route": route}

    g = StateGraph(State)
    g.add_node("triage", triage)
    # Sub-graphs share the parent's `messages` key, so they continue the same conversation.
    g.add_node("orders", react_subgraph(llm, ORDER_TOOLS, ORDERS))
    g.add_node("billing", react_subgraph(llm, BILLING_TOOLS, BILLING))
    g.add_node("escalation", react_subgraph(llm, ESCALATION_TOOLS, ESCALATION))
    g.add_edge(START, "triage")
    g.add_conditional_edges("triage", lambda s: s["route"], ["orders", "billing", "escalation"])
    for n in ("orders", "billing", "escalation"):
        g.add_edge(n, END)
    return g.compile(checkpointer=checkpointer)
