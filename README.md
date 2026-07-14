# Job Application Autopilot 🤖

> An autonomous multi-agent system that scrapes job boards, scores listings against your CV, generates tailored application documents, and — after a one-click **human approval** — submits them via email. Powered by **Qwen Cloud function-calling**.

Built for the **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**

---

## What It Does

Job Application Autopilot runs a multi-agent pipeline end-to-end, pausing only at a **human approval checkpoint** before any email is sent:

```
CV Parser → Job Scraper → Relevance Filter → CV Tailor → Cover Letter → 🧑 Human Approval → Submission → Tracker → Follow-up
```

1. **CV Parser** — Extracts structured data from your CV (`.docx` or `.pdf`) using Qwen
2. **Job Scraper** — Crawls vacancymail.co.zw for new listings (**category selectable** from the dashboard) with full descriptions
3. **Relevance Filter** — Scores each listing against your CV (0–100) using Qwen **function-calling** for reliable structured output
4. **CV Tailor** — Rewrites your professional summary to mirror the job description language
5. **Cover Letter Generator** — Produces a personalised 4-paragraph cover letter per job
6. **Submission Agent** — After you click **Approve & Send**, emails the application with `.docx` attachments via Gmail API
7. **Tracker + Follow-up** — Logs every application to SQLite and sends follow-ups after 7 days

A **FastAPI dashboard** provides a real-time view of all applications, scores, and statuses — with CV upload, a **category selector**, live pipeline status, and one-click **Approve / Reject** on each staged application. You can also **paste any job URL or description** (from any board) and run it through the same pipeline.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM | Qwen Cloud (`qwen-plus`) — **function-calling / tools API** |
| Scraping | `httpx` + `BeautifulSoup4` |
| CV Parsing | `pdfplumber`, `python-docx` |
| Email | Gmail API (OAuth2) |
| Database | SQLite |
| Dashboard | FastAPI + Jinja2 |

---

## Project Structure

```
job-autopilot/
├── agents/
│   ├── cv_parser.py         # Extract/structure CV data via Qwen function-calling
│   ├── relevance_filter.py  # Score jobs against CV (heuristic + LLM modes)
│   ├── cv_tailor.py         # Rewrite CV summary per job via Qwen
│   ├── cover_letter.py      # Generate cover letter per job via Qwen
│   ├── job_intake.py        # Turn a pasted URL/description into a normalized job
│   ├── submission.py        # Send application email via Gmail API
│   ├── tracker.py           # SQLite CRUD for application lifecycle
│   ├── followup.py          # Send follow-up emails after 7 days
│   ├── llm_utils.py         # Shared Qwen JSON + tool-call helpers
│   └── sample_profile.py    # Fictional profile for offline demos/tests
├── scrapers/
│   ├── vacancymail.py       # Reference source adapter (vacancymail.co.zw)
│   └── cvpeople.py          # Documented adapter template (scaffold)
├── api/
│   ├── main.py              # FastAPI dashboard + endpoints
│   └── templates/
│       └── dashboard.html   # Dashboard UI
├── db/
│   └── schema.sql           # SQLite schema
├── docs/
│   ├── architecture.svg     # System architecture diagram
│   ├── architecture.md      # Architecture write-up (+ Mermaid)
│   └── deploy-alibaba-cloud.md
├── scripts/
│   └── verify_qwen.py       # One-command Qwen function-calling smoke test
├── main.py                  # Orchestrator — runs the full pipeline
├── requirements.txt
└── .env.example
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- A Qwen Cloud API key — [get one here](https://home.qwencloud.com/api-keys)
- A Google Cloud project with Gmail API enabled — [setup guide](#gmail-api-setup)

### Installation

```bash
# Clone the repo
git clone https://github.com/cavy111/job-autopilot.git
cd job-autopilot

# Create and activate virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows Git Bash
# or: source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Configuration

```bash
# Copy the example env file
cp .env.example .env

# Add your Qwen API key to .env
QWEN_API_KEY=your_qwen_api_key_here
```

### Gmail API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project → Enable the Gmail API
3. Go to **APIs & Services → OAuth consent screen** → External → Create
4. Add yourself as a test user under **Test users**
5. Go to **Credentials → Create Credentials → OAuth client ID → Desktop app**
6. Download the JSON and save it as `credentials.json` in the project root

> `credentials.json` and `token.json` are gitignored — never commit these files.

### Running the Dashboard

```bash
uvicorn api.main:app --reload
```

Open **http://localhost:8000** — upload your CV using the upload button on the dashboard, then click **Run Pipeline Now**.

### Running the Pipeline from CLI

```bash
# Default — tailor documents and stage each job for your approval (no emails sent)
python main.py --cv path/to/your-cv.docx

# Full autonomy — auto-approve and send
python main.py --cv path/to/your-cv.docx --send

# Scrape a specific category (see keys in scrapers/vacancymail.py)
python main.py --cv path/to/your-cv.docx --categories sales-marketing

# Process a single pasted job (a file containing a URL or description)
python main.py --cv path/to/your-cv.docx --add-job-file pending_job.txt

# Only check and send follow-ups
python main.py --followups-only
```

---

## How Scoring Works

Each job is scored 0–100 against the candidate's CV profile:

$$S = S_{title} + S_{skills} + S_{domain} + S_{location} - S_{redflags}$$

| Component | Max Points | Description |
|---|---|---|
| $S_{title}$ | 40 | Strong/weak title pattern match |
| $S_{skills}$ | 30 | Skill keyword hits (6pts each) |
| $S_{domain}$ | 20 | Domain relevance match |
| $S_{location}$ | 10 | Harare/remote/Zimbabwe bonus |
| $S_{redflags}$ | -25 each | Experience mismatch penalties |

**Thresholds:**
- Score ≥ 70 → **APPLY** (documents generated, then staged for your approval)
- Score 50–69 → **REVIEW** (logged, not auto-applied)
- Score < 50 → **SKIP**

In LLM mode (when `QWEN_API_KEY` is set), Qwen replaces the heuristic formula with semantic reasoning. The result comes back through a **function-call (tools API)** with a fixed schema, so the score, matched keywords, red flags, and written justification are always well-formed structured JSON.

---

## Dual-Mode Architecture

Every LLM-dependent agent has two modes:

| Mode | When | Description |
|---|---|---|
| **Heuristic** | No API key | Fast keyword matching, no credits needed |
| **LLM** | API key present | Semantic reasoning via Qwen, activates automatically |

This means the full pipeline can be tested and iterated without spending any API credits.

---

## Extensibility

The pipeline is **source-agnostic by design**. Each job source is an adapter under
`scrapers/` that produces a normalized `JobListing` (`title`, `company`, `location`,
`url`, `description`, `contact_email`, `source`, …). Every downstream stage — relevance
scoring, CV tailoring, cover-letter generation, human approval, submission, and tracking —
consumes that schema and is **completely independent of where the job came from**.

Adding a new job board therefore means writing **one adapter** — no changes to the
pipeline. See `scrapers/cvpeople.py` for a documented adapter template describing the
contract, and `scrapers/vacancymail.py` for the reference implementation.

- **Current reference integration:** `vacancymail.co.zw` (live, end-to-end).
- **Roadmap:** additional boards (e.g. cvpeople.africa), user-supplied job URLs/descriptions,
  and a form/ATS submission channel alongside the current email channel.

## Dashboard

The FastAPI dashboard at `http://localhost:8000` shows:

- **CV upload** — drag and drop your `.docx` or `.pdf` CV to get started
- **Stats row** — total tracked, sent, interviews, pending, rejected
- **Application table** — role, company, relevance score bar, status badge, expiry date
- **Status controls** — manually mark applications as interview/rejected/closed
- **Search category** — choose which vacancymail category to scrape
- **Run Pipeline** — trigger a new pipeline run from the UI (disabled until CV is uploaded)
- **Add a job yourself** — paste a job URL or description from *any* board; Qwen extracts it and runs it through the same pipeline
- **Approve / Reject** — one-click human approval on each staged application before any email is sent

---

## Important Notes

- **Human-in-the-loop by default** — the pipeline tailors documents and stages each application for your approval; nothing is emailed until you click **Approve & Send** (or run with `--send` for full autonomy)
- The agent will never fabricate experience or skills not present in the CV
- Applications are deduplicated by URL — re-running won't double-apply
- Follow-ups are sent exactly 7 days after the application email

---

## Documentation

- [Architecture](docs/architecture.md) — system diagram and component-by-component breakdown
- [Deploying to Alibaba Cloud](docs/deploy-alibaba-cloud.md) — ECS deployment runbook + submission proof
- Verify your Qwen setup: `python scripts/verify_qwen.py`

---

## Author

**Dube Calvin** — BSc (Hons) Information Systems, Midlands State University
GitHub: [@cavy111](https://github.com/cavy111)

---

## License

MIT
