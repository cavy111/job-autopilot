"""
agents/job_intake.py

Turn a user-supplied job — either a URL or a pasted job description — into a
normalized job dict (same schema as the scraper's JobListing) so it can flow
through the exact same pipeline: score -> tailor -> cover letter -> approve ->
submit -> track.

Uses Qwen Cloud function-calling to extract structured fields from arbitrary,
messy input (a Track 4 "handle ambiguous inputs" cue). Degrades gracefully to a
lightweight heuristic if no QWEN_API_KEY is set or the LLM call fails.
"""

import os
import re
import hashlib
import logging

from dotenv import load_dotenv
load_dotenv()

try:
    from agents.llm_utils import call_llm_tool
except ImportError:  # allow running standalone from agents/
    from llm_utils import call_llm_tool

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en;q=0.9",
}

JOB_INTAKE_TOOL = {
    "name": "record_job_posting",
    "description": "Record the structured fields of a job posting extracted from text.",
    "parameters": {
        "type": "object",
        "properties": {
            "title":         {"type": "string", "description": "Job title / role."},
            "company":       {"type": "string", "description": "Hiring organisation."},
            "location":      {"type": "string"},
            "job_type":      {"type": "string", "description": "e.g. Full Time, Contract, Internship."},
            "description":   {"type": "string", "description": "Concise summary of the role and requirements."},
            "contact_email": {"type": "string", "description": "Application/contact email if present, else empty."},
            "how_to_apply":  {"type": "string", "description": "Application instructions if present."},
        },
        "required": ["title"],
    },
}


def _is_url(text: str) -> bool:
    t = text.strip()
    return t.lower().startswith(("http://", "https://")) and " " not in t and "\n" not in t


def job_key(raw_input: str) -> str:
    """Deterministic tracker key for a user-supplied job, WITHOUT any network or
    LLM call — a real URL as-is, or manual://<sha1> for pasted text. Lets callers
    dedupe/debounce before running the pipeline."""
    raw_input = (raw_input or "").strip()
    if _is_url(raw_input):
        return raw_input
    return "manual://" + hashlib.sha1(raw_input.encode("utf-8")).hexdigest()[:12]


def fetch_job_text(url: str) -> str:
    """Fetch a job page and return its visible text (best-effort)."""
    import httpx
    from bs4 import BeautifulSoup

    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        resp = client.get(url)
        resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text[:6000]


def _heuristic_fields(text: str) -> dict:
    """Fallback extraction when the LLM is unavailable."""
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "Untitled role")
    email = EMAIL_RE.search(text)
    return {
        "title": first[:90],
        "company": "",
        "location": "",
        "job_type": "",
        "description": text[:2000],
        "contact_email": email.group(0) if email else "",
        "how_to_apply": "",
    }


def parse_job_fields(text: str) -> dict:
    """Extract structured job fields from text via Qwen function-calling."""
    if not os.getenv("QWEN_API_KEY"):
        logger.warning("QWEN_API_KEY not set — using heuristic job intake.")
        return _heuristic_fields(text)
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=os.getenv("QWEN_API_KEY"),
            base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        )
        fields = call_llm_tool(
            client, "qwen-plus",
            messages=[
                {"role": "system", "content":
                 "Extract structured fields from this job posting. Use an empty "
                 "string for anything not present. Capture any application/contact email."},
                {"role": "user", "content": text[:6000]},
            ],
            tool=JOB_INTAKE_TOOL,
            max_tokens=800,
        )
        # backfill a contact email from the raw text if the model missed it
        if not fields.get("contact_email"):
            m = EMAIL_RE.search(text)
            if m:
                fields["contact_email"] = m.group(0)
        return fields
    except Exception as e:
        logger.warning(f"LLM job intake failed ({e}); using heuristic.")
        return _heuristic_fields(text)


def intake_job(raw_input: str) -> dict:
    """
    Turn a URL or pasted text into a normalized job dict matching the scraper
    schema (title, company, location, expires, job_type, date_posted, url,
    source, description, contact_email, how_to_apply).
    """
    raw_input = (raw_input or "").strip()
    if not raw_input:
        raise ValueError("No job input provided.")

    url = job_key(raw_input)
    if _is_url(raw_input):
        try:
            text = fetch_job_text(url)
        except Exception as e:
            logger.warning(f"Could not fetch {url} ({e}); parsing the URL text only.")
            text = url
    else:
        text = raw_input

    fields = parse_job_fields(text)

    return {
        "title":         fields.get("title") or "Untitled role",
        "company":       fields.get("company") or "",
        "location":      fields.get("location") or "",
        "expires":       "",
        "job_type":      fields.get("job_type") or "",
        "date_posted":   "",
        "url":           url,
        "source":        "manual",
        "description":   fields.get("description") or "",
        "contact_email": fields.get("contact_email") or "",
        "how_to_apply":  fields.get("how_to_apply") or "",
    }


if __name__ == "__main__":
    import sys, json
    inp = sys.argv[1] if len(sys.argv) > 1 else "Software Developer at Acme, Harare. Email cv to hr@acme.co.zw"
    print(json.dumps(intake_job(inp), indent=2))
