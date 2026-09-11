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
    job = await services.batch_service.submit(raw_audio, filename_hint=file.filename)
    # 2. fázis (skeleton): inline fut, nincs még Redis/arq queue (3. fázis, ld.
    # docs/phase1-terv.md 11. szakasz).
    await services.batch_service.run(job.job_id, raw_audio, filename_hint=file.filename)
    return JobSubmitResponse(job_id=job.job_id, status=JobStatus.QUEUED)


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
