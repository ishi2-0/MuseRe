"""FastAPI app: serves the web app and the processing API."""
import os
import shutil
import tempfile
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import pipeline

app = FastAPI(title="Reel to Trumpet")
executor = ThreadPoolExecutor(max_workers=1)  # one at a time keeps memory low
jobs: dict = {}
STATIC = os.path.join(os.path.dirname(__file__), "static")


def run_job(job_id: str, kind: str, payload: str):
    work = tempfile.mkdtemp(prefix="r2t_")
    try:
        jobs[job_id]["status"] = "processing"
        if kind == "url":
            result = pipeline.process_url(payload, work)
        else:
            result = pipeline.process_upload(payload, work)
        jobs[job_id].update(status="done", result=result)
    except Exception as exc:  # report a friendly message to the app
        traceback.print_exc()
        msg = str(exc) or exc.__class__.__name__
        if "login" in msg.lower() or "private" in msg.lower():
            msg = "Instagram wouldn't let me read that reel (private or login needed)."
        jobs[job_id].update(status="error", error=msg[:300])
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if kind == "upload":
            shutil.rmtree(os.path.dirname(payload), ignore_errors=True)


@app.post("/api/jobs")
async def create_job(url: str = Form(None), file: UploadFile = File(None)):
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {"status": "queued"}
    if file is not None and file.filename:
        d = tempfile.mkdtemp(prefix="r2t_up_")
        path = os.path.join(d, "video" + os.path.splitext(file.filename)[1])
        with open(path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        executor.submit(run_job, job_id, "upload", path)
    elif url:
        found = pipeline.find_instagram_url(url)
        if not found:
            raise HTTPException(400, "That doesn't look like an Instagram reel link.")
        executor.submit(run_job, job_id, "url", found)
    else:
        raise HTTPException(400, "Send a reel link or a video file.")
    return {"id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job")
    return job


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


app.mount("/", StaticFiles(directory=STATIC), name="static")
