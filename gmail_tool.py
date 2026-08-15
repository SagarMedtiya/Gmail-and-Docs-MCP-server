"""Gmail tool: create a draft email."""

from __future__ import annotations

import base64
import logging
from email.message import EmailMessage

from auth import gmail_service

logger = logging.getLogger(__name__)


def _build_raw_message(to: str, subject: str, body: str) -> str:
    message = EmailMessage()
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def create_email_draft(to: str, subject: str, body: str) -> dict:
    """Create a Gmail draft and return its id + message id."""
    service = gmail_service()

    raw = _build_raw_message(to, subject, body)
    draft = (
        service.users().drafts().create(
            userId="me", body={"message": {"raw": raw}}
        ).execute()
    )

    logger.info("created draft %s to %s", draft["id"], to)
    return {
        "draft_id": draft["id"],
        "message_id": draft["message"]["id"],
        "to": to,
        "subject": subject,
    }