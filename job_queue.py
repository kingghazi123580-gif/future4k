# ============================================================
# JOB QUEUE — SQLite-backed queue shared by ui.py (producer) and
# background_worker.py (consumer)
# Filename: job_queue.py
# ============================================================
# This is the missing piece background_worker.py already expects:
#   job_queue.claim_next_job(worker_id)
#   job_queue.update_progress(job_id, current, total, label)
#   job_queue.mark_done(job_id, result_path)
#   job_queue.mark_failed(job_id, error_message)
#
# Plus what ui.py needs to become a producer instead of doing the work
# itself:
#   job_queue.create_job(user_id, user_email, job_type, payload, eta_minutes)
#   job_queue.get_job(job_id)
#   job_queue.get_user_jobs(user_id)
#
# Any process (ui.py, background_worker.py) can open its own SQLite
# connection to the same file — SQLite handles the file locking, and
# claim_next_job() uses a single atomic UPDATE...WHERE status='queued'
# so two workers can never grab the same job.
# ============================================================

import os
import json
import time
import sqlite3

try:
    import config
    DB_PATH = getattr(config, "JOB_QUEUE_DB_PATH", os.path.join("data", "jobs.db"))
except ImportError:
    DB_PATH = os.path.join("data", "jobs.db")


def _get_conn():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            user_email TEXT,
            job_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            progress_current INTEGER NOT NULL DEFAULT 0,
            progress_total INTEGER NOT NULL DEFAULT 0,
            progress_label TEXT NOT NULL DEFAULT '',
            eta_minutes REAL,
            result_path TEXT,
            error_message TEXT,
            claimed_by TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            started_at REAL,
            finished_at REAL
        )
    """)
    conn.commit()
    return conn


def init_db():
    """Call once at app / worker startup (same pattern as the other feature modules)."""
    _get_conn().close()


def _row_to_dict(row) -> dict:
    (job_id, user_id, user_email, job_type, payload, status, prog_cur, prog_tot,
     prog_label, eta_minutes, result_path, error_message, claimed_by,
     created_at, updated_at, started_at, finished_at) = row
    return {
        "id": job_id,
        "user_id": user_id,
        "user_email": user_email,
        "job_type": job_type,
        "payload": payload,  # left as JSON string — caller decides whether to parse
        "status": status,
        "progress_current": prog_cur,
        "progress_total": prog_tot,
        "progress_label": prog_label,
        "eta_minutes": eta_minutes,
        "result_path": result_path,
        "error_message": error_message,
        "claimed_by": claimed_by,
        "created_at": created_at,
        "updated_at": updated_at,
        "started_at": started_at,
        "finished_at": finished_at,
    }


_COLUMNS = (
    "id, user_id, user_email, job_type, payload, status, progress_current, "
    "progress_total, progress_label, eta_minutes, result_path, error_message, "
    "claimed_by, created_at, updated_at, started_at, finished_at"
)


# ============================================================
# PRODUCER SIDE — called from ui.py
# ============================================================

def create_job(user_id: str, user_email: str, job_type: str, payload: dict,
                eta_minutes: float = None) -> int:
    """Queues a new job. Returns the new job's id. The worker picks it up
    on its next poll — nothing runs synchronously here."""
    now = time.time()
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO jobs (user_id, user_email, job_type, payload, status, "
        "eta_minutes, created_at, updated_at) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)",
        (user_id, user_email, job_type, json.dumps(payload), eta_minutes, now, now),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def get_job(job_id: int):
    conn = _get_conn()
    row = conn.execute(f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return _row_to_dict(row) if row else None


def get_user_jobs(user_id: str, limit: int = 20) -> list:
    """Most recent jobs first — powers the 'My Jobs' status page."""
    conn = _get_conn()
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def cancel_job(job_id: int) -> bool:
    """Only cancels a job that hasn't started processing yet (status still
    'queued'). A job already 'processing' can't be safely interrupted from
    here — the worker owns it at that point."""
    conn = _get_conn()
    cur = conn.execute(
        "UPDATE jobs SET status = 'cancelled', updated_at = ? WHERE id = ? AND status = 'queued'",
        (time.time(), job_id),
    )
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok


# ============================================================
# CONSUMER SIDE — called from background_worker.py
# ============================================================

def claim_next_job(worker_id: str):
    """Atomically grabs the oldest queued job and marks it 'processing'.
    Returns the job dict, or None if the queue is empty. Safe for
    multiple worker processes polling the same DB concurrently."""
    conn = _get_conn()
    row = conn.execute(
        "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if not row:
        conn.close()
        return None

    job_id = row[0]
    now = time.time()
    cur = conn.execute(
        "UPDATE jobs SET status = 'processing', claimed_by = ?, started_at = ?, "
        "updated_at = ? WHERE id = ? AND status = 'queued'",
        (worker_id, now, now, job_id),
    )
    conn.commit()
    if cur.rowcount == 0:
        # Another worker claimed it between our SELECT and UPDATE — normal race, just skip.
        conn.close()
        return None

    result_row = conn.execute(f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return _row_to_dict(result_row)


def update_progress(job_id: int, current: int, total: int, label: str = "") -> None:
    conn = _get_conn()
    conn.execute(
        "UPDATE jobs SET progress_current = ?, progress_total = ?, progress_label = ?, "
        "updated_at = ? WHERE id = ?",
        (current, total, label, time.time(), job_id),
    )
    conn.commit()
    conn.close()


def mark_done(job_id: int, result_path: str) -> None:
    now = time.time()
    conn = _get_conn()
    conn.execute(
        "UPDATE jobs SET status = 'done', result_path = ?, finished_at = ?, "
        "updated_at = ? WHERE id = ?",
        (result_path, now, now, job_id),
    )
    conn.commit()
    conn.close()


def mark_failed(job_id: int, error_message: str) -> None:
    now = time.time()
    conn = _get_conn()
    conn.execute(
        "UPDATE jobs SET status = 'failed', error_message = ?, finished_at = ?, "
        "updated_at = ? WHERE id = ?",
        (error_message, now, now, job_id),
    )
    conn.commit()
    conn.close()