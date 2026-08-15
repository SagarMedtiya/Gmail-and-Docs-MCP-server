# Deploy to Render (free tier)

Deploy the Google MCP Server (FastAPI + Google Docs/Gmail tools) as a Render
**Web Service** on the **free plan**. Two things need special care on a cloud host:

1. `credentials.json` / `token.json` are **files**, not environment variables.
2. The approval prompt needs a **terminal** — `input()` blocks until someone
   answers, and there is no human at a hosted server's keyboard.

> The free plan has an **ephemeral filesystem** and **no persistent disks**, so
> both files ship as base64 **environment variables** instead.

---

## 1. Prepare the code for Render

The repo is already prepared. `auth.py` supports three env vars:

| Env var | Purpose |
|---------|---------|
| `GOOGLE_CLIENT_SECRETS_B64` | base64 of `credentials.json`, decoded on startup |
| `GOOGLE_TOKEN_B64` | base64 of `token.json`, decoded on startup (free-tier token persistence) |
| `MCP_APPROVAL` | `1` keep the human gate · `0` auto-approve (use only behind auth) |

Optional path overrides (`CREDS_PATH`, `TOKEN_PATH`) exist for paid plan with a
persistent disk; **not needed on free**.

---

## 2. Generate the secret values (on YOUR machine)

### A. base64 of `credentials.json`

```bash
python -c "import base64;print(base64.b64encode(open('credentials.json','rb').read()).decode())" > creds.b64
```

Copy the contents of `creds.b64` → this is `GOOGLE_CLIENT_SECRETS_B64`.

### B. Generate `token.json` locally (once)

```bash
python make_token.py    # opens browser; sign in, authorize Docs + Gmail (both scopes)
```

### C. base64 of `token.json`

```bash
python -c "import base64;print(base64.b64encode(open('token.json','rb').read()).decode())" > token.b64
```

Copy the contents of `token.b64` → this is `GOOGLE_TOKEN_B64`.

> The refresh token embedded in `token.json` stays valid, so Render reloads it
> from the env var on every cold start and refreshes automatically. Re-running
> OAuth is only needed if you revoke consent.

---

## 3. Files that must NOT be in the repo

`.gitignore` already excludes them — keep it that way:

```text
credentials.json
token.json
creds.b64
token.b64
.venv/
__pycache__/
```

---

## 4. Create the Web Service (dashboard)

1. **Render Dashboard → New → Web Service**, connect your **public** GitHub repo
   (free tier requires public repos).
2. Settings:
   - **Environment:** Python
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:**
     ```bash
     uvicorn server:app --host 0.0.0.0 --port $PORT
     ```
     (Render injects `PORT` automatically.)
   - **Instance Type:** Free.
3. **Environment Variables:**
   | Name | Value |
   |------|-------|
   | `GOOGLE_CLIENT_SECRETS_B64` | contents of `creds.b64` (from §2.A) |
   | `GOOGLE_TOKEN_B64` | contents of `token.b64` (from §2.C) |
   | `MCP_APPROVAL` | `1` (keep approval) or `0` (auto-approve — protect the endpoint) |
4. **Deploy.**

---

## 5. Alternative: `render.yaml` blueprint (Infrastructure-as-Code)

`render.yaml` is committed in the repo root. Use **New → Blueprint** and pick the
repo. It defines the free web service, start command, and env vars (`sync: false`
ones are set in the dashboard after the first deploy).

```yaml
services:
  - type: web
    name: google-mcp-server
    runtime: python
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn server:app --host 0.0.0.0 --port $PORT
    autoDeploy: true
    envVars:
      - key: GOOGLE_CLIENT_SECRETS_B64
        sync: false
      - key: GOOGLE_TOKEN_B64
        sync: false
      - key: MCP_APPROVAL
        value: "1"
```

---

## 6. Verify

1. Open `https://<name>.onrender.com/docs` — both endpoints should be listed.
2. (Optional) confirm the token loads: in the **Shell tab** run
   ```bash
   python -c "from auth import authenticate; authenticate(); print('OK')"
   ```
3. Hit an endpoint once; watch logs for the approval prompt:
   ```
   INFO mcp-server: ACTION: append_to_doc
   INFO mcp-server: PAYLOAD: {"doc_id": "...", "content": "..."}
   Approve? (y/n)   # answer in the Shell tab / live logs
   ```
4. Re-deploy — no re-auth needed: `GOOGLE_TOKEN_B64` is re-read on startup.

---

## 7. Free-tier behavior you should expect

- Service **sleeps after 15 minutes idle**; first request = 30–60 s cold start.
- 750 instance-hours/month, no credit card required.
- Filesystem resets on every deploy — fine, the token comes from the env var.
- Only **public** repos deploy on the free plan.

---

## 8. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `credentials.json not found.` | `GOOGLE_CLIENT_SECRETS_B64` unset or empty. |
| Token/auth hangs on startup | `GOOGLE_TOKEN_B64` unset/empty, so `authenticate()` tries the browser flow. Set the var, or run the Shell-tab OAuth command. |
| `redirect_uri_mismatch` in browser | `credentials.json` is a **Desktop** OAuth client. Locally this is fine (`run_local_server`). For hosted callback auth, create a **Web application** client instead. |
| App hangs on `Approve? (y/n)` | No one is answering. Use the **Shell tab**, or set `MCP_APPROVAL=0` + IP allow-list. |
| `PORT` not bound | Start command must use `--port $PORT`, not a hardcoded `8000`. |
| 412/403 from Docs/Gmail APIs | Re-consent both scopes locally and re-generate `token.json` (§2.B/C). |

---

## 9. Known limitation

The `input()` approval is fundamentally a **human-in-the-loop terminal**
feature. On a hosted web service it only works interactively through Render's
Shell/logs. For anything production-facing, disable the prompt (`MCP_APPROVAL=0`)
**and** put the service behind auth (Render IP Access Lists, a VPN, or a
reverse proxy with key auth). Never leave an approval-less Google-writer
endpoint public.