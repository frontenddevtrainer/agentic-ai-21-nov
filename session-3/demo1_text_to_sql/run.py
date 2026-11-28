"""python -m demo1_text_to_sql.run "Top 5 countries by revenue" """
import sys

from common.llm import get_llm
from demo1_text_to_sql.graph import build_graph


def main():
    question = " ".join(sys.argv[1:]) or "Which 3 countries generated the most revenue from paid orders?"
    graph = build_graph(get_llm())
    print(f"Q: {question}\n")
    for update in graph.stream({"question": question}, stream_mode="updates"):
        for node, delta in update.items():
            if node == "tools":
                for m in delta["messages"]:
                    print(f"  [tool result] {str(m.content)[:160]}")
            elif node == "sql_writer":
                m = delta["messages"][-1]
                for c in getattr(m, "tool_calls", []):
                    print(f"  [sql_writer -> {c['name']}] {c['args']}")
            elif node == "critic":
                print(f"  [critic] {delta['critique']}")
            elif node == "planner":
                print(f"  [planner]\n{delta['plan']}")
            elif node == "summarizer":
                print(f"\nA: {delta['answer']}")


if __name__ == "__main__":
    main()
