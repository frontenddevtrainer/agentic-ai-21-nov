"""Reusable building blocks."""
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition


def react_subgraph(llm, tools, system_prompt: str):
    """A tool-calling agent as a compiled graph:  agent -> (tools -> agent)* -> end.

    It is a graph itself, so it can be dropped into a parent graph as a node
    (shared `messages` state) or invoked from a function node (private state).
    """
    model = llm.bind_tools(tools)

    def agent(state: MessagesState):
        return {"messages": [model.invoke([SystemMessage(content=system_prompt)] + state["messages"])]}

    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile()


def text_of(message) -> str:
    """Plain text of a message whether content is a str or a list of blocks."""
    c = message.content
    if isinstance(c, str):
        return c
    return "".join(b.get("text", "") for b in c if isinstance(b, dict))
