"""Google OAuth 2.0 authentication with token persistence."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

CREDENTIALS_FILE = Path(
    os.environ.get("CREDS_PATH", str(Path(__file__).parent / "credentials.json"))
)
TOKEN_FILE = Path(
    os.environ.get("TOKEN_PATH", str(Path(__file__).parent / "token.json"))
)

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/gmail.compose",
]

# Optional: decode base64 credentials from env (Render deploys). Ignored when
# GOOGLE_CLIENT_SECRETS_B64 is unset (local dev still uses credentials.json).
_CREDS_B64 = os.environ.get("GOOGLE_CLIENT_SECRETS_B64")
if _CREDS_B64:
    CREDENTIALS_FILE.write_bytes(base64.b64decode(_CREDS_B64))

# Optional: decode base64 token from env (Render deploys). Free tier has an
# ephemeral filesystem, so token.json is shipped via GOOGLE_TOKEN_B64 instead
# of a persistent disk. Only written when the token file is missing, so local
# dev (which has a real token.json) is unaffected.
_TOKEN_B64 = os.environ.get("GOOGLE_TOKEN_B64")
if _TOKEN_B64 and not TOKEN_FILE.exists():
    TOKEN_FILE.write_bytes(base64.b64decode(_TOKEN_B64))


def _build_service(service_name: str, version: str):
    """Build an authorized Google API service client (Docs or Gmail)."""
    from googleapiclient.discovery import build

    creds = authenticate()
    return build(service_name, version, credentials=creds)


def authenticate() -> Credentials:
    """Return valid credentials, refreshing or going through OAuth as needed.

    If ``token.json`` exists it is loaded directly (no browser login).
    Otherwise it starts the installed-app OAuth flow, prompts the user in the
    browser, and saves ``token.json`` for next time.
    """
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"{CREDENTIALS_FILE} not found. "
                    "Download it from Google Cloud console (Desktop app) "
                    "and place it next to this file."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)

        TOKEN_FILE.write_text(creds.to_json())

    return creds


def docs_service():
    return _build_service("docs", "v1")


def gmail_service():
    return _build_service("gmail", "v1")


def clear_token() -> None:
    """Delete the saved token (forces fresh browser login)."""
    if TOKEN_FILE.exists():
        os.remove(TOKEN_FILE)