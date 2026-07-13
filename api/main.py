"""
api/main.py — FastAPI Dashboard
"""

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys, shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.tracker import init_db, get_all, get_stats, update_status, get_application
from agents.status import read_status, reset_status

app = FastAPI(title="Job Application Autopilot")
templates = Jinja2Templates(directory="api/templates")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
CV_POINTER = Path("active_cv.txt")

init_db()

STATUS_COLORS = {
    "pending":     "#6c757d",
    "tailoring":   "#0dcaf0",
    "ready":       "#0d6efd",
    "awaiting_approval": "#6f42c1",
    "sent":        "#ffc107",
    "followed_up": "#fd7e14",
    "interview":   "#198754",
    "rejected":    "#dc3545",
    "closed":      "#adb5bd",
}


def get_active_cv() -> str | None:
    if CV_POINTER.exists():
        path = CV_POINTER.read_text().strip()
        if Path(path).exists():
            return path
    return None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    apps  = get_all()
    stats = get_stats()
    cv    = get_active_cv()
    for a in apps:
        a["status_color"] = STATUS_COLORS.get(a["status"], "#6c757d")
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"apps": apps, "stats": stats, "active_cv": cv},
    )


@app.get("/pipeline-status")
async def pipeline_status():
    """Polled by the dashboard's JS every couple seconds."""
    return JSONResponse(read_status())


@app.post("/upload-cv")
async def upload_cv(cv_file: UploadFile = File(...)):
    suffix = Path(cv_file.filename).suffix.lower()
    if suffix not in {".docx", ".pdf"}:
        return RedirectResponse("/?error=invalid_file_type", status_code=303)
    dest = UPLOAD_DIR / cv_file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(cv_file.file, f)
    CV_POINTER.write_text(str(dest))
    return RedirectResponse("/", status_code=303)


@app.post("/update-status")
async def update(job_url: str = Form(...), status: str = Form(...)):
    update_status(job_url, status)
    return RedirectResponse("/", status_code=303)


@app.post("/run-pipeline")
async def run_pipeline():
    import subprocess
    reset_status()
    cv = get_active_cv()
    cmd = [sys.executable, "main.py"]
    if cv:
        cmd += ["--cv", cv]
    subprocess.Popen(cmd)
    return RedirectResponse("/", status_code=303)


@app.post("/approve-application")
async def approve_application(job_url: str = Form(...)):
    """Human-in-the-loop checkpoint: send a staged application only on approval."""
    from agents.submission import send_application
    from datetime import datetime, timedelta

    app_row = get_application(job_url)
    if not app_row:
        return RedirectResponse("/?error=not_found", status_code=303)

    contact_email = app_row.get("contact_email") or ""
    if not contact_email:
        update_status(job_url, "awaiting_approval",
                      notes="Cannot send — no contact email on file")
        return RedirectResponse("/?error=no_contact_email", status_code=303)

    job = {
        "title":   app_row.get("job_title", ""),
        "company": app_row.get("company", ""),
        "url":     app_row.get("job_url", ""),
    }
    sent = send_application(
        cv_profile={},
        job=job,
        cv_path=app_row.get("cv_path") or "",
        cover_letter_path=app_row.get("cover_letter_path") or "",
        contact_email=contact_email,
        subject=app_row.get("email_subject") or f"Application for {job['title']}",
        dry_run=False,
    )
    if sent:
        sent_at = datetime.now()
        update_status(job_url, "sent", sent_at=sent_at,
                      follow_up_at=sent_at + timedelta(days=7))
    else:
        update_status(job_url, "awaiting_approval",
                      notes="Send failed — check Gmail credentials")
    return RedirectResponse("/", status_code=303)


@app.post("/reject-application")
async def reject_application(job_url: str = Form(...)):
    """Discard a staged application without sending."""
    update_status(job_url, "closed", notes="Rejected by user")
    return RedirectResponse("/", status_code=303)
