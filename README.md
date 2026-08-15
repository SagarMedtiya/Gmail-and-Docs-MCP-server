# Google MCP Server

FastAPI-based MCP-style server that integrates **Google Docs** and **Gmail**.
Every tool call prints its name + payload in the terminal and asks for an
explicit `y/n` approval before executing.

## Features

| Endpoint | Tool | Description |
|----------|------|-------------|
| `POST /append_to_doc` | Docs | Appends text to a Google Doc (`doc_id`, `content`) |
| `POST /create_email_draft` | Gmail | Creates a Gmail draft (`to`, `subject`, `body`) |

OAuth 2.0 scopes used:
- `https://www.googleapis.com/auth/documents`
- `https://www.googleapis.com/auth/gmail.compose`

## Prerequisites

1. Python 3.9+
2. A Google Cloud project with the **Google Docs API** and **Gmail API** enabled.
3. An OAuth 2.0 **Desktop app** client credential:
   - Google Cloud Console → APIs & Services → Credentials → **Create Credentials → OAuth client ID → Desktop app**.
   - Download the JSON and save it as `credentials.json` next to the scripts.

## Setup

```bash
cd <this-project-dir>
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

On first run, `auth.py` opens your browser for login and saves the token to
`token.json`. On later runs `token.json` is loaded directly (no browser login).
Delete `token.json` to force a fresh login.

## Run

```bash
python server.py
```

The API starts at `http://127.0.0.1:8000`.

### Example calls

```bash
curl -X POST http://127.0.0.1:8000/append_to_doc ^
  -H "Content-Type: application/json" ^
  -d "{\"doc_id\": \"<DOC_ID>\", \"content\": \"Hello from MCP server\\n\"}"

curl -X POST http://127.0.0.1:8000/create_email_draft ^
  -H "Content-Type: application/json" ^
  -d "{\"to\": \"a@example.com\", \"subject\": \"Hi\", \"body\": \"Hello!\"}"
```

Each request is only executed after you type `y` at the
`Approve? (y/n)` prompt in the server terminal.

Interactive docs: http://127.0.0.1:8000/docs

## Security notes

- `credentials.json` and `token.json` are **never committed** (see `.gitignore`).
- Every destructive/external action requires explicit human approval.
- Runs locally only (`127.0.0.1`); bind to `0.0.0.0` only behind TLS/auth.