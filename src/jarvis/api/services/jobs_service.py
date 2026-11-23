"""Async chat job use cases."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import HTTPException

from jarvis.api.schemas.chat import AskInput
from jarvis.api.schemas.jobs import AsyncAskInput, JobAcceptedOut, JobStatusOut
from jarvis.api.services.chat_service import chat_service
from jarvis.infrastructure.persistence.jobs.repository import (
    ChatJobRecord,
    create_job,
    get_job_for_owner,
    update_job,
)
from jarvis.infrastructure.push.sender import maybe_send_job_push

logger = logging.getLogger(__name__)


def _job_out(job: ChatJobRecord) -> JobStatusOut:
    """Map a job record to the API schema."""
    response = None
    if job.response_json:
        try:
            parsed = json.loads(job.response_json)
            if isinstance(parsed, list):
                response = [str(item) for item in parsed]
        except json.JSONDecodeError:
            response = None
    return JobStatusOut(
        job_id=job.id,
        status=job.status,
        thread_id=job.thread_id,
        response=response,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
    )


class JobsService:
    """Accept async asks and expose pollable job status."""

    async def submit_ask(
        self,
        body: AsyncAskInput,
        user: dict[str, Any],
        *,
        origin: str = "",
    ) -> JobAcceptedOut:
        """
        Enqueue an async chat turn and return a job id immediately.

        Args:
            body: Ask payload.
            user: JWT claims.
            origin: Request origin for stored image URLs.

        Returns:
            Accepted job stub.

        Raises:
            HTTPException: 400 on empty turn.
            ForbiddenError: On unauthorized thread_id.
        """
        thread_id = chat_service._resolve_thread_id(  # noqa: SLF001
            body.thread_id, user, action="ask"
        )
        if not (body.message or "").strip() and not body.images:
            raise HTTPException(status_code=400, detail="Message cannot be empty.")
        job = create_job(owner_real_name=user["real_name"], thread_id=thread_id)
        ask_input = AskInput(
            message=body.message,
            images=body.images,
            model_name=body.model_name,
            thread_id=thread_id,
        )
        asyncio.create_task(
            self._run_job(job.id, ask_input, user, origin=origin),
            name=f"jarvis-chat-job-{job.id}",
        )
        return JobAcceptedOut(
            job_id=job.id, status="running", thread_id=thread_id
        )

    def get_status(self, job_id: str, user: dict[str, Any]) -> JobStatusOut:
        """
        Return job status for the owner.

        Args:
            job_id: Job id.
            user: JWT claims.

        Returns:
            Job status.

        Raises:
            HTTPException: 404 when missing.
        """
        job = get_job_for_owner(job_id, user["real_name"])
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found.")
        return _job_out(job)

    async def _run_job(
        self,
        job_id: str,
        ask_input: AskInput,
        user: dict[str, Any],
        *,
        origin: str,
    ) -> None:
        """Execute the ask and persist completion + optional push."""
        try:
            result = await chat_service.ask(ask_input, user, origin=origin)
            response = result.get("response") or []
            update_job(job_id, status="done", response=list(response))
            await maybe_send_job_push(
                owner_real_name=user["real_name"],
                job_id=job_id,
                title="Jarvis",
                body="Your reply is ready.",
            )
        except Exception as exc:
            logger.exception("Async chat job %s failed", job_id)
            update_job(
                job_id,
                status="failed",
                error=str(exc) or exc.__class__.__name__,
            )


jobs_service = JobsService()
