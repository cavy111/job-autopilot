# Job Application Autopilot 🤖

> An autonomous multi-agent system that scrapes job boards, scores listings against your CV, generates tailored application documents, and submits them via email — powered by Qwen Cloud.

Built for the **Qwen Cloud Global AI Hackathon — Track 4: Autopilot Agent**

---

## What It Does

Job Application Autopilot runs a 7-agent pipeline end-to-end with zero human intervention:

```
CV Parser → Job Scraper → Relevance Filter → CV Tailor → Cover Letter → Submission → Tracker → Follow-up
```

1. **CV Parser** — Extracts structured data from your CV (`.docx` or `.pdf`) using Qwen
2. **Job Scraper** — Crawls vacancymail.co.zw for new ICT listings with full descriptions
3. **Relevance Filter** — Scores each listing against your CV (0–100) using Qwen semantic scoring
4. **CV Tailor** — Rewrites your professional summary to mirror the job description language
5. **Cover Letter Generator** — Produces a personalised 4-paragraph cover letter per job
6. **Submission Agent** — Sends the application email with `.docx` attachments via Gmail API
7. **Tracker + Follow-up** — Logs every application to SQLite and sends follow-ups after 7 days

A **FastAPI dashboard** provides a real-time view of all applications, scores, and statuses — with a CV upload button to get started without touching any config files.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13 |
| LLM | Qwen Cloud (`qwen-plus`) |
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
│   ├── cv_parser.py         # Extract and structure CV data via Qwen
│   ├── relevance_filter.py  # Score jobs against CV (heuristic + LLM modes)
│   ├── cv_tailor.py         # Rewrite CV summary per job via Qwen
│   ├── cover_letter.py      # Generate cover letter per job via Qwen
│   ├── submission.py        # Send application email via Gmail API
│   ├── tracker.py           # SQLite CRUD for application lifecycle
│   └── followup.py          # Send follow-up emails after 7 days
├── scrapers/
│   └── vacancymail.py       # Scrape vacancymail.co.zw ICT listings
├── api/
│   ├── main.py              # FastAPI dashboard
│   └── templates/
│       └── dashboard.html   # Dashboard UI
├── db/
│   └── schema.sql           # SQLite schema
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
# Dry run (safe — no emails sent)
python main.py --cv path/to/your-cv.docx

# Live mode — sends real emails
python main.py --cv path/to/your-cv.docx --send

# Only check and send follow-ups
python main.py --followups-only

# Only scrape and score, skip document generation
python main.py --scrape-only
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
- Score ≥ 70 → **APPLY** automatically
- Score 50–69 → **REVIEW** (logged, not auto-applied)
- Score < 50 → **SKIP**

In LLM mode (when `QWEN_API_KEY` is set), Qwen replaces the heuristic formula with semantic reasoning, producing a score alongside matched keywords, red flags, and a written justification.

---

## Dual-Mode Architecture

Every LLM-dependent agent has two modes:

| Mode | When | Description |
|---|---|---|
| **Heuristic** | No API key | Fast keyword matching, no credits needed |
| **LLM** | API key present | Semantic reasoning via Qwen, activates automatically |

This means the full pipeline can be tested and iterated without spending any API credits.

---

## Dashboard

The FastAPI dashboard at `http://localhost:8000` shows:

- **CV upload** — drag and drop your `.docx` or `.pdf` CV to get started
- **Stats row** — total tracked, sent, interviews, pending, rejected
- **Application table** — role, company, relevance score bar, status badge, expiry date
- **Status controls** — manually mark applications as interview/rejected/closed
- **Run Pipeline** — trigger a new pipeline run from the UI (disabled until CV is uploaded)

---

## Important Notes

- The pipeline defaults to **dry run mode** — no emails are sent unless you pass `--send`
- The agent will never fabricate experience or skills not present in the CV
- Applications are deduplicated by URL — re-running won't double-apply
- Follow-ups are sent exactly 7 days after the application email

---

## Author

**Dube Calvin** — BSc (Hons) Information Systems, Midlands State University
GitHub: [@cavy111](https://github.com/cavy111)

---

## License

MIT