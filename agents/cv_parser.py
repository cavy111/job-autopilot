"""
agents/cv_parser.py

Parses Calvin's CV (docx or PDF) into a structured dict that all
downstream agents (relevance filter, cv tailor, cover letter) can use.

Two-stage approach:
  Stage 1 — Extract raw text from the file (no LLM needed)
  Stage 2 — Structure the text into a typed dict via Qwen

For now, Stage 1 uses python-docx for .docx files and pdfplumber for PDFs.
Stage 2 uses the Qwen API (swap base_url to test with OpenAI-compatible APIs).
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_utils import parse_llm_json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data shape — what we extract from the CV
# ---------------------------------------------------------------------------

EMPTY_PROFILE: dict = {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "summary": "",
    "skills": {
        "languages": [],
        "frameworks": [],
        "databases": [],
        "devops": [],
        "other": [],
    },
    "experience": [],
    "education": [],
    "certifications": [],
    "references": [],
    "raw_text": "",
}


# ---------------------------------------------------------------------------
# Stage 1 — Raw text extraction
# ---------------------------------------------------------------------------

def _extract_from_docx(path: str) -> str:
    try:
        from docx import Document
    except ImportError:
        raise ImportError("python-docx not installed. Run: pip install python-docx")
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _extract_from_pdf(path: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber not installed. Run: pip install pdfplumber")
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    text = "\n".join(pages).strip()
    if len(text) < 100:
        raise ValueError(
            "Extracted text is too short — the PDF may be scanned/image-based. "
            "Please provide a text-based PDF or a .docx file instead."
        )
    return text


def extract_raw_text(cv_path: str) -> str:
    path = Path(cv_path)
    if not path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_path}")
    suffix = path.suffix.lower()
    logger.info(f"Extracting text from {suffix} file: {path.name}")
    if suffix == ".docx":
        return _extract_from_docx(cv_path)
    elif suffix == ".pdf":
        return _extract_from_pdf(cv_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Use .docx or .pdf")


# ---------------------------------------------------------------------------
# Stage 2 — LLM structuring via Qwen API
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a precise CV parser. Extract structured information from the CV text provided.

Return ONLY a valid JSON object with exactly these fields:
{
  "name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "summary": "string",
  "skills": {
    "languages": ["list of programming languages"],
    "frameworks": ["list of frameworks and libraries"],
    "databases": ["list of database technologies"],
    "devops": ["list of devops tools and platforms"],
    "other": ["list of other skills"]
  },
  "experience": [
    {
      "title": "job title",
      "company": "company name",
      "location": "city, country",
      "period": "start - end",
      "bullets": ["responsibility or achievement"]
    }
  ],
  "education": [
    {
      "degree": "degree name",
      "grade": "grade or null",
      "institution": "institution name",
      "location": "city, country",
      "period": "years"
    }
  ],
  "certifications": ["list of certification strings"],
  "references": [
    {
      "name": "full name",
      "role": "title and organisation",
      "contact": "phone and/or email"
    }
  ]
}

Rules:
- Return ONLY the JSON object. No markdown, no backticks, no explanation.
- If a field is not found, use null for strings or [] for arrays.
- Preserve exact names, dates, and contact details from the CV.
- Do not invent or infer information not present in the text.
"""


def _call_llm(raw_text: str) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise EnvironmentError("QWEN_API_KEY not set. Add it to your .env file.")

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    logger.info("Sending CV text to Qwen for structuring...")
    response = client.chat.completions.create(
        model="qwen-plus",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this CV:\n\n{raw_text}"},
        ],
        temperature=0.1,
        max_tokens=2000,
    )

    raw_response = response.choices[0].message.content.strip()
    return parse_llm_json(raw_response)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def parse_cv(cv_path: str, use_llm: bool = True) -> dict:
    """
    Parse a CV file into a structured profile dict.

    Args:
        cv_path:  Path to the CV file (.docx or .pdf)
        use_llm:  If True, uses Qwen to structure the text (requires API key).
                  If False, returns raw_text only — useful for testing Stage 1.

    Returns:
        Dict matching the EMPTY_PROFILE shape, plus raw_text field.
    """
    raw_text = extract_raw_text(cv_path)
    logger.info(f"Extracted {len(raw_text)} characters of raw text")

    if not use_llm:
        logger.info("use_llm=False — returning raw text only")
        profile = EMPTY_PROFILE.copy()
        profile["raw_text"] = raw_text
        return profile

    profile = _call_llm(raw_text)
    profile["raw_text"] = raw_text
    return profile


# ---------------------------------------------------------------------------
# Quick test — run directly: python agents/cv_parser.py path/to/cv.docx
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    cv_path = sys.argv[1] if len(sys.argv) > 1 else "Calvin_Dube_CV_Gateway.docx"

    print(f"\nParsing: {cv_path}")
    print("=" * 55)

    # Stage 1 — no API key needed
    print("\n[Stage 1] Extracting raw text...")
    raw = extract_raw_text(cv_path)
    print(f"  Extracted {len(raw)} characters")
    print(f"  Preview:\n{raw[:300]}\n...")

    # Stage 2 — needs QWEN_API_KEY in .env
    if os.getenv("QWEN_API_KEY"):
        print("\n[Stage 2] Structuring with Qwen...")
        profile = parse_cv(cv_path)
        print(f"\n  Name:      {profile.get('name')}")
        print(f"  Email:     {profile.get('email')}")
        print(f"  Phone:     {profile.get('phone')}")
        print(f"  Languages: {profile.get('skills', {}).get('languages')}")
        print(f"  Jobs:      {len(profile.get('experience', []))} roles")
        print(f"  Education: {len(profile.get('education', []))} entries")
        with open("cv_profile.json", "w") as f:
            json.dump(profile, f, indent=2)
        print("\nFull profile saved to cv_profile.json")
    else:
        print("\n[Stage 2] Skipped — QWEN_API_KEY not set in .env")
        print("  Once you have credits, add QWEN_API_KEY=... to your .env")
        print("  and run: python agents/cv_parser.py Calvin_Dube_CV_Gateway.docx")