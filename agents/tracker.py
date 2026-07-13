"""
agents/tracker.py

Manages the SQLite database for tracking all job applications.
Every other agent reads/writes through this module — it's the
single source of truth for application state.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH     = "applications.db"
SCHEMA_PATH = "db/schema.sql"


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # safer concurrent writes
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    schema = Path(SCHEMA_PATH).read_text()
    with get_connection() as conn:
        conn.executescript(schema)
    logger.info(f"Database initialised: {DB_PATH}")


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def upsert_job(job: dict, relevance_score: int = 0) -> int:
    """
    Insert a new job or update it if already tracked (matched on url).
    Returns the row id.
    """
    sql = """
        INSERT INTO applications (
            job_url, job_title, company, location,
            job_type, expires, relevance_score, status
        ) VALUES (
            :url, :title, :company, :location,
            :job_type, :expires, :score, 'pending'
        )
        ON CONFLICT(job_url) DO UPDATE SET
            relevance_score = excluded.relevance_score,
            updated_at      = CURRENT_TIMESTAMP
    """
    with get_connection() as conn:
        cursor = conn.execute(sql, {
            "url":      job.get("url", ""),
            "title":    job.get("title", ""),
            "company":  job.get("company", ""),
            "location": job.get("location", ""),
            "job_type": job.get("job_type", ""),
            "expires":  job.get("expires", ""),
            "score":    relevance_score,
        })
        return cursor.lastrowid


def update_status(job_url: str, status: str, **kwargs) -> bool:
    """
    Update the status of an application and any additional fields.

    Usage:
        update_status(url, "ready", cv_path="output/cvs/CV_...", cover_letter_path="...")
        update_status(url, "sent",  sent_at=datetime.now(), follow_up_at=..., email_subject="...")

    Returns True if a row was actually updated, False if job_url isn't tracked.
    """
    allowed_fields = {
        "cv_path", "cover_letter_path", "contact_email",
        "email_subject", "sent_at", "follow_up_at",
        "followed_up_at", "notes",
    }
    updates = {"status": status, "updated_at": datetime.now().isoformat()}
    for key, val in kwargs.items():
        if key in allowed_fields:
            updates[key] = val.isoformat() if isinstance(val, datetime) else val

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    sql = f"UPDATE applications SET {set_clause} WHERE job_url = :job_url"
    updates["job_url"] = job_url

    with get_connection() as conn:
        cursor = conn.execute(sql, updates)
        updated = cursor.rowcount > 0

    if updated:
        logger.info(f"Updated [{status}]: {job_url}")
    else:
        logger.warning(f"update_status: no tracked application for {job_url}")
    return updated


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_by_status(status: str) -> list[dict]:
    """Return all applications with the given status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM applications WHERE status = ? ORDER BY relevance_score DESC",
            (status,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_due_followups() -> list[dict]:
    """Return applications where follow_up_at has passed and no follow-up sent yet."""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM applications
            WHERE status = 'sent'
              AND follow_up_at IS NOT NULL
              AND follow_up_at <= ?
              AND followed_up_at IS NULL
            ORDER BY follow_up_at ASC
        """, (now,)).fetchall()
    return [dict(r) for r in rows]


def get_all() -> list[dict]:
    """Return all applications ordered by created_at descending."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM applications ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    """Return a summary count by status — used by the dashboard."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*) as count
            FROM applications
            GROUP BY status
        """).fetchall()
    stats = {row["status"]: row["count"] for row in rows}
    stats["total"] = sum(stats.values())
    return stats


def get_application(job_url: str) -> Optional[dict]:
    """Return a single application row (as a dict) by URL, or None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM applications WHERE job_url = ?", (job_url,)
        ).fetchone()
    return dict(row) if row else None


def already_tracked(job_url: str) -> bool:
    """Return True if this job URL is already in the database."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM applications WHERE job_url = ?", (job_url,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Quick test — python agents/tracker.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()

    # Insert test jobs
    test_jobs = [
        {
            "url":      "https://vacancymail.co.zw/jobs/software-developer-test/",
            "title":    "Software Developer",
            "company":  "TechCorp Zimbabwe",
            "location": "Harare",
            "job_type": "Full Time",
            "expires":  "30 Jun 2026",
        },
        {
            "url":      "https://vacancymail.co.zw/jobs/it-support-test/",
            "title":    "IT Support Specialist",
            "company":  "Vacancy Mail",
            "location": "Harare",
            "job_type": "Full Time",
            "expires":  "28 Jun 2026",
        },
    ]

    for job in test_jobs:
        upsert_job(job, relevance_score=75)
        print(f"Inserted: {job['title']} @ {job['company']}")

    # Simulate updating one to 'sent'
    sent_at     = datetime.now()
    follow_up_at = sent_at + timedelta(days=7)
    update_status(
        test_jobs[0]["url"],
        "sent",
        sent_at=sent_at,
        follow_up_at=follow_up_at,
        email_subject="Application for Software Developer — Jane Doe",
        contact_email="hr@techcorp.co.zw",
    )

    print("\n--- All applications ---")
    for app in get_all():
        print(f"  [{app['status']:12}] {app['job_title']} @ {app['company']} (score: {app['relevance_score']})")

    print(f"\n--- Stats ---")
    for status, count in get_stats().items():
        print(f"  {status}: {count}")

    print(f"\n--- Due follow-ups ---")
    followups = get_due_followups()
    print(f"  {len(followups)} due now")