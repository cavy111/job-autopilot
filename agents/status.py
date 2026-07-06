"""
agents/status.py

Tiny helper the orchestrator uses to report pipeline progress to a JSON
file, which the dashboard polls to show live status without needing
WebSockets.
"""

import json
import time
from pathlib import Path

STATUS_FILE = Path("pipeline_status.json")

STEPS = [
    "idle", "loading_cv", "scraping", "filtering",
    "scoring", "applying", "followups", "done", "error",
]


def write_status(step: str, message: str = "", progress: int = 0, detail: str = ""):
    """Write current pipeline status to disk for the dashboard to poll."""
    data = {
        "step": step,
        "message": message,
        "progress": progress,   # 0-100
        "detail": detail,
        "timestamp": time.time(),
    }
    STATUS_FILE.write_text(json.dumps(data))


def read_status() -> dict:
    """Read current status, or return idle if no run has started."""
    if not STATUS_FILE.exists():
        return {"step": "idle", "message": "", "progress": 0, "detail": "", "timestamp": 0}
    try:
        return json.loads(STATUS_FILE.read_text())
    except Exception:
        return {"step": "idle", "message": "", "progress": 0, "detail": "", "timestamp": 0}


def reset_status():
    write_status("idle", "", 0)