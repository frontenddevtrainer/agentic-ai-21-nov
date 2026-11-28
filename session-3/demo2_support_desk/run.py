"""Interactive support chat.  python -m demo2_support_desk.run [--thread NAME]

Try:  "Hi, I'm ben@example.com - my webcam never arrived and I want my money back."
When a refund needs approval you'll be asked y/n. Kill the process at that prompt,
start again with the same --thread, and the pending approval is still there.
"""
import argparse

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from common.checkpoint import sqlite_saver
from common.agents import text_of
from common.llm import get_llm
from demo2_support_desk.graph import build_graph


def pending_interrupt(graph, config):
    for task in graph.get_state(config).tasks:
        for it in task.interrupts:
            return it.value
    return None


def drive(graph, config, inp):
    """Run until the graph finishes or pauses; loop on approval prompts."""
    while True:
        if inp is not None:
            graph.invoke(inp, config)
        ask = pending_interrupt(graph, config)
        if not ask:
            return
        print(f"\n[APPROVAL NEEDED] refund {ask['amount']:.2f} on order {ask['order_id']} - {ask['reason']}")
        ok = input("Approve? [y/N] ").strip().lower() == "y"
        inp = Command(resume={"approved": ok, "by": "human-reviewer"})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", default="support-1")
    args = ap.parse_args()
    config = {"configurable": {"thread_id": args.thread}}
    with sqlite_saver() as saver:
        graph = build_graph(get_llm(), saver)
        if pending_interrupt(graph, config):  # resumed after a restart
            print("(found a paused refund approval from an earlier run)")
            drive(graph, config, None)
            print("\nAgent:", text_of(graph.get_state(config).values["messages"][-1]))
        while True:
            try:
                user = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user:
                continue
            drive(graph, config, {"messages": [HumanMessage(content=user)]})
            print("\nAgent:", text_of(graph.get_state(config).values["messages"][-1]))


if __name__ == "__main__":
    main()
