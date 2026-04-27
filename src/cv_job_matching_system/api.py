"""
FastAPI web application for the CV Job Matching System.

Run locally:
    uvicorn cv_job_matching_system.api:app --host 0.0.0.0 --port 8000 --reload

Production (Gunicorn + Uvicorn workers):
    gunicorn cv_job_matching_system.api:app -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:8000
"""

from __future__ import annotations

import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from cv_job_matching_system.crew import CvJobMatchingSystemCrew


# ---------------------------------------------------------------------------
# In-memory job store (swap for Redis/DB in a scaled deployment)
# ---------------------------------------------------------------------------

_jobs: Dict[str, dict] = {}


def _get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CV Job Matching System",
    description="AI-powered job search from your CV — searches LinkedIn, Indeed & the web.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static frontend
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_cv_bytes(data: bytes, filename: str) -> str:
    """Extract text from uploaded CV bytes (PDF or plain text)."""
    if filename.lower().endswith(".pdf"):
        try:
            import fitz
            with fitz.open(stream=data, filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Could not parse PDF: {exc}. Try a plain-text CV.",
            )
    return data.decode("utf-8", errors="ignore").strip()


def _run_crew_async(job_id: str, candidate_name: str, location: str, cv_content: str):
    """Run the crew in a background thread and update job state."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
    try:
        result = CvJobMatchingSystemCrew().crew().kickoff(
            inputs={
                "candidate_name": candidate_name,
                "location": location,
                "cv_content": cv_content,
                "cv_file_path": "",
            }
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["report"] = result.raw
        _jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()
    except Exception as exc:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(exc)
        _jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the single-page frontend."""
    html_file = _static_dir / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return HTMLResponse("<h1>CV Job Matching System API</h1><p>Visit /docs for API reference.</p>")


@app.post("/search", summary="Upload CV and start job search")
async def start_search(
    cv_file: UploadFile = File(..., description="PDF or plain-text CV file"),
    candidate_name: str = Form(..., description="Candidate's full name"),
    location: str = Form(..., description="Preferred job location, e.g. 'Dublin, Ireland'"),
):
    """
    Upload a CV and start an async job search.
    Returns a `job_id` — poll `/status/{job_id}` until done, then fetch `/report/{job_id}`.
    """
    if not os.getenv("GROQ_API_KEY") or not os.getenv("SERPER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="Server is missing API keys. Contact the administrator.",
        )

    raw = await cv_file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CV file must be under 5 MB.")

    cv_content = _read_cv_bytes(raw, cv_file.filename or "cv.pdf")
    if not cv_content:
        raise HTTPException(status_code=422, detail="Could not extract text from the CV file.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "candidate_name": candidate_name,
        "location": location,
        "created_at": datetime.utcnow().isoformat(),
        "report": None,
        "error": None,
    }

    thread = threading.Thread(
        target=_run_crew_async,
        args=(job_id, candidate_name, location, cv_content),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "queued", "message": "Job search started. Poll /status/{job_id} for updates."}


@app.get("/status/{job_id}", summary="Check job search status")
async def get_status(job_id: str):
    """Returns status: queued | running | done | error"""
    job = _get_job(job_id)
    return {
        "job_id": job_id,
        "status": job["status"],
        "candidate_name": job["candidate_name"],
        "location": job["location"],
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
    }


@app.get("/report/{job_id}", summary="Get completed job search report")
async def get_report(job_id: str, format: str = "json"):
    """
    Retrieve the completed report. Use `?format=markdown` to get raw markdown text.
    Only available when status is `done`.
    """
    job = _get_job(job_id)
    if job["status"] != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Report not ready yet. Current status: {job['status']}",
        )

    if format == "markdown":
        return HTMLResponse(
            content=job["report"],
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="job_report_{job_id[:8]}.md"'},
        )

    return {
        "job_id": job_id,
        "candidate_name": job["candidate_name"],
        "location": job["location"],
        "report_markdown": job["report"],
        "finished_at": job.get("finished_at"),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "jobs_in_memory": len(_jobs)}


def serve():
    """Entry point for `uv run serve` / pyproject script."""
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("cv_job_matching_system.api:app", host="0.0.0.0", port=port, reload=False)
