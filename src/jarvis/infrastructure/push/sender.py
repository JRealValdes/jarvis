"""Send push notifications to registered devices.

Delivery uses Firebase Cloud Messaging when ``FCM_SERVER_KEY`` (legacy HTTP)
or credentials path env is configured. Without credentials, sends are logged
and reported as not delivered so local/dev setups stay quiet.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from jarvis.infrastructure.persistence.devices.repository import list_tokens_for_user

logger = logging.getLogger(__name__)

FCM_LEGACY_URL = "https://fcm.googleapis.com/fcm/send"


def _fcm_server_key() -> str | None:
    """Return the legacy FCM server key from the environment, if set."""
    key = (os.environ.get("FCM_SERVER_KEY") or "").strip()
    return key or None


def send_push_to_user(
    *,
    owner_real_name: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> bool:
    """
    Send a data+notification push to all of the user's registered devices.

    Args:
        owner_real_name: Target user.
        title: Notification title.
        body: Notification body.
        data: Optional string data payload (deep-link fields).

    Returns:
        True if at least one delivery attempt succeeded.
    """
    tokens = list_tokens_for_user(owner_real_name)
    if not tokens:
        logger.info("No device tokens for %s; skip push", owner_real_name)
        return False
    server_key = _fcm_server_key()
    if not server_key:
        logger.info(
            "FCM_SERVER_KEY unset; would push to %s device(s) for %s: %s — %s",
            len(tokens),
            owner_real_name,
            title,
            body,
        )
        return False
    payload_data = {str(k): str(v) for k, v in (data or {}).items()}
    any_ok = False
    for record in tokens:
        ok = _send_fcm_legacy(
            server_key=server_key,
            token=record.token,
            title=title,
            body=body,
            data=payload_data,
        )
        any_ok = any_ok or ok
    return any_ok


def _send_fcm_legacy(
    *,
    server_key: str,
    token: str,
    title: str,
    body: str,
    data: dict[str, str],
) -> bool:
    """
    POST one legacy FCM message.

    Args:
        server_key: FCM server key.
        token: Device registration token.
        title: Notification title.
        body: Notification body.
        data: Custom data map.

    Returns:
        True on HTTP 200 with a successful FCM result.
    """
    payload: dict[str, Any] = {
        "to": token,
        "notification": {"title": title, "body": body},
        "data": data,
        "priority": "high",
    }
    try:
        response = requests.post(
            FCM_LEGACY_URL,
            headers={
                "Authorization": f"key={server_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
    except requests.RequestException:
        logger.exception("FCM request failed for token …%s", token[-8:])
        return False
    if response.status_code != 200:
        logger.warning(
            "FCM HTTP %s for token …%s: %s",
            response.status_code,
            token[-8:],
            response.text[:200],
        )
        return False
    try:
        body_json = response.json()
    except ValueError:
        return True
    return int(body_json.get("success") or 0) > 0


async def maybe_send_task_push(
    *,
    owner_real_name: str,
    task_id: str,
    title: str,
    summary: str,
) -> bool:
    """
    Notify the user that a periodic task run is ready to open.

    Args:
        owner_real_name: Task owner.
        task_id: Task to open on tap.
        title: Task title.
        summary: Short body text.

    Returns:
        True when at least one push was accepted by FCM.
    """
    return send_push_to_user(
        owner_real_name=owner_real_name,
        title=title,
        body=summary or "Your scheduled task finished.",
        data={
            "type": "periodic_task",
            "task_id": task_id,
        },
    )


async def maybe_send_job_push(
    *,
    owner_real_name: str,
    job_id: str,
    title: str,
    body: str,
) -> bool:
    """
    Notify the user that an async chat job completed.

    Args:
        owner_real_name: Job owner.
        job_id: Completed job id.
        title: Notification title.
        body: Notification body.

    Returns:
        True when at least one push was accepted by FCM.
    """
    return send_push_to_user(
        owner_real_name=owner_real_name,
        title=title,
        body=body,
        data={
            "type": "chat_job",
            "job_id": job_id,
        },
    )
