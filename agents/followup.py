"""
agents/followup.py

Checks the database for applications where:
  - status = 'sent'
  - follow_up_at <= now
  - followed_up_at IS NULL

And sends a polite follow-up email for each one via Gmail.

Designed to be called by the orchestrator on a schedule (e.g. daily).
"""

import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SENDER_NAME  = "Dube Calvin"
SENDER_EMAIL = "calvindube.cd@gmail.com"


def _build_followup_body(app: dict) -> str:
    """Build a short, polite follow-up email body."""
    return f"""Dear Hiring Manager,

I hope this message finds you well. I am writing to follow up on my application for the {app['job_title']} position at {app['company']}, submitted on {app['sent_at'][:10] if app.get('sent_at') else 'recently'}.

I remain very interested in this opportunity and would welcome the chance to discuss how my skills and experience align with your requirements.

Please let me know if you need any additional information from me. I look forward to hearing from you.

Yours sincerely,
{SENDER_NAME}
{SENDER_EMAIL}
+263 782 821 968
""".strip()


def run_followups(dry_run: bool = True) -> int:
    """
    Send follow-up emails for all due applications.

    Args:
        dry_run: If True, print details only — no emails sent

    Returns:
        Number of follow-ups sent (or would have been sent in dry_run)
    """
    from agents.tracker import get_due_followups, update_status
    from agents.submission import _get_gmail_service, _build_email
    import base64

    due = get_due_followups()
    logger.info(f"Found {len(due)} application(s) due for follow-up")

    if not due:
        return 0

    count = 0
    service = None if dry_run else _get_gmail_service()

    for app in due:
        body    = _build_followup_body(app)
        fallback_subject = f"Application for {app['job_title']}"
        subject = f"Follow-up: {app['email_subject'] or fallback_subject}"
        to      = app.get("contact_email", "")

        if not to:
            logger.warning(f"No contact email for {app['job_title']} @ {app['company']} — skipping")
            continue

        if dry_run:
            print(f"\n{'='*55}")
            print(f"DRY RUN — FOLLOW-UP")
            print(f"To:      {to}")
            print(f"Subject: {subject}")
            print(f"Body:\n{body}")
            count += 1
            continue

        try:
            raw = _build_email(to=to, subject=subject, body=body)
            service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()

            update_status(
                app["job_url"],
                "followed_up",
                followed_up_at=datetime.now(),
            )
            logger.info(f"Follow-up sent: {app['job_title']} @ {app['company']}")
            count += 1

        except Exception as e:
            logger.error(f"Failed to send follow-up for {app['job_title']}: {e}")

    return count


if __name__ == "__main__":
    from agents.tracker import init_db
    init_db()
    sent = run_followups(dry_run=True)
    print(f"\nFollow-ups processed: {sent}")