"""
agents/relevance_filter.py

Scores job listings against Calvin's CV profile and decides whether to apply.

Two modes:
  Heuristic mode (default, no API needed):
    - Keyword matching against skills, title patterns, and experience
    - Fast, free, testable immediately
    - Good enough for filtering obvious mismatches

  LLM mode (requires QWEN_API_KEY):
    - Sends CV summary + job description to Qwen
    - Returns semantic score with detailed reasoning
    - More accurate for nuanced matches

Score: 0-100
  >= 70  → APPLY (strong match)
  50-69  → REVIEW (possible match, worth checking manually)
  < 50   → SKIP
"""

import os
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring thresholds
# ---------------------------------------------------------------------------

APPLY_THRESHOLD  = 70   # auto-apply above this
REVIEW_THRESHOLD = 50   # flag for manual review between 50-69
# below 50 = skip silently

# ---------------------------------------------------------------------------
# Calvin's keyword profile — used in heuristic mode
# Built from his actual CV so no API needed to filter obvious matches
# ---------------------------------------------------------------------------

CALVIN_SKILLS = {
    "languages": [
        "python", "javascript", "php", "java", "html", "css", "html5", "css3"
    ],
    "frameworks": [
        "django", "react", "laravel", "spring boot", "spring", "flutter"
    ],
    "databases": [
        "sql", "mysql", "postgresql", "sqlite", "supabase", "firebase"
    ],
    "devops": [
        "git", "digitalocean", "docker", "linux", "ubuntu", "rest", "api",
        "restful", "json"
    ],
    "domains": [
        "web development", "web developer", "software developer",
        "software engineer", "full stack", "fullstack", "backend", "frontend",
        "it support", "systems support", "ict", "information systems",
        "information technology", "web applications", "web app",
        "application developer", "software development", "ai", "automation",
        "machine learning", "artificial intelligence", "data engineering",
        "digital", "technology officer", "it officer", "ict officer",
    ],
}

# Titles that are a strong direct match
STRONG_TITLE_PATTERNS = [
    r"software\s+dev",
    r"web\s+dev",
    r"full.?stack",
    r"python\s+dev",
    r"django",
    r"react\s+dev",
    r"application\s+dev",
    r"systems\s+dev",
    r"it\s+officer",
    r"ict\s+officer",
    r"systems\s+support",
    r"it\s+support",
    r"webmaster",
    r"ai\s+.{0,20}engineer",
    r"automation\s+engineer",
    r"digital\s+.{0,20}officer",
    r"technology\s+.{0,20}developer",
    r"it\s+.{0,20}specialist",
]

# Titles that are a weak/partial match — worth reviewing
WEAK_TITLE_PATTERNS = [
    r"technician",
    r"analyst",
    r"data\s+",
    r"network",
    r"database",
    r"graduate\s+trainee",
    r"it\s+graduate",
    r"trainee",
    r"intern",
    r"it\s+.{0,20}communications",
]

# Red flags — likely not a good fit regardless of score
RED_FLAG_PATTERNS = [
    r"10\+?\s+years",
    r"15\+?\s+years",
    r"senior\s+(software|web|it)",   # senior roles requiring deep experience
    r"chief\s+",
    r"director\s+of",
    r"head\s+of\s+it",
    r"c(?:to|io|iso)\b",             # CTO, CIO, CISO
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FilterResult:
    job_url: str
    job_title: str
    company: str
    score: int                        # 0-100
    decision: str                     # "APPLY", "REVIEW", or "SKIP"
    matched_keywords: list[str]
    red_flags: list[str]
    reasoning: str
    mode: str                         # "heuristic" or "llm"

    def to_dict(self) -> dict:
        return {
            "job_url": self.job_url,
            "job_title": self.job_title,
            "company": self.company,
            "score": self.score,
            "decision": self.decision,
            "matched_keywords": self.matched_keywords,
            "red_flags": self.red_flags,
            "reasoning": self.reasoning,
            "mode": self.mode,
        }


# ---------------------------------------------------------------------------
# Heuristic scoring (no API)
# ---------------------------------------------------------------------------

def _heuristic_score(job: dict) -> FilterResult:
    """
    Score a job listing using keyword matching against Calvin's skill profile.

    job dict expected keys: title, company, location, description (optional),
    url, job_type, expires
    """
    title       = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    company     = job.get("company", "Unknown")
    url         = job.get("url", "")
    text        = f"{title} {description}"  # combined searchable text

    score = 0
    matched = []
    red_flags = []
    reasons = []

    # 1. Title pattern matching (weighted highest — 40 points max)
    strong_title_hit = False
    for pattern in STRONG_TITLE_PATTERNS:
        if re.search(pattern, title):
            score += 40
            matched.append(f"title: '{pattern}'")
            strong_title_hit = True
            reasons.append(f"Title strongly matches role type ({pattern})")
            break  # only count one strong title hit

    if not strong_title_hit:
        for pattern in WEAK_TITLE_PATTERNS:
            if re.search(pattern, title):
                score += 15
                matched.append(f"title (weak): '{pattern}'")
                reasons.append(f"Title partially matches ({pattern})")
                break

    # 2. Skill keyword matching in description (30 points max)
    all_skills = (
        CALVIN_SKILLS["languages"]
        + CALVIN_SKILLS["frameworks"]
        + CALVIN_SKILLS["databases"]
        + CALVIN_SKILLS["devops"]
    )
    skill_hits = []
    for skill in all_skills:
        if skill in text and skill not in skill_hits:
            skill_hits.append(skill)

    skill_score = min(30, len(skill_hits) * 6)  # 6 points per skill, max 30
    score += skill_score
    matched.extend(skill_hits)
    if skill_hits:
        reasons.append(f"Matched {len(skill_hits)} skills: {', '.join(skill_hits[:5])}")

    # 3. Domain keyword matching (20 points max)
    domain_hits = []
    for domain in CALVIN_SKILLS["domains"]:
        if domain in text:
            domain_hits.append(domain)
    domain_score = min(20, len(domain_hits) * 10)
    score += domain_score
    if domain_hits:
        reasons.append(f"Domain match: {', '.join(domain_hits[:3])}")
        matched.extend(domain_hits)

    # 4. Location bonus — Harare or remote preferred (10 points)
    location = (job.get("location") or "").lower()
    if "harare" in location or "remote" in location or "zimbabwe" in location:
        score += 10
        reasons.append("Location is Harare / remote / Zimbabwe")

    # 5. Red flag detection — cap score or reduce
    for pattern in RED_FLAG_PATTERNS:
        if re.search(pattern, text):
            red_flags.append(pattern)
            score = max(0, score - 25)
            reasons.append(f"Red flag: {pattern}")

    # Cap at 100
    score = min(100, score)

    # Decision
    if score >= APPLY_THRESHOLD:
        decision = "APPLY"
    elif score >= REVIEW_THRESHOLD:
        decision = "REVIEW"
    else:
        decision = "SKIP"

    reasoning = " | ".join(reasons) if reasons else "No strong signals found"

    return FilterResult(
        job_url=url,
        job_title=job.get("title", ""),
        company=company,
        score=score,
        decision=decision,
        matched_keywords=list(set(matched)),
        red_flags=red_flags,
        reasoning=reasoning,
        mode="heuristic",
    )


# ---------------------------------------------------------------------------
# LLM scoring (requires QWEN_API_KEY)
# ---------------------------------------------------------------------------

LLM_SYSTEM_PROMPT = """You are a job application advisor helping a candidate decide which jobs to apply for.

You will be given:
1. A candidate profile (skills, experience, education)
2. A job listing (title, company, description)

Score how well the candidate matches this job from 0 to 100.

Return ONLY a JSON object with these fields:
{
  "score": <integer 0-100>,
  "decision": "<APPLY|REVIEW|SKIP>",
  "matched_keywords": ["list of matching skills or keywords"],
  "red_flags": ["list of concerns or mismatches"],
  "reasoning": "2-3 sentence explanation of the score"
}

Scoring guide:
  80-100: Strong match — most requirements met, apply immediately
  60-79:  Good match — core skills match, some gaps but worth applying
  40-59:  Partial match — some relevant skills but significant gaps, review manually
  0-39:   Poor match — major mismatch in skills, experience level, or role type

Decision:
  APPLY  if score >= 70
  REVIEW if score 50-69
  SKIP   if score < 50

Rules:
- Return ONLY the JSON. No markdown, no backticks, no explanation outside the JSON.
- Be honest about gaps — don't inflate scores.
- Consider experience level: the candidate has ~1 year professional experience.
"""


def _llm_score(job: dict, cv_profile: dict) -> FilterResult:
    """Score a job listing using Qwen LLM for semantic matching."""
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError("openai not installed. Run: pip install openai")

    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        raise EnvironmentError("QWEN_API_KEY not set in .env")

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    # Build a compact candidate summary to keep tokens low
    skills_flat = (
        cv_profile.get("skills", {}).get("languages", [])
        + cv_profile.get("skills", {}).get("frameworks", [])
        + cv_profile.get("skills", {}).get("databases", [])
        + cv_profile.get("skills", {}).get("devops", [])
    )
    exp = cv_profile.get("experience", [])
    exp_summary = "; ".join(
        f"{e.get('title')} at {e.get('company')} ({e.get('period')})"
        for e in exp
    )

    candidate_summary = f"""
Name: {cv_profile.get('name')}
Skills: {', '.join(skills_flat)}
Experience: {exp_summary}
Education: {cv_profile.get('education', [{}])[0].get('degree', '')} from {cv_profile.get('education', [{}])[0].get('institution', '')}
Summary: {cv_profile.get('summary', '')[:300]}
""".strip()

    job_text = f"""
Title: {job.get('title')}
Company: {job.get('company')}
Location: {job.get('location')}
Type: {job.get('job_type')}
Description: {(job.get('description') or 'Not available')[:800]}
""".strip()

    user_message = f"CANDIDATE:\n{candidate_summary}\n\nJOB:\n{job_text}"

    response = client.chat.completions.create(
        model="qwen-turbo",
        messages=[
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=500,
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)
    score = int(result.get("score", 0))

    return FilterResult(
        job_url=job.get("url", ""),
        job_title=job.get("title", ""),
        company=job.get("company", ""),
        score=score,
        decision=result.get("decision", "SKIP"),
        matched_keywords=result.get("matched_keywords", []),
        red_flags=result.get("red_flags", []),
        reasoning=result.get("reasoning", ""),
        mode="llm",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def filter_job(job: dict, cv_profile: Optional[dict] = None) -> FilterResult:
    """
    Score a single job listing against Calvin's CV.

    Args:
        job:        JobListing dict from the scraper (must have title, url, company)
        cv_profile: Parsed CV dict from cv_parser.parse_cv().
                    If None or QWEN_API_KEY not set, falls back to heuristic mode.

    Returns:
        FilterResult with score, decision, and reasoning.
    """
    use_llm = bool(os.getenv("QWEN_API_KEY")) and cv_profile is not None

    if use_llm:
        try:
            logger.info(f"LLM scoring: {job.get('title')} @ {job.get('company')}")
            return _llm_score(job, cv_profile)
        except Exception as e:
            logger.warning(f"LLM scoring failed ({e}), falling back to heuristic")

    logger.info(f"Heuristic scoring: {job.get('title')} @ {job.get('company')}")
    return _heuristic_score(job)


def filter_jobs(jobs: list[dict], cv_profile: Optional[dict] = None) -> list[FilterResult]:
    """
    Score a list of job listings. Returns all results sorted by score descending.
    """
    results = []
    for job in jobs:
        result = filter_job(job, cv_profile)
        logger.info(
            f"  [{result.decision:6}] {result.score:3}/100 — "
            f"{result.job_title[:45]} @ {result.company}"
        )
        results.append(result)

    results.sort(key=lambda r: r.score, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Quick test — python agents/relevance_filter.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Load real scraped listings if test_output.json exists
    import sys
    from pathlib import Path

    listings_path = Path("test_output.json")
    if listings_path.exists():
        with open(listings_path) as f:
            jobs = json.load(f)
        print(f"Loaded {len(jobs)} jobs from test_output.json\n")
    else:
        # Fallback sample jobs for testing
        jobs = [
            {
                "title": "Software Developer",
                "company": "TechCorp Zimbabwe",
                "location": "Harare",
                "job_type": "Full Time",
                "url": "https://vacancymail.co.zw/jobs/software-developer-test/",
                "description": "We are looking for a Python and Django developer "
                               "with React experience to build web applications.",
            },
            {
                "title": "Data Clerk",
                "company": "Union Zimbabwe Trust",
                "location": "Masvingo",
                "job_type": "Full Time",
                "url": "https://vacancymail.co.zw/jobs/data-clerk-67881/",
                "description": "Data entry and record keeping responsibilities.",
            },
            {
                "title": "Regulatory Technology Systems Developers x3",
                "company": "Securities and Exchange Commission of Zimbabwe",
                "location": "Harare",
                "job_type": "Full Time",
                "url": "https://vacancymail.co.zw/jobs/regulatory-technology-67719/",
                "description": "Software development role requiring Python, SQL, "
                               "and REST API experience.",
            },
        ]
        print("test_output.json not found — using sample jobs\n")

    print("=" * 60)
    print("RELEVANCE FILTER RESULTS")
    print("=" * 60)

    results = filter_jobs(jobs)

    apply_list  = [r for r in results if r.decision == "APPLY"]
    review_list = [r for r in results if r.decision == "REVIEW"]
    skip_list   = [r for r in results if r.decision == "SKIP"]

    print(f"\nSummary: {len(apply_list)} APPLY | {len(review_list)} REVIEW | {len(skip_list)} SKIP\n")

    for r in results:
        icon = {"APPLY": "✓", "REVIEW": "?", "SKIP": "✗"}.get(r.decision, " ")
        print(f"{icon} [{r.score:3}/100] {r.decision:6} — {r.job_title}")
        print(f"         {r.company} | {r.reasoning[:80]}")
        if r.matched_keywords:
            print(f"         Matched: {', '.join(r.matched_keywords[:6])}")
        if r.red_flags:
            print(f"         Red flags: {', '.join(r.red_flags)}")
        print()