"""
main.py — Job Application Autopilot Orchestrator

Runs the full pipeline end-to-end:

  1. Scrape vacancymail.co.zw for new ICT job listings
  2. Filter out already-tracked jobs
  3. Score each listing against the candidate's CV (heuristic or LLM)
  4. For jobs scoring >= APPLY_THRESHOLD:
       a. Parse CV (from cache or fresh)
       b. Tailor CV to job
       c. Generate cover letter
       d. Send application email
       e. Log everything to SQLite
  5. Send follow-up emails for any due applications

Usage:
  python main.py --cv path/to/cv.docx       # full pipeline, dry run (safe default)
  python main.py --cv path/to/cv.docx --send # actually send emails
  python main.py --followups-only            # only run follow-up check
  python main.py --scrape-only               # only scrape and score, no documents
"""

import argparse
import logging
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

from agents.sample_profile import SAMPLE_CV_PROFILE

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("orchestrator")

# ── Config ──────────────────────────────────────────────────────────────────

CV_PATH          = ""    # Set via --cv flag or upload via dashboard
APPLY_THRESHOLD  = 70    # minimum score to auto-apply
REVIEW_THRESHOLD = 50    # scores 50-69 logged but not auto-applied

SCRAPE_CATEGORIES = ["ict"]
SCRAPE_MAX_PAGES  = 3
FETCH_DETAILS     = True  # fetch full job descriptions (slower but better scoring)

OUTPUT_DIR_CVS    = "output/cvs"
OUTPUT_DIR_COVERS = "output/cover_letters"

# Path written by the dashboard when a CV is uploaded
CV_POINTER = Path("active_cv.txt")


# ── Pipeline steps ──────────────────────────────────────────────────────────

def step_scrape() -> list[dict]:
    """Step 1 — Scrape fresh job listings from vacancymail, skipping detail
    fetches for jobs we've already tracked (major speed improvement)."""
    from scrapers.vacancymail import scrape
    from agents.tracker import get_all
    from agents.status import write_status

    logger.info("── Step 1: Scraping vacancymail.co.zw ──")
    write_status("scraping", "Scraping vacancymail.co.zw for new listings...", 20)

    tracked_urls = {app["job_url"] for app in get_all()}

    jobs = scrape(
        categories=SCRAPE_CATEGORIES,
        max_pages=SCRAPE_MAX_PAGES,
        fetch_details=FETCH_DETAILS,
        skip_urls=tracked_urls,
    )
    logger.info(f"Scraped {len(jobs)} listings")
    return [j.to_dict() for j in jobs]


def step_filter_new(jobs: list[dict]) -> list[dict]:
    """Step 2 — Remove jobs already in the database."""
    from agents.tracker import already_tracked
    from agents.status import write_status
    write_status("filtering", "Filtering out already-tracked jobs...", 35)
    new_jobs = [j for j in jobs if not already_tracked(j["url"])]
    logger.info(f"── Step 2: {len(new_jobs)} new jobs (filtered {len(jobs) - len(new_jobs)} already tracked)")
    return new_jobs


def step_score(jobs: list[dict], cv_profile: dict) -> list[tuple[dict, object]]:
    """Step 3 — Score each job and split into apply/review/skip."""
    from agents.relevance_filter import filter_jobs
    from agents.tracker import upsert_job
    from agents.status import write_status

    logger.info("── Step 3: Scoring jobs ──")
    write_status("scoring", f"Scoring {len(jobs)} jobs against your CV...", 50)
    results = filter_jobs(jobs, cv_profile)

    apply_list  = []
    review_list = []

    for result in results:
        job = next(j for j in jobs if j["url"] == result.job_url)
        upsert_job(job, relevance_score=result.score)

        if result.decision == "APPLY":
            apply_list.append((job, result))
        elif result.decision == "REVIEW":
            review_list.append((job, result))
            logger.info(f"  [REVIEW] {result.score}/100 — {result.job_title} @ {result.company}")

    logger.info(
        f"Scoring complete: {len(apply_list)} APPLY, "
        f"{len(review_list)} REVIEW, "
        f"{len(results) - len(apply_list) - len(review_list)} SKIP"
    )
    return apply_list


def step_apply(apply_list: list[tuple], cv_profile: dict, auto_send: bool = False):
    """Step 4 — Generate tailored documents and stage each application for a
    human approval checkpoint. Nothing is emailed automatically unless
    auto_send=True (the --send flag)."""
    from agents.cv_tailor import tailor_cv
    from agents.cover_letter import generate_cover_letter
    from agents.submission import send_application
    from agents.tracker import update_status
    from agents.status import write_status

    logger.info(f"── Step 4: Preparing {len(apply_list)} applications (auto_send={auto_send}) ──")
    total = len(apply_list) or 1

    for i, (job, result) in enumerate(apply_list, 1):
        logger.info(f"Processing: {job['title']} @ {job['company']} ({result.score}/100)")
        progress = 60 + int((i - 1) / total * 30)
        write_status(
            "applying",
            f"Tailoring documents for {job['title']} @ {job['company']} ({i}/{total})",
            progress,
        )

        update_status(job["url"], "tailoring")

        # Generate real documents so a human can review them before sending.
        cv_out = tailor_cv(cv_profile, job, output_dir=OUTPUT_DIR_CVS, dry_run=False)
        cl_out = generate_cover_letter(cv_profile, job, output_dir=OUTPUT_DIR_COVERS, dry_run=False)

        contact_email = job.get("contact_email") or ""
        name    = cv_profile.get("name", "Applicant")
        subject = f"Application for {job['title']} — {name}"

        # Human-in-the-loop checkpoint: stage for approval, never auto-send by default.
        if not contact_email:
            logger.warning(f"No contact email for {job['title']} — needs manual handling")
            update_status(
                job["url"], "awaiting_approval",
                cv_path=cv_out, cover_letter_path=cl_out, email_subject=subject,
                notes="No contact email found — add one before sending",
            )
            continue

        update_status(
            job["url"], "awaiting_approval",
            cv_path=cv_out, cover_letter_path=cl_out,
            contact_email=contact_email, email_subject=subject,
        )
        logger.info(f"  ⏸ Awaiting approval: {job['title']} @ {job['company']} → {contact_email}")

        if auto_send:
            sent = send_application(
                cv_profile=cv_profile, job=job,
                cv_path=cv_out, cover_letter_path=cl_out,
                contact_email=contact_email, subject=subject, dry_run=False,
            )
            if sent:
                sent_at      = datetime.now()
                follow_up_at = sent_at + timedelta(days=7)
                update_status(
                    job["url"], "sent",
                    sent_at=sent_at, follow_up_at=follow_up_at,
                    contact_email=contact_email, email_subject=subject,
                )
                logger.info(f"  ✓ Auto-sent: {job['title']} @ {job['company']}")
            else:
                update_status(job["url"], "awaiting_approval",
                              notes="Auto-send failed — approve manually from the dashboard")


def step_followups(dry_run: bool = True):
    """Step 5 — Send follow-up emails for due applications."""
    from agents.followup import run_followups
    from agents.status import write_status
    logger.info("── Step 5: Checking follow-ups ──")
    write_status("followups", "Checking for due follow-ups...", 92)
    count = run_followups(dry_run=dry_run)
    logger.info(f"Follow-ups processed: {count}")


# ── Entry point ─────────────────────────────────────────────────────────────

def main():
    from agents.status import write_status

    parser = argparse.ArgumentParser(description="Job Application Autopilot")
    parser.add_argument("--cv",             type=str,            help="Path to CV file (.docx or .pdf)")
    parser.add_argument("--send",           action="store_true", help="Auto-approve and send (default: stage for human approval in the dashboard)")
    parser.add_argument("--followups-only", action="store_true", help="Only run follow-up check")
    parser.add_argument("--scrape-only",    action="store_true", help="Only scrape and score, no documents")
    args = parser.parse_args()

    dry_run = not args.send

    try:
        # Init database
        from agents.tracker import init_db
        init_db()

        if dry_run:
            logger.info("🔒 DRY RUN MODE — no emails will be sent (use --send to go live)")

        # Follow-ups only — no CV needed
        if args.followups_only:
            write_status("followups", "Checking for due follow-ups...", 10)
            step_followups(dry_run=dry_run)
            write_status("done", "Follow-up check complete.", 100)
            return

        # Resolve CV path: --cv flag > active_cv.txt (set by dashboard) > CV_PATH constant
        cv_path = args.cv
        if not cv_path and CV_POINTER.exists():
            cv_path = CV_POINTER.read_text().strip()
        if not cv_path:
            cv_path = CV_PATH

        if not cv_path or not Path(cv_path).exists():
            msg = "No CV file found. Upload one via the dashboard or pass --cv path/to/cv.docx"
            logger.error(msg)
            write_status("error", msg, 0)
            sys.exit(1)

        logger.info(f"── Loading CV: {cv_path} ──")
        write_status("loading_cv", "Reading and parsing your CV...", 5)
        from agents.cv_parser import parse_cv

        if os.getenv("QWEN_API_KEY"):
            cv_profile = parse_cv(cv_path, use_llm=True)
        else:
            logger.warning("QWEN_API_KEY not set — using hardcoded CV profile")
            cv_profile = _hardcoded_cv_profile()

        # Scrape
        jobs = step_scrape()
        if not jobs:
            write_status("done", "No jobs scraped this run.", 100)
            logger.info("No jobs scraped — exiting")
            return

        # Filter already-tracked
        new_jobs = step_filter_new(jobs)
        if not new_jobs:
            write_status("done", "No new jobs found this run.", 100)
            logger.info("No new jobs found — exiting")
            return

        # Score
        apply_list = step_score(new_jobs, cv_profile)

        if args.scrape_only:
            write_status("done", "Scrape and score complete.", 100)
            logger.info("--scrape-only flag set — stopping before document generation")
            return

        # Apply — generate documents and stage for human approval
        if apply_list:
            step_apply(apply_list, cv_profile, auto_send=args.send)
        else:
            logger.info("No jobs met the apply threshold this run")

        # Follow-ups
        step_followups(dry_run=dry_run)

        write_status("done", f"Pipeline complete — {len(apply_list)} application(s) ready for your review.", 100)
        logger.info("── Pipeline complete ──")

    except Exception as e:
        logger.exception("Pipeline failed")
        write_status("error", f"Pipeline failed: {e}", 0)
        raise


def _hardcoded_cv_profile() -> dict:
    """Fallback CV profile used when QWEN_API_KEY is not set."""
    return dict(SAMPLE_CV_PROFILE)


if __name__ == "__main__":
    main()