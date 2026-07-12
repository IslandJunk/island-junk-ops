# Deploying Island Junk Ops to Render

The single milestone that needs a public URL: **Twilio inbound replies + the manager nudge**
(Twilio POSTs to `https://<app>/sms/inbound`, which can't work locally). Outbound texts already
work without a deploy. Everything below is a one-time setup; after that, pushes to `main` redeploy.

The repo now carries the deploy artifacts: **`render.yaml`** (web service), **`.python-version`**
(3.13), and a **`DATABASE_URL` scheme fix** so Render's raw Postgres URL doesn't crash the boot.

> **The database already exists, is migrated (Alembic head `cdecca6a35e4`), and is seeded.** Do
> **not** create a new one. We point the service at the existing DB. Nothing here wipes data.

---

## 0. Prerequisites (you have these)
- A Render account with the existing **Island Junk Postgres** instance.
- Your Twilio creds (Account SID, Auth Token) + the updates line `+17789065865`.
- The Google service-account JSON (locally at `spike/service-account-key.json`, git-ignored).

---

## 1. Create the web service from the Blueprint
1. Render dashboard → **New → Blueprint**.
2. Connect this GitHub repo, branch **`main`**. Render reads `render.yaml` and proposes the
   **island-junk-ops** web service (no database — correct; we reuse the existing one).
3. Click **Apply**. It will stop and ask for the `sync: false` env vars — fill them in step 2.

*(Manual alternative: New → Web Service → this repo, then set Build `pip install -r requirements.txt`,
Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Health check `/health`, and the env vars below.)*

---

## 2. Environment variables (dashboard → the service → Environment)

| Key | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://…` | From the existing DB's **Connection** page. See §2a. |
| `SESSION_SECRET` | *(auto)* | `render.yaml` generates a strong one — leave it. |
| `ENVIRONMENT` | `production` | already set by the blueprint |
| `PYTHON_VERSION` | `3.13` | already set by the blueprint |
| `TWILIO_ACCOUNT_SID` | your SID | |
| `TWILIO_AUTH_TOKEN` | your token | rotate it afterward (§6) |
| `TWILIO_UPDATES_LINE` | `+17789065865` | |
| `TWILIO_VALIDATE_SIGNATURES` | `false` | flip to `true` in §5, step 3 |

**Square / Dropbox** come later (NEXT items 2–3) — add `SQUARE_ACCESS_TOKEN`,
`SQUARE_LOCATION_ID`, `SQUARE_ENVIRONMENT=production`, `DROPBOX_ACCESS_TOKEN` when you wire those.

### 2a. Getting `DATABASE_URL` right (the one gotcha)
Render's DB page shows an **Internal** and an **External** URL, both starting `postgresql://`.
- The code auto-rewrites the scheme to `postgresql+psycopg://`, so you can paste **either** form
  as-is and it will boot. (You may also paste the `+psycopg` form manually — also fine.)
- Prefer the **Internal Database URL** (same-region, faster, no egress). Use **External** only if
  the service and DB are in different regions.

---

## 3. (Migrations) — nothing to do on the first deploy
The DB is already at head, so the first deploy applies no migrations.
- **Starter+ plan:** `preDeployCommand` in `render.yaml` auto-runs `alembic upgrade head` on every
  future deploy — you're done.
- **Free plan:** `preDeployCommand` is ignored. After you ship a *new* migration, open the service's
  **Shell** and run `alembic -c alembic.ini upgrade head` once.

---

## 4. Google service-account key (Secret File) — required for the calendar
The day-board (read) and booking (write) need the service-account JSON, which is git-ignored and
**not in the repo**. Add it as a Render **Secret File**:
1. Service → **Environment → Secret Files → Add Secret File**.
2. **Filename / path:** `spike/service-account-key.json` (must match — the app reads this path).
3. **Contents:** paste the JSON from your local `spike/service-account-key.json`.

*(The calendar guard is unchanged: the app still writes only to the TEST / reminder / punch
calendars and hard-refuses the two live dispatch calendars.)*

---

## 5. Deploy, then wire Twilio inbound
1. Trigger the deploy. Watch logs for `Application startup complete`. Then verify:
   ```
   curl https://<app>.onrender.com/health
   # {"status":"ok","db_configured":true,...}
   ```
   Log in at `https://<app>.onrender.com/app` (Manager / 1111) and confirm the day-board loads
   real calendar data (proves the Secret File + DATABASE_URL are good).
2. **Twilio console → Phone Numbers → the updates line → Messaging:** set **"A message comes in"**
   to **Webhook**, `POST https://<app>.onrender.com/sms/inbound`. Save.
3. Text the updates line from your phone → you should get the "unmonitored line" auto-reply, **and**
   the manager phone should get the nudge (who + address). Then set
   `TWILIO_VALIDATE_SIGNATURES=true` and redeploy (now the public URL is known, signatures validate).

---

## 6. Housekeeping
- **Rotate the Twilio Auth Token** (it passed through chat once): Twilio console → regenerate →
  update `TWILIO_AUTH_TOKEN` in Render → redeploy.
- **Auto-deploy:** on by default (push to `main` redeploys). Toggle under Settings if you want manual.
- **Rollback:** Render → the service → **Events/Deploys → Rollback** to a prior deploy.

---

## Quick reference
| Thing | Value |
|---|---|
| Build | `pip install -r requirements.txt` |
| Pre-deploy (Starter+) | `alembic -c alembic.ini upgrade head` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Python | `3.13` (`.python-version` / `PYTHON_VERSION`) |
| Inbound webhook | `POST https://<app>/sms/inbound` |
| Alembic head | `cdecca6a35e4` |
