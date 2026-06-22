"""
agents/submission.py

Sends job application emails via the Gmail API using OAuth2.
Attaches the tailored CV and cover letter .docx files.

First run: opens a browser for OAuth consent and saves token.json.
Subsequent runs: uses the saved token silently.

Modes:
  dry_run=True  — prints email details, no Gmail API call
  dry_run=False — sends real email via Gmail API
"""

import os
import base64
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE       = "token.json"
SENDER_NAME      = "Dube Calvin"
SENDER_EMAIL     = "REDACTED@example.com"

# Gmail API scopes needed
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


# ---------------------------------------------------------------------------
# Gmail auth
# ---------------------------------------------------------------------------

def _get_gmail_service():
    """
    Authenticate with Gmail API using OAuth2.
    Opens browser on first run to get user consent.
    Saves token.json for subsequent silent runs.
    """
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        raise ImportError(
            "Google API packages not installed. Run:\n"
            "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )

    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not Path(CREDENTIALS_FILE).exists():
                raise FileNotFoundError(
                    f"{CREDENTIALS_FILE} not found. "
                    "Download it from Google Cloud Console → APIs & Services → Credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
        logger.info("Gmail token saved to token.json")

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------

def _build_email(
    to: str,
    subject: str,
    body: str,
    cv_path: Optional[str] = None,
    cover_letter_path: Optional[str] = None,
) -> str:
    """
    Build a MIME email with optional .docx attachments.
    Returns base64url-encoded string ready for Gmail API.
    """
    msg = MIMEMultipart()
    msg["From"]    = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"]      = to
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))

    # Attach files
    for file_path in [cover_letter_path, cv_path]:
        if not file_path:
            continue
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"Attachment not found, skipping: {file_path}")
            continue

        with open(path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={path.name}",
        )
        msg.attach(part)
        logger.info(f"Attached: {path.name}")

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return raw


def _build_email_body(cv_profile: dict, job: dict) -> str:
    """
    Build a short, professional plain-text email body.
    The cover letter does the heavy lifting — this is just the email wrapper.
    """
    name  = cv_profile.get("name", "Dube Calvin")
    title = job.get("title", "the advertised position")
    company = job.get("company", "your organisation")

    return f"""Dear Hiring Manager,

Please find attached my application for the {title} position at {company}.

I have included my tailored CV and cover letter for your consideration.

I look forward to hearing from you.

Yours sincerely,
{name}
{cv_profile.get('phone', '')}
{cv_profile.get('email', '')}
""".strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def send_application(
    cv_profile: dict,
    job: dict,
    cv_path: str,
    cover_letter_path: str,
    contact_email: str,
    subject: str,
    dry_run: bool = True,
) -> bool:
    """
    Send a job application email with CV and cover letter attached.

    Args:
        cv_profile:         Candidate profile dict
        job:                Job listing dict
        cv_path:            Path to tailored CV .docx
        cover_letter_path:  Path to cover letter .docx
        contact_email:      Recipient email address
        subject:            Email subject line
        dry_run:            If True, print details only — don't send

    Returns:
        True if sent successfully, False otherwise.
    """
    body = _build_email_body(cv_profile, job)

    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN — SUBMISSION AGENT")
        print("=" * 60)
        print(f"To:          {contact_email}")
        print(f"Subject:     {subject}")
        print(f"CV:          {cv_path or 'NOT SET'}")
        print(f"Cover Letter:{cover_letter_path or 'NOT SET'}")
        print(f"\n--- EMAIL BODY ---")
        print(body)
        print("\n[No email sent — set dry_run=False to send for real]")
        return False

    try:
        service = _get_gmail_service()
        raw = _build_email(
            to=contact_email,
            subject=subject,
            body=body,
            cv_path=cv_path,
            cover_letter_path=cover_letter_path,
        )
        service.users().messages().send(
            userId="me",
            body={"raw": raw}
        ).execute()
        logger.info(f"Email sent to {contact_email} — {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


# ---------------------------------------------------------------------------
# Quick test — python agents/submission.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cv_profile = {
        "name":  "Dube Calvin",
        "email": "REDACTED@example.com",
        "phone": "+263 00 000 0000",
    }

    job = {
        "title":    "Regulatory Technology Systems Developers x3",
        "company":  "Securities and Exchange Commission of Zimbabwe",
        "location": "Harare",
        "job_type": "Full Time",
        "url":      "https://vacancymail.co.zw/jobs/regulatory-technology-67719/",
    }

    # Always dry_run=True until you're ready to send real emails
    send_application(
        cv_profile=cv_profile,
        job=job,
        cv_path="output/cvs/CV_example.docx",
        cover_letter_path="output/cover_letters/CoverLetter_example.docx",
        contact_email="REDACTED@example.com",  # send to yourself for testing
        subject="Application for Regulatory Technology Systems Developers — Dube Calvin",
        dry_run=False,
    )