"""Google Docs tool: append content to an existing document."""

from __future__ import annotations

import logging

from auth import docs_service

logger = logging.getLogger(__name__)


def append_to_doc(doc_id: str, content: str) -> dict:
    """Append ``content`` as a new paragraph at the end of the Google Doc.

    Returns a small summary dict with the doc id and the appended text.
    """
    service = docs_service()

    doc = service.documents().get(documentId=doc_id).execute()
    end_index = doc.get("body", {}).get("content", [])[-1]["endIndex"]

    requests = [
        {
            "insertText": {
                "location": {"index": end_index - 1},
                "text": content,
            }
        }
    ]
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    logger.info("appended content to doc %s", doc_id)
    return {"doc_id": doc_id, "appended": content}