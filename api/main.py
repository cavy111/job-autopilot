"""
api/main.py — FastAPI Dashboard

Shows a real-time view of the job application pipeline:
  - Stats (total, sent, pending, review, interview)
  - Applications table with status, score, company, role
  - Action buttons: mark as interview, rejected, closed
  - Trigger a new pipeline run from the UI

Run with: uvicorn api.main:app --reload
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys, os

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.tracker import init_db, get_all, get_stats, update_status

app = FastAPI(title="Job Application Autopilot")
templates = Jinja2Templates(directory="api/templates")

init_db()

STATUS_COLORS = {
    "pending":     "#6c757d",
    "tailoring":   "#0dcaf0",
    "ready":       "#0d6efd",
    "sent":        "#ffc107",
    "followed_up": "#fd7e14",
    "interview":   "#198754",
    "rejected":    "#dc3545",
    "closed":      "#adb5bd",
}

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    apps  = get_all()
    stats = get_stats()
    for a in apps:
        a["status_color"] = STATUS_COLORS.get(a["status"], "#6c757d")
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"apps": apps, "stats": stats},
    )

@app.post("/update-status")
async def update(job_url: str = Form(...), status: str = Form(...)):
    update_status(job_url, status)
    return RedirectResponse("/", status_code=303)

@app.post("/run-pipeline")
async def run_pipeline():
    """Trigger a pipeline run in the background."""
    import subprocess, sys
    subprocess.Popen([sys.executable, "main.py"])
    return RedirectResponse("/", status_code=303)