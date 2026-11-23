"""HTTP routes for asynchronous chat jobs."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from jarvis.api.dependencies import verify_jwt_token
from jarvis.api.schemas.jobs import AsyncAskInput, JobAcceptedOut, JobStatusOut
from jarvis.api.services.jobs_service import jobs_service

router = APIRouter(tags=["jobs"])


@router.post("/ask-async", response_model=JobAcceptedOut)
async def ask_async(
    body: AsyncAskInput,
    request: Request,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> JobAcceptedOut:
    """
    Submit a chat turn that continues on the server after the client disconnects.

    Poll ``GET /jobs/{job_id}`` or wait for a push with ``type=chat_job``.
    """
    return await jobs_service.submit_ask(
        body, user, origin=str(request.base_url)
    )


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
async def get_job(
    job_id: str,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> JobStatusOut:
    """Return status (and response when done) for an owned async chat job."""
    return jobs_service.get_status(job_id, user)
