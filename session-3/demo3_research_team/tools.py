import re

from langchain_core.tools import tool

from common.db import as_json, fetch


def _fts_query(text: str) -> str:
    """'checkpointing in agents' -> '"checkpointing" OR "agents"' (FTS5 syntax)."""
    words = [w for w in re.findall(r"[A-Za-z0-9]+", text.lower()) if len(w) > 2]
    return " OR ".join(f'"{w}"' for w in words) or '"agent"'


@tool
def search_sources(query: str) -> str:
    """Search the research corpus (SQLite FTS5 full-text, best match first). Returns the best 3
    sources with id, title, url and body."""
    rows = fetch(
        "SELECT s.id, s.title, s.url, s.body FROM research.sources_fts "
        "JOIN research.sources s ON s.id = sources_fts.rowid "
        "WHERE sources_fts MATCH ? ORDER BY bm25(sources_fts) LIMIT 3",
        (_fts_query(query),),
    )
    return as_json(rows) if rows else "No sources found. Try different keywords."


@tool
def recall_notes(topic: str) -> str:
    """Long-term memory: notes saved by earlier research runs that match this topic."""
    rows = fetch(
        "SELECT n.id, n.topic, n.content, n.source_id, n.created_at FROM research.notes_fts "
        "JOIN research.notes n ON n.id = notes_fts.rowid "
        "WHERE notes_fts MATCH ? ORDER BY bm25(notes_fts) LIMIT 8",
        (_fts_query(topic),),
    )
    return as_json(rows) if rows else "No earlier notes on this topic."


@tool
def save_note(topic: str, content: str, source_id: int | None = None) -> str:
    """Save one concise finding (a sentence or two) to long-term memory, citing source_id."""
    row = fetch(
        "INSERT INTO research.notes (topic, content, source_id) VALUES (?,?,?) RETURNING id",
        (topic, content, source_id),
    )[0]
    return f"Saved note {row['id']}."


RESEARCH_TOOLS = [recall_notes, search_sources, save_note]
