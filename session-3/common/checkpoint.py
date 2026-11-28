"""SQLite-backed LangGraph checkpointer.

Every super-step of a graph is saved to data/checkpoints.db keyed by thread_id, which gives
you: resumable runs, human-in-the-loop pauses that survive a restart, and replay.
"""
from contextlib import contextmanager

from langgraph.checkpoint.sqlite import SqliteSaver

from common.db import checkpoint_path


@contextmanager
def sqlite_saver():
    with SqliteSaver.from_conn_string(str(checkpoint_path())) as saver:
        yield saver
