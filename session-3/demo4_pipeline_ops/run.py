"""python -m demo4_pipeline_ops.run  [--reset]   (--reset restores the seeded failures first)"""
import sys

from common.db import fetch
from common.seed import build
from common.llm import get_llm
from demo4_pipeline_ops.graph import build_graph


def main():
    if "--reset" in sys.argv:
        build("ops")
        print("(reset seeded failures)\n")
    graph = build_graph(get_llm())
    final = {}
    for mode, chunk in graph.stream({"diagnoses": []}, stream_mode=["updates", "values"]):
        if mode == "values":
            final = chunk
        else:
            for node, delta in chunk.items():
                print(f"[{node}]", (delta or {}).get("diagnoses") or (delta or {}).get("actions") or "")
    print("\n=== Handoff note ===\n" + final["report"])
    print("\n=== Audit trail ===")
    for r in fetch("SELECT time(ts) AS t, actor, action, detail FROM ops.audit_log ORDER BY id"):
        print(r["t"], r["actor"], r["action"], r["detail"])


if __name__ == "__main__":
    main()
