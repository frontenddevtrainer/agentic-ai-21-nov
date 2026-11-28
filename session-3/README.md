# Agentic AI - Session 3: LangGraph + tools + SQLite + multi-agent

Five self-contained demos, each with its own SQLite database (no server to run). Each one teaches a different LangGraph idea.

| # | Demo | Agents | LangGraph ideas | SQLite is used for |
|---|------|--------|-----------------|----------------------|
| 1 | `demo1_text_to_sql` | planner, SQL writer, critic, summarizer | tool loop, self-correction, critic loop, layered tool safety | a sales warehouse, via a **read-only connection** |
| 2 | `demo2_support_desk` | triage + orders / billing / escalation specialists | routing, sub-graphs, `interrupt()` human approval, resume after restart | customers, orders, refunds, tickets + **checkpointer** |
| 3 | `demo3_research_team` | researcher, writer, reviewer | pipeline + review loop, long-term memory, pause/resume | notes (full-text search), reports + **checkpointer** |
| 4 | `demo4_pipeline_ops` | monitor, N parallel diagnosers, fixer, reporter | `Send` fan-out, reducers, guard-railed write tools, audit trail | jobs, logs, incidents, audit log |
| 5 | `demo5_procurement` | checker, forecaster, buyer (agent sub-graphs) + approver | private vs shared state, mixed code/LLM nodes, approval gate | products, demand history, purchase orders + **checkpointer** |

## Setup

```bash
cd langgraph-demos
cp .env.example .env            # add ANTHROPIC_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
That's it. The databases (`data/sales.db`, `support.db`, `research.db`, `ops.db`, `inventory.db`) are created and
seeded automatically on first use from `db/schema/*.sql` + `common/seed.py` (fixed random seed, so everyone gets the
same rows). Rebuild any of them with `python -m common.seed --reset [name]`. Graph checkpoints go in
`data/checkpoints.db`. Open any file with `sqlite3 data/support.db` or a viewer like DB Browser for SQLite.

Run any demo from this folder with `python -m <package>.run`.

## Demo scripts (what to show, what to say)

**1. Text-to-SQL** - `python -m demo1_text_to_sql.run "Which 3 countries generated the most revenue from paid orders?"`
Watch the writer list tables, describe them, hit an error, and fix itself. Then try
`"Delete all cancelled orders"`: the guard rejects it, and even if it didn't, the `analyst_ro` role is read-only
(the connection is opened `mode=ro` with `PRAGMA query_only` and a 5 s timeout, so a `DELETE` fails inside SQLite itself).
Three layers: validator, read-only connection, timeout.

**2. Support desk** - `python -m demo2_support_desk.run`
- *"Hi, I'm ben@example.com - my webcam never arrived, I want a refund."* -> triage routes to billing, which looks
  up the order and requests a 199.00 refund. The graph **pauses** and asks you to approve.
- Press Ctrl-C at the prompt, rerun with the same `--thread`: the pending approval is restored from the SQLite checkpoint file.
- *"Where is my order? asha@example.com"* -> orders agent. *"This is outrageous, I'm calling my lawyer"* -> escalation.
- Inspect: `sqlite3 data/support.db 'select * from refunds'` and `sqlite3 data/checkpoints.db 'select thread_id, checkpoint_id from checkpoints'`

**3. Research team** - `python -m demo3_research_team.run "How should agents use checkpointing?" --pause`
Stops after the researcher. Then `--thread research-1 --resume` (even in a new terminal) continues to writer/reviewer.
Run a second topic with a new `--thread` and watch `recall_notes` find the first run's notes
(`sqlite3 data/research.db 'select * from notes'`). Sources are a seeded corpus (`research.sources`) so the demo is offline and repeatable.

**4. Pipeline ops** - `python -m demo4_pipeline_ops.run --reset`
Three seeded failures: a transient timeout (retried), schema drift (incident), out-of-memory with attempts exhausted
(incident). Diagnosers run in parallel. Point out that `retry_job` itself refuses exhausted jobs - the rule lives in
the tool, not the prompt - and that every action is in `ops.audit_log`.

**5. Procurement** - `python -m demo5_procurement.run --reset`
Three suppliers get draft POs. Totals <= 5000 auto-approve; the Globex server-chassis order (12.8k) pauses for your
y/n. Show `purchase_orders` in `data/inventory.db` before and after.

## Tests (no API key needed)

`tests/` replaces the model with a scripted fake and runs the real graphs against real (throw-away) SQLite files,
including a pause-in-one-process / resume-in-another test with the actual `SqliteSaver`.

```bash
pytest -q
```
Tests use a temporary data directory and re-seed it before every test, so your `data/` files are never touched.

## Notes

- Model: `MODEL_NAME` in `.env` (default `claude-sonnet-5-5`). Everything goes through `common/llm.py`.
- Demo 3 uses SQLite FTS5 full-text search (BM25 ranking) over a seeded corpus rather than embeddings or live web
  search, so it is offline and repeatable. Swapping in embeddings is a good extension exercise.
- Connections are opened per query to keep the code readable. SQLite is a single-writer database: fine for a demo,
  use Postgres or similar for concurrent production traffic.
- The prompts and graphs were exercised end-to-end with the scripted model; behaviour with the real model
  (wording of verdicts, number of tool calls) may need prompt tweaks.
