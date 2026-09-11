"""Batch job végpontok — docs/phase1-terv.md 9. szakasz."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile
from pydantic import BaseModel

from leiratozo.domain.models import JobStatus

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


class JobSubmitResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    error_code: str | None = None
    error_message: str | None = None


@router.post("", response_model=JobSubmitResponse, status_code=202)
async def submit_job(request: Request, file: UploadFile) -> JobSubmitResponse:
    services = request.app.state.services
    raw_audio = await file.read()
    # queue.backend szerint dönt inline (dev/teszt) vs. Redis/arq (production) között
    # — ld. api/deps.py ServiceContainer.submit_batch_job és queue/worker.py.
    job = await services.submit_batch_job(raw_audio, filename_hint=file.filename)
    return JobSubmitResponse(job_id=job.job_id, status=job.status)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(request: Request, job_id: str) -> JobStatusResponse:
    services = request.app.state.services
    try:
        job = await services.job_store.get(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found") from None
    return JobStatusResponse(
        job_id=job.job_id, status=job.status, error_code=job.error_code, error_message=job.error_message
    )


@router.get("/{job_id}/result")
async def get_job_result(request: Request, job_id: str):
    services = request.app.state.services
    document = await services.job_store.get_result(job_id)
    if document is None:
        raise HTTPException(status_code=404, detail="result not available")
    return document
