from langchain_core.tools import tool

from common.db import as_json, fetch


def audit(actor: str, action: str, detail: dict) -> None:
    import json

    fetch("INSERT INTO ops.audit_log (actor, action, detail) VALUES (?,?,?)",
          (actor, action, json.dumps(detail, default=str)))


def failed_jobs() -> list[dict]:
    return fetch("SELECT id, name, attempts, max_attempts FROM ops.jobs WHERE status='failed' ORDER BY id")


@tool
def check_job_status(job_id: int) -> str:
    """Current status, attempt count and attempt limit of a job."""
    rows = fetch("SELECT id, name, status, attempts, max_attempts, last_run FROM ops.jobs WHERE id=?", (job_id,))
    return as_json(rows[0]) if rows else "No such job."


@tool
def read_logs(job_id: int, limit: int = 15) -> str:
    """Most recent log lines for a job (oldest first)."""
    rows = fetch(
        "SELECT ts, level, message FROM (SELECT id, ts, level, message FROM ops.job_logs WHERE job_id=? "
        "ORDER BY id DESC LIMIT ?) ORDER BY id",
        (job_id, limit),
    )
    audit("diagnoser", "read_logs", {"job_id": job_id})
    return as_json(rows) if rows else "No logs."


@tool
def retry_job(job_id: int) -> str:
    """Re-run a FAILED job. Refused when the job has used all its attempts."""
    rows = fetch("SELECT status, attempts, max_attempts, will_succeed_on_retry FROM ops.jobs WHERE id=?", (job_id,))
    if not rows:
        return "No such job."
    j = rows[0]
    if j["status"] != "failed":
        return f"Refused: job is '{j['status']}', only failed jobs can be retried."
    if j["attempts"] >= j["max_attempts"]:
        audit("fixer", "retry_refused", {"job_id": job_id, "reason": "attempts exhausted"})
        return "Refused: attempts exhausted. Escalate with write_incident instead."
    outcome = "succeeded" if j["will_succeed_on_retry"] else "failed"
    fetch("UPDATE ops.jobs SET status=?, attempts=attempts+1, last_run=CURRENT_TIMESTAMP WHERE id=?", (outcome, job_id))
    fetch("INSERT INTO ops.job_logs (job_id, level, message) VALUES (?,'INFO',?)",
          (job_id, f"Retry triggered by ops agent: {outcome}"))
    audit("fixer", "retry_job", {"job_id": job_id, "outcome": outcome})
    return f"Retried job {job_id}: now '{outcome}'."


@tool
def write_incident(job_id: int, severity: str, summary: str) -> str:
    """Open an incident for humans. severity: low|medium|high."""
    row = fetch("INSERT INTO ops.incidents (job_id, severity, summary) VALUES (?,?,?) RETURNING id",
                (job_id, severity, summary))[0]
    audit("fixer", "write_incident", {"job_id": job_id, "incident_id": row["id"], "severity": severity})
    return f"Incident #{row['id']} opened for job {job_id}."


DIAGNOSE_TOOLS = [check_job_status, read_logs]
FIX_TOOLS = [retry_job, write_incident]
