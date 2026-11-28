"""python -m demo5_procurement.run [--thread T] [--reset]

Runs the restock workflow. Small POs auto-approve; big ones pause and ask you.
--reset rebuilds the inventory database (clears earlier purchase orders).
"""
import argparse

from langgraph.types import Command

from common.checkpoint import sqlite_saver
from common.seed import build
from common.llm import get_llm
from demo5_procurement.graph import build_graph


def pending(graph, config):
    for t in graph.get_state(config).tasks:
        for i in t.interrupts:
            return i.value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thread", default="procure-1")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    if args.reset:
        build("inventory")
    config = {"configurable": {"thread_id": args.thread}}
    with sqlite_saver() as saver:
        graph = build_graph(get_llm(), saver)
        inp = None if pending(graph, config) else {}
        while True:
            if inp is not None:
                graph.invoke(inp, config)
            ask = pending(graph, config)
            if not ask:
                break
            decisions = {}
            for p in ask["needs_approval"]:
                a = input(f"PO #{p['id']} to {p['supplier']} totals {p['total']:.2f} (limit {ask['limit']:.0f}). Approve? [y/N] ")
                decisions[str(p["id"])] = a.strip().lower() == "y"
            inp = Command(resume=decisions)
        print("\n" + graph.get_state(config).values["summary"])


if __name__ == "__main__":
    main()
