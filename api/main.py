"""
api/main.py — FastAPI Dashboard
"""

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import sys, os, shutil

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.tracker import init_db, get_all, get_stats, update_status

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
    cv = get_active_cv()
    cmd = [sys.executable, "main.py"]
    if cv:
        cmd += ["--cv", cv]
    subprocess.Popen(cmd)
    return RedirectResponse("/", status_code=303)