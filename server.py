"""FastAPI MCP-style server exposing Google Docs + Gmail tools.

Every tool call first prints its name + payload in the terminal and asks
``Approve? (y/n)``; only a "y" proceeds with the action. Set the env var
``MCP_APPROVAL=0`` to disable the human gate (deployment doc §1.C).
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import docs_tool
import gmail_tool

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("mcp-server")

app = FastAPI(title="Google MCP Server", version="1.0.0")

APPROVAL_ENABLED = os.environ.get("MCP_APPROVAL", "1") != "0"


class AppendToDocRequest(BaseModel):
    doc_id: str = Field(..., description="Google Doc document id.")
    content: str = Field(..., description="Text to append to the document.")


class CreateDraftRequest(BaseModel):
    to: str = Field(..., description="Recipient email address.")
    subject: str = Field(..., description="Email subject line.")
    body: str = Field(..., description="Email body text.")


def _request_approval(action: str, payload: dict) -> bool:
    """Print action + payload, then block for a terminal (y/n) confirmation."""
    import json

    logger.info("ACTION: %s", action)
    logger.info("PAYLOAD: %s", json.dumps(payload, ensure_ascii=False))
    if not APPROVAL_ENABLED:
        logger.warning("MCP_APPROVAL=0 — auto-approving action %s", action)
        return True
    try:
        answer = input("Approve? (y/n) > ").strip().lower()
    except EOFError:
        logger.error(
            "approval prompt needs an interactive terminal (none present). "
            "Set MCP_APPROVAL=0 to auto-approve; action %s rejected.",
            action,
        )
        return False
    return answer == "y"


@app.post("/append_to_doc")
async def append_to_doc(req: AppendToDocRequest):
    payload = {"doc_id": req.doc_id, "content": req.content}
    if not _request_approval("append_to_doc", payload):
        raise HTTPException(status_code=403, detail="Action rejected by user")
    try:
        result = docs_tool.append_to_doc(req.doc_id, req.content)
    except Exception as exc:  # noqa: BLE001
        logger.exception("append_to_doc failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", **result}


@app.post("/create_email_draft")
async def create_email_draft(req: CreateDraftRequest):
    payload = {"to": req.to, "subject": req.subject, "body": req.body}
    if not _request_approval("create_email_draft", payload):
        raise HTTPException(status_code=403, detail="Action rejected by user")
    try:
        result = gmail_tool.create_email_draft(req.to, req.subject, req.body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("create_email_draft failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"status": "ok", **result}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)
    sys.exit(0)