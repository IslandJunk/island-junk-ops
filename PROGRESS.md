# Island Junk — Build Progress & Handoff

**2026-07-12 (bin payments + calendar build STARTED)** — Wes approved a **4-workstream build** (spec:
`docs/bin-payments-and-calendar-plan.md`) that reverses three guardrails *deliberately* (auto-paint status
colours on the app's own calendar — never live; owner-pressed card charging via Square tokens; live
read-only QuickBooks sync). Decisions locked: two calendar events per bin rental (drop + pickup, invoiced
once after pickup), reference-code QB matching, customer-level saved card, **owner-only** charge, pre-auth
rejected (auth expiry) in favour of card-on-file. **Shipped so far:** WS1 — Owner-Hub **"Bins awaiting
payment"** queue + **"Received as e-transfer"** close-out (`owner-hub-bridge.js`, uses existing
`/reminders` endpoints); WS2 — **auto-paint core** (`gcal.recolor_event` TEST-calendar-only +
`app/dispatch/paint.py`; done→Basil, awaiting→Tomato; owner close-out colours never auto-painted; verified
against the real TEST calendar). **NOT yet wired:** the crew-completion trigger that calls `paint_job_status`
(next step). **Still to build:** WS1 two-event link + `BIN-xxxx` reference code; WS3 card-on-file (needs a
Square **sandbox** app-id + token from Wes); WS4 QuickBooks sync (needs a QB **sandbox** + developer app).
No new migration yet (kept to the live prod DB's existing schema). Make.com stays off.

**2026-07-12 (LIVE on Render)** — **Deployed to production.** App is live at
**`https://island-junk-ops.onrender.com`** (Blueprint `render.yaml`, Starter plan, Python 3.13, GitHub repo
`IslandJunk/island-junk-ops`). Verified in prod: `/health`, PIN login (DB+auth), day-board reads the TEST calendar
(Google key via a Render **Secret File** at `/etc/secrets/service_account_key.json`), and — the point of deploying —
**inbound SMS is now live**: a real text to the updates line routed through `/sms/inbound` → auto-reply + manager nudge,
all confirmed in the live log. **`TWILIO_VALIDATE_SIGNATURES=true`** is on and validated (signed request accepted).
Deploy-prep fixes this session: psycopg scheme normalization in both the app engine and alembic `env.py`; Google key path
via `GOOGLE_SERVICE_ACCOUNT_FILE`; and Twilio signature validation reconstructs the **public** URL behind Render's proxy
(`_public_url`). Secrets live in the Render dashboard (git-ignored `.env` is local-only). Runbook: **`DEPLOY.md`**.

**2026-07-12 (later)** — Wired the last two **deferred customer-facing SMS triggers** (§10, spec §2): the residential
**completion text** (crew sends price + GST + e-transfer from the calc's e-Transfer modal, with a confirm-number input →
unique customer-name fallback) and the **next-customer ETA** (crew marks a stop done on the day-board and texts the *next*
stop their crew-entered arrival estimate — never raw map distance). Two new crew-accessible endpoints (`POST /sms/completion`,
`POST /sms/eta`) compose server-side from the locked templates (brand-named, no card numbers); two additive bridges add the
buttons to the approved screens. Verified end-to-end (resolver, both template paths, both endpoints, opt-out safety gate,
no-phone/last-stop guards) with **zero real texts** (opt-out short-circuit). Alembic head unchanged (no new migration).

**2026-07-12 (earlier)** — Went **live on Twilio** (Wes's creds in `.env`, Full account, updates line 778-906-5865): outbound texts
**delivered end-to-end**. Built the **manager-reply nudge** (forwards a customer reply to the manager's phone *with* name +
address — the "who's it from?" fix), made all **message wording owner-editable** in the Owner Hub, and shipped the full
**follow-up-review send system** (real Victoria Google link, two-level dedup, manager board res + commercial, crew job-end
button). Earlier in the arc: global **brand-switching** (Nanaimo keystone), **punch-time calendar mirror**, trucks/colour-map
editing, the rest of field/dispatch + operational-tail persistence, and all three integrations scaffolded creds-gated.

**Stack:** FastAPI + SQLAlchemy 2 + Alembic + Postgres (Render, via `.env`). Python **3.14**. Serves the approved
`/prototypes` HTML **untouched** — real DB data injected inline as `localStorage` in `<head>` before the page's scripts,
and per-screen **bridges** (appended before `</body>`) swap `localStorage` writes for API calls. Deploy target: **Render**.

**Repo state:** clean tree, HEAD `618fe77`, Alembic head **`cdecca6a35e4`** (19 migrations; they live under
`migrations/versions/`, NOT `alembic/versions/`). 12 routers, 34 synced keys. Login: **Manager / PIN 1111** or
**Wes (owner) / PIN 4321**. Preview server: `.claude/launch.json` (name `api`) runs plain uvicorn with **no `--reload`** →
restart it after any Python edit. Owner Hub has a *second* gate (owner password + sim 2FA) — the prototype's own demo;
call `unlock()` to skip in browser tests.

Authoritative reference docs (a spec wins where it goes deeper): `CLAUDE.md`, `island-junk-SPEC-scheduling-and-dispatch.md`,
`island-junk-SPEC-login-sessions-and-access.md`, `island-junk-SPEC-sms-and-texting.md`, `docs/data-model.md`,
`island-junk-CURRENT-VERSIONS.md`.

---

## 1. DONE (whole build — all verified against the live Render DB)

**Foundation**
- Calendar **stack-order spike proven** (`orderBy=startTime` = the manual top-to-bottom stack). Brand-tagged base/mixins,
  config, **PIN auth + owner-only guard** at the logic layer. ORM registry via `app.models.all`.
- Schema: **~40 tables, 19 migrations.** Seeded: 75-bin fleet, 15-person roster (PINs `0000`), Victoria rate card, trucks
  #3–7, colour map + colour→truck, disposal facilities/materials + rate history, area surcharges.
- **Refs → DB** (`app/web/refs.py`): every `ij_*` key a screen reads is injected from Postgres, `None`-until-data (screen
  keeps its demo until real rows exist). **Sync → DB** (`app/web/sync_handlers.py` + `sync-bridge.js` whitelist, 34 keys):
  every user write persists via `POST /sync`.

**Booking / dispatch**
- **Booking** — `POST /booking` writes the Job + **ONE Sage event to the TEST calendar** (guard-enforced). 7 lanes wired
  (`booking-bridge.js`); reads the saved rate sheet. Auto-sends a booking-confirm SMS (best-effort).
- **Day-Board reader** — `GET /day-board`: drops `#` manager notes → colour→truck → stack order = route order → headline
  time. Enriches each stop from the linked Job (incl. `customer_phone` for the on-our-way text).

**Persistence (all localStorage tools now back to Postgres)**
- **Bin-tracker driver tool** — reads the real 75-bin fleet (`ij_bins_full_v1`) instead of in-memory `seed()`; every action
  (drop/pick/return/weigh/mark-fixed) persists via `apply_bins`. Driver day/weights/gear (`bin_driver_day`, `bin_weigh`,
  `tool_daily_log`).
- **Day-board overlays** (`dayboard_overlay`, atomic `ON CONFLICT`), **attendance/breaks**, **day-notes**, **brand
  settings** KV, **hands-on pre-check**, **crew checklist templates**, **PM PO#s**, **reviews**, **consumables usage**,
  **trucks** (`apply_fleet`) + **colour→truck map** (`apply_colourmap`, status/sage colours protected — Make.com).
- Crew/yard/owner day: bins, roster (owner-guarded), incidents, clock in/out, field-jobs, yard weigh + rich yard-processing
  record (waste class, %/gross/tare/net, dump fee → margin). Maintenance doc, defect flags, reminders.

**Owner tools**
- **Ready-to-invoice queue** (`GET /invoice-queue`): commercial field-jobs + processed bins (with disposal margin) +
  overdue roll-offs. **Never invoices/charges.** Owner-hub sheet has a **48-hour CC-charge clock** button + **Square
  payment-link** button per item.
- **CC-charge reminder** (§9/§11): `POST /reminders/cc-charge`, 48h = 2 working days (skips weekends + BC stats). Off-board
  "CC Charge Reminders" calendar is LIVE (Flamingo → purple on paid).
- **Disposal cost model** (`compute_load_margin`, `GET /disposal/margins`). **QuickBooks import** (§13): 2,173 residential
  + 824 company imported. **Rate-sheet write-back** cluster (rates, facilities/materials, surcharges, custom customers).

**Global brand-switching (Nanaimo keystone, §3)** — owner-hub Victoria↔Nanaimo switch is now global. `POST /auth/brand`
sets `session.active_brand`; serving + owner reads resolve it via `app.api.deps.active_brand_for`. **Never-mix (§15):**
pages stamped `window.__IJ_BRAND`; sync writes the page's brand for the owner, **hard-forces crew to their own brand**.
Verified reversible + isolated. Unblocks Nanaimo setup via the existing screens (no new UI).

**Calendars (all off-board / TEST — never a live dispatch calendar)** — booking→TEST cal; CC-charge→reminder cal;
**punch-time mirror** (`apply_clock` → one event per person per day, clock-in→out, on the shared "PUNCH TIME - TEST" cal).
Three isolated writable targets, each guard refuses the other two + the live IDs.

**Integrations** (`app/integrations/`, `app/sms/`) — creds-gated (dry-run until `.env` creds):
- **Twilio SMS — LIVE (outbound).** One send-only updates line 778-906-5865 (both brands); **never sends from a MAIN line**
  (guard). Outbound: booking-confirm, on-our-way, next-ETA, reminder, completion, **review** — each brand-named, no card
  numbers. **Wording is owner-editable** in the Owner Hub (`ij_owner_cfg_v1.templates`, persisted per brand; `templates.py::render`
  uses it, else built-in). Inbound reply routing (STOP/HELP first, then "unmonitored line → right main line") + the
  **manager nudge** (reply forwarded to the manager with name/address). Endpoints `/sms/inbound|send|status|log`.
- **Follow-up reviews — full send system (§11).** `POST /reviews/send` (real Victoria link `g.page/r/CYpCB7lEXE6yEAE/review`)
  with **two-level dedup** (this record + this phone within 60 days). Phone resolved by unique customer-name match.
  Manager board send button (`manager-hub-bridge.js`, res + commercial — commercial jobs spawn review records) + crew
  job-end button (`residential-calculator-bridge.js`). `GET /reviews` = the board.
- **Square** — `POST /square/payment-link` (payment LINK only, **no charge call exists**). **Dropbox** — `POST /dropbox/job-photo`
  (files under the TEST root only; guard refuses outside paths). Both dry-run until creds.

---

## 2. IN FLIGHT (nothing broken — these are the exact open loops)

- **Twilio inbound is LIVE** (2026-07-12) — deployed; the Messaging webhook points at
  `POST https://island-junk-ops.onrender.com/sms/inbound` and `TWILIO_VALIDATE_SIGNATURES=true` is on + validated. Reply
  routing + manager nudge confirmed against the live log.
- **Square is LIVE** (2026-07-12) — creds set in the Render dashboard; `GET /square/status` = live (production) and a real
  payment link was created end-to-end (`https://square.link/...`). Owner-hub invoice-queue buttons now make real links.
  Still no charge call (guardrail) — links only.
- **Dropbox** — fully built (`app/integrations/dropbox_files.py`), still dry-run. What's left: add `DROPBOX_ACCESS_TOKEN`
  in the Render dashboard (§3) + decide the photo source — no code.
- **Client SMS triggers — completion + next-ETA now WIRED** (`POST /sms/completion`, `POST /sms/eta`, both crew-accessible,
  server-composed from the locked templates). Completion: the calc's e-Transfer modal gets a confirm-number input (blank →
  unique customer-name match) + send button (`residential-calculator-bridge.js`). Next-ETA: the day-board job sheet gets a
  "Text next stop your ETA" affordance under the on-our-way button — finds the next phoned stop in the same truck/day, takes
  a crew-entered time, sends (`day-board-bridge.js`). **Still deferred:** the completion **photo attachment** (endpoint takes
  `media_url` but no hosted photo URL exists yet) + **Dropbox photo filing** — both blocked on a real photo source (§8 photos
  arrive at booking; needs Dropbox creds to host an MMS-able URL).
- **Nanaimo review link** — `app/sms/templates.py::_REVIEW_LINK[Brand.nanaimo]` is `""`; set when Nanaimo is built.

---

## 3. NEXT (in order)

1. ~~**Deploy to Render**~~ — **DONE** (2026-07-12). Live at `https://island-junk-ops.onrender.com`; Twilio inbound +
   manager nudge on and secured. See the top-of-file entry + `DEPLOY.md`. Env/secrets are set in the Render dashboard.
2. ~~**Square creds**~~ — **DONE** (2026-07-12). `SQUARE_ACCESS_TOKEN` / `SQUARE_LOCATION_ID` / `SQUARE_ENVIRONMENT=production`
   set in the Render dashboard; `/square/status` = live, real payment link verified.
3. **Dropbox creds** → Render Environment tab: `DROPBOX_ACCESS_TOKEN` (keep `DROPBOX_ROOT=/Island Junk TEST` until go-live).
   Then decide the real **photo source** (§8: customer photos at booking) and wire the crew forms → `/dropbox/job-photo`.
4. ~~**Wire the deferred SMS triggers** (completion text + next-ETA)~~ — **DONE** (2026-07-12, phone-flow = confirm-number
   step with a unique-name fallback). Remaining SMS work is the completion **photo attachment**, which waits on Dropbox (step 3)
   to host an MMS-able URL for the job photo.
5. **Nanaimo review link + workspace data** — set the Nanaimo Google review link; when starting Nanaimo, drive setup through
   the existing screens (brand-switch → rate-sheet "Copy Victoria", employees, bins, colour map, customer import) + stand up
   its calendar/Twilio/Dropbox/Square.

**Rotate the Twilio Auth Token** when convenient (it passed through chat): Twilio console → regenerate → swap `.env`.

---

## 4. OPEN DECISIONS (waiting on Wes — context in `docs/data-model.md`)

- **Colour semantics that touch Make.com (HIGH-STAKES).** Make reads job-status colour off the live ISLAND JUNK VICTORIA
  calendar and fires ad-conversion signals, so these must be exact. Proposed in `docs/data-model.md` (2026-07-09), **confirm
  before go-live:** **Flamingo(4) = STATUS only** (residential unpaid — CC *or* e-transfer; never a truck), and the **bin
  truck = Graphite/Blueberry** (Lavender stays a free *assignable* colour, NOT the bin truck). `apply_colourmap` already
  refuses to touch status/sage colours — but confirm the assignments themselves.
- **7 booking lanes vs the brief's 5 types.** Modeled as `booking_lane` (collect/invoiced/bins/pm/contracts/custom/pallet)
  + `account_type` + bin `action`; §7's flat 5-value `type` was retired. Confirm this taxonomy is intended.
- **Real crew PINs** — all seeded `0000`; owner must set real per-person PINs before crew can log in.
- **Punch calendar** — chose **per-day** (one event per person per day) over per-punch; confirm. Nanaimo punch calendar TBD.
- **Manager-nudge target** — Wes chose the **main line** (778-966-5865); this is already the default (no `.env` override).
- **Yard waste-class picker** — deferred: `WASTE_CLASSES` wording differs from `disposal_material.m` ("Rubble" vs "Rubble
  (brick/tile/mortar)"), so a naive merge dupes. Needs a `headline_class` flag + Wes confirming the pickable set + wording.
- **Two empty waste-class prices** (`Mixed drywall (≥31%)`, `Concrete/clay tile`) + possible **yard-waste `min $24` row** —
  fill in the rate sheet when Wes confirms.
- **QuickBooks export** — his export had **no Company column** (handled by name-shape inference); a re-export *with* it gives
  an authoritative split. **Mixed-load wood default** is clean $80 — flip to $110 in the rate sheet if usually treated.
- **Bin truck real dispatch number/label** — prototype's "12" is demo (maintenance seed says "Bin truck (Hino) · #12").
- **June-2026 expanded palette** — classic palette has only 3 hand-load colours, so only 3 of trucks #3–7 colour distinctly;
  the full 24-colour set is needed to colour all five.

---

## 5. GOTCHAS (don't forget)

- **The "#" rule (STANDING RULE, scheduling spec §4):** a **leading `#` in a Google Calendar event title = a manager-only
  note the app ignores completely** — not a job, not dispatch. The day-board reader drops these
  (`app/dispatch/calendar_read.py::is_manager_note`). **Build this into EVERY future calendar reader.** (Open: the spec's
  `#3 truck` example reads like a typo for `Truck #3`; we implemented the plain leading-`#` = note rule — confirm.)
- **Calendar guard (NEVER weaken):** `app/integrations/gcal.py` hard-refuses the two live IDs `LIVE_VICTORIA`,
  `LIVE_JOBS2` + `primary`. Three writable targets (TEST/reminder/punch); each `_assert_*_calendar` allows ONLY its own and
  refuses the others. Every calendar test creates a **real** event — delete it by id afterward.
- **Brand resolution — NEVER write `emp.brand or Brand.victoria` again.** Reads/actions: `active_brand_for(request, emp)`;
  served pages: `optional_brand(request, db)`; **writes (sync) use the PAGE's brand** (`window.__IJ_BRAND`), and sync
  **hard-forces crew to `emp.brand`**. New owner endpoints thread `request` + use `active_brand_for`. (day-board + booking
  still on the old path — calendar-bound, intentionally deferred.)
- **`ij_bins_v1` served in TWO shapes on purpose.** `build_bins_v1` = lean `state` shape (registry + yard read/write, don't
  change). `build_bins_full_v1` → `ij_bins_full_v1` = rich `status`+fields shape, bin-tracker only (inject-only, not synced).
  `apply_bins` accepts BOTH, **present-key-only** (a lean write never blanks a rich field).
- **Bridges: mutate `const`s in place** (can't reassign a top-level `const`, but `.push`/`.length`/props work) — **BUT a
  top-level `let`/`function` you CAN reassign** from a later appended classic script (shared global lexical env; e.g.
  `bin-tracker-bridge.js` reassigns `let bins` + wraps `render()`). Only works on classic, sloppy-mode scripts (no
  `type="module"`, no `use strict`).
- **Demo-seed suppression:** some prototypes WRITE their seed to localStorage on render (`revList()`, `poSeed()`). Builders
  that return `[]`-when-empty suppress it (reviews/usage); `ij_po_needed_v1` needs the injected `ij_po_seeded_v1="1"` flag.
- **`_serve_prototype` injects before the LAST `</body>`** (some prototypes embed `</body>` in JS template strings; a
  replace-all breaks that script). `</head>` uses the FIRST match.
- **Alembic + shared `brand` enum:** autogenerate emits inline `sa.Enum('victoria','nanaimo', name='brand')` in every new
  table — hand-edit to a module-level `brand_enum = postgresql.ENUM(..., name='brand', create_type=False)` and add
  `from sqlalchemy.dialects import postgresql` if the file lacks it (column-only migrations don't import it).
- **Owner is `brand=NULL`** (shared) — brand-scoped employee lookups MUST include brand-null (`or_(brand==b, brand.is_(None))`).
- **Python 3.14:** plain `uvicorn` (not `[standard]`), `psycopg[binary]`, `pbkdf2_sha256` (not bcrypt), `tzdata`, `openpyxl`,
  `twilio>=9` (lazy-imported — only needed once creds are set). All in `requirements.txt`.
- **`.env` keys** (git-ignored, UPPERCASE to match): `DATABASE_URL`, `SESSION_SECRET`, `TWILIO_ACCOUNT_SID`,
  `TWILIO_AUTH_TOKEN`, `TWILIO_UPDATES_LINE` (set). Not yet set: `SQUARE_ACCESS_TOKEN`, `SQUARE_LOCATION_ID`,
  `DROPBOX_ACCESS_TOKEN`, `TWILIO_VALIDATE_SIGNATURES`, `MANAGER_NOTIFY_*`.
- **Windows console renders `—`/`·`/`≥` as `�`** in Bash output (DB stores correct UTF-8) — prefix Python one-liners with
  `PYTHONIOENCODING=utf-8` when printing those.
- **PII stays out of git:** `.gitignore` excludes `.env`, `**/service-account-key.json`, `**/.venv/`, `spike/out/`, and
  customer exports (`*Customers*.xlsx` / `*.csv`).

---

## 6. HOW TO RESUME

**Prereqs (in place):** `.env` (Render `DATABASE_URL` + `SESSION_SECRET` + Twilio creds), `spike/service-account-key.json`
(Google creds). The Render DB is already migrated + seeded — steps 3–4 are only for a fresh DB.

```bash
# from repo root (Windows paths; .venv already exists)
.venv/Scripts/python.exe -m pip install -r requirements.txt          # 1. deps (incl. twilio, openpyxl)
.venv/Scripts/python.exe -c "import app.main; print('imports OK')"    # 2. sanity
.venv/Scripts/alembic.exe -c alembic.ini upgrade head                # 3. migrate (head = cdecca6a35e4)
# 4. seed (FRESH DB ONLY, in this order — colour_trucks needs trucks+colours):
.venv/Scripts/python.exe -m scripts.seed_owner
.venv/Scripts/python.exe -m scripts.seed_crew
.venv/Scripts/python.exe -m scripts.seed_trucks
.venv/Scripts/python.exe -m scripts.seed_bins
.venv/Scripts/python.exe -m scripts.seed_rates
.venv/Scripts/python.exe -m scripts.seed_colours
.venv/Scripts/python.exe -m scripts.seed_colour_trucks
.venv/Scripts/python.exe -m scripts.seed_disposal
.venv/Scripts/python.exe -m scripts.seed_surcharges
# (customers are imported, not seeded: python -m scripts.import_customers "Victoria Customers.xlsx" --apply)
# 5. run
.venv/Scripts/python.exe -m uvicorn app.main:app                     # http://127.0.0.1:8000/app · /health
```

Login: **Manager / 1111** or **Wes (owner) / 4321**. In browser tests the owner-hub's second gate is skippable via
`unlock()`; prefer the API for auth (`POST /auth/login {pin, brand}` sets the cookie). Preview server: `preview_start`
(name `api`) — restart it after any Python edit (no `--reload`).

**Safety confirmed this session:** `app/integrations/gcal.py` still hard-refuses the two live calendar IDs (`LIVE_VICTORIA`,
`LIVE_JOBS2`) + `primary` and writes ONLY to the configured TEST / reminder / punch calendars; `.gitignore` still protects
`.env`, `spike/service-account-key.json`, and customer PII exports (verified they are ignored).
