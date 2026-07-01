"""
scrapers/vacancymail.py

Scrapes job listings from vacancymail.co.zw — Zimbabwe's most established
legitimate job board. Targets the ICT & Computer category by default.

URL patterns:
  Category page:  /categories/ict-computer-jobs-in-zimbabwe/?page=2
  Job detail:     /jobs/some-job-title-12345/

HTML structure (confirmed from live site inspection):
  Each listing is:  <a class="job-listing" href="/jobs/slug/">
    <div class="job-listing-details">
      <div class="job-listing-company-logo"><img alt="CompanyName"></div>
      <div class="job-listing-description">
        <h3 class="job-listing-title">Title</h3>
        <h4 class="job-listing-company">Company</h4>
        <p class="job-listing-text">Snippet...</p>
      </div>
    </div>
    <div class="job-listing-footer">
      <ul>
        <li>Location</li>
        <li>Expires DATE</li>
        <li>Full Time</li>
        <li>TBA</li>
        <li>Posted X days</li>
      </ul>
    </div>
  </a>
"""

import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass, asdict
from typing import Optional
import time
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "https://vacancymail.co.zw"

# Category URLs to scrape — add more as needed
CATEGORIES = {
    "ict": "/categories/ict-computer-jobs-in-zimbabwe/",
    "engineering": "/categories/science-engineering-jobs-in-zimbabwe/",
}

REQUEST_DELAY = 2.0  # seconds between requests — be polite

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-ZW,en;q=0.9",
    "Referer": "https://vacancymail.co.zw/",
}

MAX_RETRIES = 3
RETRY_DELAY = 5.0


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    expires: str
    job_type: str
    date_posted: str
    url: str
    source: str = "vacancymail"
    description: Optional[str] = None
    contact_email: Optional[str] = None
    how_to_apply: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _get_page(client: httpx.Client, url: str) -> Optional[BeautifulSoup]:
    """Fetch a URL with retries. Returns BeautifulSoup or None on failure."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP {e.response.status_code} on {url} (attempt {attempt})")
        except httpx.RequestError as e:
            logger.warning(f"Network error on {url} (attempt {attempt}): {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"  Retrying in {RETRY_DELAY}s...")
                time.sleep(RETRY_DELAY)
    return None


def _parse_listing_card(anchor: BeautifulSoup) -> Optional[JobListing]:
    """
    Parse a single <a class="job-listing"> element.

    Structure confirmed from live HTML:
      - Title:    h3.job-listing-title
      - Company:  h4.job-listing-company  (also in img[alt] as fallback)
      - Snippet:  p.job-listing-text
      - Footer:   div.job-listing-footer ul > li  (location, expires, type, salary, posted)
    """
    try:
        href = anchor.get("href", "")
        if not href or "/jobs/" not in href:
            return None
        url = f"{BASE_URL}{href}" if href.startswith("/") else href

        # Title
        title_el = anchor.select_one("h3.job-listing-title")
        title = title_el.get_text(strip=True) if title_el else ""
        if not title:
            return None

        # Company — prefer h4, fall back to logo img alt text
        company_el = anchor.select_one("h4.job-listing-company")
        if company_el:
            company = company_el.get_text(strip=True)
        else:
            logo_img = anchor.select_one(".job-listing-company-logo img")
            company = logo_img.get("alt", "Unknown") if logo_img else "Unknown"

        # Footer <li> items — order: location, expires, job_type, salary, date_posted
        footer_items = anchor.select("div.job-listing-footer li")
        texts = [li.get_text(strip=True) for li in footer_items]

        location   = texts[0] if len(texts) > 0 else ""
        expires    = texts[1].replace("Expires", "").strip() if len(texts) > 1 else ""
        job_type   = texts[2] if len(texts) > 2 else None
        date_posted = texts[4].replace("Posted", "").strip() if len(texts) > 4 else ""

        # "TBA" salary in slot 3 — ignore it. Clean up job_type if it ended up as TBA
        if job_type == "TBA":
            job_type = None

        return JobListing(
            title=title,
            company=company,
            location=location,
            expires=expires,
            job_type=job_type,
            date_posted=date_posted,
            url=url,
        )

    except Exception as e:
        logger.warning(f"Failed to parse card: {e}")
        return None


def _parse_category_page(soup: BeautifulSoup) -> list[JobListing]:
    """Extract all job listings from a category page."""
    listings = []

    # Confirmed selector from live HTML: <a class="job-listing" href="/jobs/...">
    job_anchors = soup.select("a.job-listing")

    if not job_anchors:
        logger.warning("No job cards found — selector 'a.job-listing' matched nothing")
        return listings

    for anchor in job_anchors:
        listing = _parse_listing_card(anchor)
        if listing:
            listings.append(listing)

    return listings


def _has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
    """Check if there's a next page link."""
    # Pagination links look like: <a href="?page=2">2</a>
    next_page_num = current_page + 1
    return bool(soup.select_one(f'a[href*="page={next_page_num}"]'))


def _fetch_job_detail(client: httpx.Client, job: JobListing) -> JobListing:
    """
    Visit the job detail page to extract full description,
    contact email, and how-to-apply instructions.
    """
    soup = _get_page(client, job.url)
    if not soup:
        return job

    # Description — main job body
    desc_el = soup.select_one(
        ".job-description, .entry-content, "
        "article .content, .job-details-content, main p"
    )
    if desc_el:
        job.description = desc_el.get_text(separator="\n", strip=True)

    # Contact email — try mailto links first, then regex scan full page text
    import re
    email_el = soup.select_one('a[href^="mailto:"]')
    if email_el:
        job.contact_email = email_el["href"].replace("mailto:", "").strip()
    else:
        full_text = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, full_text)
        exclude = {"noreply", "example", "vacancymail"}
        for email in emails:
            if not any(x in email.lower() for x in exclude):
                job.contact_email = email
                break

    # How to apply — look for "apply" keyword in paragraphs
    for p in soup.find_all("p"):
        text = p.get_text(strip=True).lower()
        if "apply" in text and ("email" in text or "send" in text or "submit" in text):
            job.how_to_apply = p.get_text(strip=True)
            break

    return job


def scrape(
    categories: list[str] = ("ict",),
    max_pages: int = 3,
    fetch_details: bool = True,
) -> list[JobListing]:
    """
    Main entry point. Scrape vacancymail.co.zw for the given categories.

    Args:
        categories:    Keys from the CATEGORIES dict above. Default: ["ict"]
        max_pages:     Max pages per category (default 3)
        fetch_details: Fetch full description + email from each job page

    Returns:
        Deduplicated list of JobListing objects
    """
    all_listings: dict[str, JobListing] = {}  # keyed by URL

    with httpx.Client(follow_redirects=True) as client:
        for cat_key in categories:
            cat_path = CATEGORIES.get(cat_key)
            if not cat_path:
                logger.warning(f"Unknown category key: '{cat_key}'. Available: {list(CATEGORIES)}")
                continue

            logger.info(f"Scraping category: '{cat_key}'")

            for page in range(1, max_pages + 1):
                if page == 1:
                    url = f"{BASE_URL}{cat_path}"
                else:
                    url = f"{BASE_URL}{cat_path}?page={page}"

                logger.info(f"  Fetching page {page}: {url}")
                soup = _get_page(client, url)

                if not soup:
                    logger.warning(f"  Skipping page {page} — fetch failed")
                    break

                page_listings = _parse_category_page(soup)
                logger.info(f"  Found {len(page_listings)} listings")

                for listing in page_listings:
                    if listing.url not in all_listings:
                        all_listings[listing.url] = listing

                if not _has_next_page(soup, page):
                    logger.info(f"  No more pages for '{cat_key}'")
                    break

                time.sleep(REQUEST_DELAY)

        if fetch_details:
            total = len(all_listings)
            logger.info(f"Fetching details for {total} listings...")
            for i, job in enumerate(all_listings.values(), 1):
                logger.info(f"  [{i}/{total}] {job.title[:50]}")
                _fetch_job_detail(client, job)
                time.sleep(REQUEST_DELAY)

    results = list(all_listings.values())
    logger.info(f"Done. {len(results)} unique listings collected.")
    return results


if __name__ == "__main__":
    import json

    results = scrape(
        categories=["ict"],
        max_pages=2,
        fetch_details=False,  # flip to True once you confirm listings are found
    )

    print(f"\n{'='*55}")
    print(f"  Found {len(results)} jobs on vacancymail.co.zw")
    print(f"{'='*55}\n")

    for job in results[:5]:
        print(f"Title:     {job.title}")
        print(f"Company:   {job.company}")
        print(f"Location:  {job.location}")
        print(f"Expires:   {job.expires}")
        print(f"Type:      {job.job_type}")
        print(f"Posted:    {job.date_posted}")
        print(f"URL:       {job.url}")
        print("-" * 50)

    with open("test_output.json", "w") as f:
        json.dump([j.to_dict() for j in results], f, indent=2)
    print(f"\nFull results saved to test_output.json")