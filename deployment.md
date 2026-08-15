# Deploy to Render

Deploy the Google MCP Server (FastAPI + Google Docs/Gmail tools) as a Render
**Web Service**. Because this app is interactive (OAuth browser login + a
terminal `Approve? (y/n)` gate), two things need special care on a cloud host:

1. `credentials.json` / `token.json` are **files**, not environment variables.
2. The approval prompt needs a **terminal** — `input()` blocks until someone
   answers, and there is no human at a hosted server's keyboard.

> If you only need the tool endpoints reachable, read the **Workaround** in
> `server.py` notes below before exposing this publicly.

---

## 1. Prepare the code for Render

### A. Load credentials from an environment variable (recommended)

Render has no built-in "secret file upload" for arbitrary files. Encode your
`credentials.json` as base64 and ship it through an environment variable.
Add to `auth.py`:

```python
import base64

def _creds_from_env(raw: str) -> None:
    """Decode base64-encoded credentials.json content into CREDENTIALS_FILE."""
    CREDENTIALS_FILE.write_bytes(base64.b64decode(raw))

if os.environ.get("GOOGLE_CLIENT_SECRETS_B64"):
    _creds_from_env(os.environ["GOOGLE_CLIENT_SECRETS_B64"])
```

Generate the value from your local machine:

```bash
python -c "import base64;print(base64.b64encode(open('credentials.json','rb').read()).decode())" > creds.b64
```

Then set `GOOGLE_CLIENT_SECRETS_B64` to the contents of `creds.b64` in the
Render dashboard (see §3). Never commit `creds.b64`.

### B. Keep `token.json` on a persistent disk

Render's default disk is **ephemeral** — `token.json` written by the OAuth
flow disappears on restart/redeploy (the refresh token is only re-usable while
the file exists). Choose one:

- **Paid plan:** add a **Persistent Disk** (Render → Service → Disks), mount at
  `/var/data`, and set env `TOKEN_PATH=/var/data/token.json` + `CREDS_PATH=/var/data/credentials.json`.
- **Free/Starter:** the app will re-open the browser OAuth flow on each deploy.
  You must complete login each time via the terminal workaround below.

Add env-path support to `auth.py`:

```python
TOKEN_FILE = Path(os.environ.get("TOKEN_PATH", str(Path(__file__).parent / "token.json")))
CREDENTIALS_FILE = Path(os.environ.get("CREDS_PATH", str(Path(__file__).parent / "credentials.json")))
```

### C. Make the approval prompt non-blocking (or disable it)

On Render you can still type into the service's **Shell tab**, but consumers
hitting the HTTP endpoint can't answer `input()`. Either:

- Keep the prompt, and use the **Shell tab** to answer `y` when a request comes
  in (`Approval needed` flow) — workable for manual/testing use only.
- Add a **config flag** to skip the gate for CI/internal use:

```python
import os
APPROVAL_ENABLED = os.environ.get("MCP_APPROVAL", "1") != "0"

async def _needs_approval(action, payload):
    if not APPROVAL_ENABLED:
        return True
    ...  # existing input() path
```

> **Security:** if you disable approval, protect the service with Render's
> allowed-IPs / a reverse auth proxy. The endpoints write to a real Google
> account.

---

## 2. Files that must NOT be in the repo

`.gitignore` already excludes them — keep it that way:

```text
credentials.json
token.json
creds.b64
.venv/
__pycache__/
```

---

## 3. Create the Web Service (dashboard)

1. **Render Dashboard → New → Web Service**, connect your repo.
2. Settings:
   - **Root Directory:** (repo root, e.g. `google-mcp-server/` if your repo is wider)
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:**
     ```bash
     uvicorn server:app --host 0.0.0.0 --port $PORT
     ```
     (Render injects `PORT` automatically.)
   - **Instance Type:** Free/Starter (Cheap) is fine for a test MCP server.
3. **Environment Variables:**
   | Name | Value |
   |------|-------|
   | `GOOGLE_CLIENT_SECRETS_B64` | base64 of your `credentials.json` (from §1.A) |
   | `TOKEN_PATH` | `/var/data/token.json` |
   | `CREDS_PATH` | `/var/data/credentials.json` |
   | `MCP_APPROVAL` | `1` (keep approval) or `0` (disable — with IP protection) |
4. **Persistent Disk (paid plans only):** attach disk, mount path `/var/data`, size ≥ 1 GB.
5. **Deploy.**

---

## 4. Alternative: `render.yaml` blueprint (Infrastructure-as-Code)

Create `render.yaml` in the repo root:

```yaml
services:
  - type: web
    name: google-mcp-server
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: GOOGLE_CLIENT_SECRETS_B64
        sync: false               # set in dashboard after deploy
      - key: MCP_APPROVAL
        value: "1"
    disk:
      name: runtime-data
      mountPath: /var/data
      sizeGB: 1
```

It can't store file contents, so you **still set** `GOOGLE_CLIENT_SECRETS_B64`
manually in the dashboard the first time.

---

## 5. Verify

1. After deploy, open your service URL `https://<name>.onrender.com`.
2. Visit `/docs` (Swagger) to confirm the two endpoints are live.
3. Generate the token:
   ```bash
   # in the Render Shell tab (if no persistent disk file exists yet)
   python -c "from auth import authenticate; authenticate(); print('OK')"
   ```
4. Hit an endpoint once; watch logs for the approval prompt:
   ```
   INFO mcp-server: ACTION: append_to_doc
   INFO mcp-server: PAYLOAD: {"doc_id": "...", "content": "..."}
   Approve? (y/n)   # answer in the Shell tab / live logs
   ```
5. Re-deploy and confirm `token.json` still exists on `/var/data`
   (persistent disk) — otherwise you'll re-auth.

---

## 6. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `credentials.json not found.` | `GOOGLE_CLIENT_SECRETS_B64` unset or `auth.py` not updated with the env lookup. |
| `redirect_uri_mismatch` in browser | `credentials.json` is a **Desktop** OAuth client. For a hosted localhost redirect, create an **OAuth Client ID (Web application)** and add your Render callback, or keep the Desktop flow for manual shell use. |
| App hangs on `Approve? (y/n)` | No one is answering. Use the **Shell tab** to answer, or set `MCP_APPROVAL=0` (paid/IP-protected scenario). |
| Token lost after redeploy | Disk is ephemeral → add a persistent disk (§1.B) or re-run OAuth each time. |
| `PORT` not bound | Start command must use `--port $PORT`, not a hardcoded `8000`. |
| 412/403 from Docs/Gmail APIs | Google OAuth consent must include both scopes; re-consent, then check Render logs for the refresh path. |

---

## 7. Known limitation

The `input()` approval is fundamentally a **human-in-the-loop terminal**
feature. On a hosted web service it only works interactively through Render's
Shell/logs. For anything production-facing, disable the prompt (`MCP_APPROVAL=0`)
**and** put the service behind auth (Render IP Access Lists, a VPN, or a
reverse proxy with key auth). Never leave an approval-less Google-writer
endpoint public.