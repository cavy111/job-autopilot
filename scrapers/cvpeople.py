"""
scrapers/cvpeople.py — SOURCE ADAPTER TEMPLATE (scaffold, not yet implemented)

This file demonstrates how to add a new job source to the pipeline. The pipeline
is deliberately *source-agnostic*: every adapter only has to produce normalized
`JobListing` objects, and all downstream stages (relevance scoring, CV tailoring,
cover-letter generation, human approval, submission, and tracking) consume that
schema without knowing or caring which site a job came from.

To add a source (e.g. cvpeople.africa), copy this file and implement `scrape()`:

  The adapter contract
  --------------------
  Expose a single entry point:

      scrape(categories, max_pages, fetch_details, skip_urls) -> list[JobListing]

  Each returned `JobListing` should set at minimum:
      title, company, location, url, source="cvpeople"
  and, where available (needed for auto-submission):
      description, contact_email, how_to_apply

  Return a de-duplicated list (key on `url`). Respect `skip_urls` to avoid
  re-fetching jobs already tracked, and be polite (rate-limit requests).

Wire a finished adapter into the pipeline by importing its `scrape` in
`main.py → step_scrape()` and merging its results with the other sources.

This template intentionally returns an empty list so it is safe to reference
before it is implemented — the pipeline simply gets no jobs from this source.
"""

import logging

from scrapers.vacancymail import JobListing  # shared normalized schema

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cvpeople.africa"  # example target


def scrape(
    categories: list[str] = ("ict",),
    max_pages: int = 3,
    fetch_details: bool = True,
    skip_urls: set = None,
) -> list[JobListing]:
    """Scaffold adapter. Implement fetching + parsing here and return
    normalized JobListing objects. See the module docstring for the contract."""
    skip_urls = skip_urls or set()
    logger.info("cvpeople adapter is a template — no listings returned yet.")

    listings: list[JobListing] = []

    # --- IMPLEMENT ME ---------------------------------------------------------
    # 1. For each category, fetch the listing pages (httpx + BeautifulSoup).
    # 2. Parse each card into a JobListing(..., source="cvpeople").
    # 3. If fetch_details: open each job page for description + contact_email.
    # 4. Skip any url already in skip_urls; de-duplicate on url.
    #
    # Example of the shape you must return:
    # listings.append(JobListing(
    #     title="Software Developer",
    #     company="Example Co",
    #     location="Harare",
    #     expires="30 Jul 2026",
    #     job_type="Full Time",
    #     date_posted="1 day ago",
    #     url=f"{BASE_URL}/jobs/software-developer-123/",
    #     source="cvpeople",
    #     description="...",
    #     contact_email="hr@example.co.zw",
    #     how_to_apply="Email your CV to ...",
    # ))
    # --------------------------------------------------------------------------

    return listings


if __name__ == "__main__":
    jobs = scrape()
    print(f"cvpeople adapter returned {len(jobs)} listings (template scaffold).")
