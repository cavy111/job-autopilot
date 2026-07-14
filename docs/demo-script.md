# Demo Video Script — Job Application Autopilot

**Target length:** under 3:00 (judges may stop watching at 3:00 — front-load the good stuff).
**Format:** screen recording with voice-over. Upload to YouTube/Vimeo/Youku, set **public**.
**Track:** 4 — Autopilot Agent. **Goal:** show it *functioning*, and hit the four judging criteria
(Innovation 30 / Technical 30 / Impact 25 / Presentation 15) without narrating a tutorial.

> Treat it like a pitch, not a walkthrough. Show the working product first; explain the tech in
> one tight breath. Every second past 3:00 is wasted.

---

## Pre-recording checklist (do this BEFORE you hit record)

So the live run can't fail or stall on camera:

1. **Deploy is live** (if ready): record against your Alibaba Cloud URL so the browser bar shows it.
   Otherwise record locally — still valid, but mention it's the Alibaba-deployed backend.
2. **Qwen works:** run `python scripts/verify_qwen.py` → expect `✓ PASS`. Fix before filming.
3. **Seed real data:** do one full pipeline run beforehand so the dashboard already has a few
   scored jobs and at least one `awaiting_approval` row — you don't want to watch a scrape live.
4. **Gmail pre-authorized:** `token.json` in place, so **Approve & Send** works instantly (no OAuth
   popup on camera). Test one send to yourself.
5. **Have a real job posting ready** to paste for the "add a job" moment (a URL or copied text).
6. Close noisy tabs, zoom the browser to ~110%, hide bookmarks, use a clean CV.
7. Keep your CV and a sample job on screen — no personal emails/passwords visible.

---

## The script (≈2:50)

### 0:00–0:20 — Hook + problem
**On screen:** your face cam or the dashboard hero; a stack of job tabs closing.
**Say:**
> "Job hunting is the same grind a hundred times: find a posting, rewrite your CV, write a cover
> letter, send it, remember to follow up. **Job Application Autopilot** does all of that for you —
> an autonomous multi-agent system on **Qwen Cloud** — but it never sends anything without your
> say-so."

### 0:20–0:35 — What it is (one breath)
**On screen:** the architecture diagram (`docs/architecture.svg`), highlight the agent chain.
**Say:**
> "Seven agents run end to end: parse your CV, scrape live jobs, score each one against you,
> tailor a CV and cover letter, then stop at a human approval gate before submitting and tracking."

### 0:35–1:20 — The core loop (the money shot)
**On screen:** the dashboard. Upload CV → pick a **category** → **Run Pipeline** → live status bar → table fills with scored jobs.
**Say:**
> "I upload my CV, pick a category, and run it. The scraper pulls live listings, and **Qwen scores
> each job against my actual CV** — using function-calling, so every score, matched skill, and red
> flag comes back as clean structured data. High-fit jobs get a tailored CV and cover letter
> generated automatically."
**On screen:** click a job to show the score bar + status `awaiting_approval`, open the generated
`.docx` CV/cover letter briefly.

### 1:20–1:50 — Human-in-the-loop (the differentiator)
**On screen:** the `awaiting_approval` row; hover the **Approve & Send / Reject** buttons.
**Say:**
> "Here's the key: it does **not** spam employers. Every application waits for me. I review the
> tailored documents, then click **Approve & Send** — and only then does it email the application
> through Gmail and schedule a follow-up for seven days later."
**On screen:** click **Approve & Send** → row flips to `sent`.

### 1:50–2:20 — Bring your own job (any board)
**On screen:** the "➕ Add a job yourself" box; paste a real job URL or description → submit → it
appears scored and staged.
**Say:**
> "It's not locked to one job board. I can paste **any** job — a link or the raw description from
> anywhere — and Qwen extracts it into the same pipeline: scored, tailored, and staged for approval,
> just like a scraped job."

### 2:20–2:40 — Tech + production-readiness
**On screen:** quick cuts — the architecture diagram, the code (`base_url=dashscope-intl…`), the
Alibaba Cloud console / URL.
**Say:**
> "Under the hood: a modular multi-agent architecture, Qwen function-calling for every reasoning
> step, a source-agnostic design so new job boards are one adapter, and the whole backend runs on
> **Alibaba Cloud**. It even has a heuristic fallback so it runs with zero API credits."

### 2:40–2:50 — Close
**On screen:** dashboard with several tracked applications; your name/handle.
**Say:**
> "Autonomous where it should be, human where it matters. That's Job Application Autopilot on Qwen
> Cloud. Thanks for watching."

---

## Criteria coverage (make sure each lands)

- **Innovation (30%)** — say "function-calling" and show structured output; the CV-driven scoring.
- **Technical (30%)** — architecture diagram, multi-agent, source-agnostic adapters, Alibaba deploy.
- **Impact (25%)** — the relatable problem in the hook; "any board"; follow-up automation.
- **Presentation (15%)** — clean screen, tight VO, the diagram on screen, under 3:00.

## Do / Don't

- **Do** show real documents opening and a real status change (`awaiting_approval → sent`).
- **Do** keep the browser URL visible if it's the Alibaba Cloud deployment.
- **Don't** read code line by line or explain setup — that's what the repo is for.
- **Don't** run a cold scrape live; use pre-seeded data and let one action (approve, or add-a-job)
  happen live for authenticity.
- **Don't** show any real third-party contact emails when approving — use a test job to yourself.
