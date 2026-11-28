"""python -m demo3_research_team.run "How should agents use checkpointing?" [--thread T] [--pause] [--resume]

--pause   stop right after the researcher (state is saved in SQLite)
--resume  continue the same --thread from where it stopped (works from a new process)
Run the same topic twice with different threads to see long-term memory reused.
"""
import argparse

from common.checkpoint import sqlite_saver
from common.llm import get_llm
from demo3_research_team.graph import build_graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", nargs="*")
    ap.add_argument("--thread", default="research-1")
    ap.add_argument("--pause", action="store_true")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    config = {"configurable": {"thread_id": args.thread}}

    with sqlite_saver() as saver:
        graph = build_graph(get_llm(), saver, interrupt_after=["researcher"] if args.pause else None)
        inp = None if args.resume else {"topic": " ".join(args.topic) or "Human-in-the-loop for agents"}
        for update in graph.stream(inp, config, stream_mode="updates"):
            for node, delta in update.items():
                print(f"[{node}] done" + (f" (review: {delta.get('feedback') or 'APPROVED'})" if node == "reviewer" else ""))
        state = graph.get_state(config)
        if state.next:
            print(f"\nPaused before {state.next}. Resume with:  --thread {args.thread} --resume")
        else:
            print(f"\n=== Report #{state.values['report_id']} ===\n{state.values['draft']}")


if __name__ == "__main__":
    main()
