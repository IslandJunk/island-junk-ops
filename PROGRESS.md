# Island Junk — Build Progress & Handoff

**2026-07-09** — Backed the Victoria app end-to-end: FastAPI + Postgres (Render) behind the
approved prototypes, with the calendar write/read loop proven and the crew's whole day
persisting to Postgres. Schema design + open decisions live in `docs/data-model.md`; the
scheduling rules in `island-junk-SPEC-scheduling-and-dispatch.md`.

**Stack:** FastAPI + SQLAlchemy 2 + Alembic + Postgres (Render, connected via `.env`).
Python 3.14. Serves the approved `/prototypes` HTML *untouched* — real DB data is injected
inline as `localStorage` before each page's scripts run, and per-screen "bridges" swap
`localStorage` writes for API calls. Deploy target: Render.

---

## 1. DONE (whole build, verified)

- **Calendar stack-order spike PROVEN** (`/spike`) — the highest-risk unknown. `orderBy=startTime`
  recovers the manager's manual top-to-bottom stack; the `#`-note rule + headline-time parse added later.
- **Foundation** — brand-tagged base/mixins, config, PIN auth + **owner-only guard** (logic layer). Real login on Render.
- **27 tables** on Render via 8 Alembic migrations: employee, owner_security, device, auth_session,
  colour_map, truck, truck_alert_pref, residential_customer, company_customer, pm_company/group/building,
  job, bin, rate_card, area_surcharge, surcharge_waiver, contract, disposal_facility, disposal_material,
  disposal_rate_history, incident, clock_punch, field_job, weigh_log, yard_processing.
- **Real data seeded** — 75-bin fleet, 15-person roster (PINs `0000` placeholder), Victoria rate card,
  trucks #3–7, colour map (decided scheme), starter colour→truck (Tangerine→3, Peacock→4, Banana→5).
- **Booking engine** — `POST /booking` writes the job + **ONE Sage event to the TEST calendar** (live-calendar
  guard enforced). All 7 lanes wired via `/app/new-booking` + `booking-bridge.js` (Collect + Invoiced browser-verified).
- **Day Board reader** — `GET /day-board` → drops `#` notes → colour→truck → **stack order = route order** →
  headline time. Wired to `/app/day-board` showing live routes. `is_manager_note` + `parse_headline_time` unit-tested.
- **Login + all 18 screens** — `/app` real PIN login → launcher (access-gated tiles) → every screen served via the
  `SCREENS` registry with its DB refs injected. Truck Hub / Bin Registry / crew calculators verified on real data.
- **Reference data from DB** (`app/web/refs.py`): fleet, colour map, bins, employees, rates (+ incidents/clock/
  field-jobs/weigh, None-until-data so screens keep demo until real rows exist).
- **Write-persistence — the whole crew day → Postgres** via generic sync (`/sync`, `sync-bridge.js` on every page)
  + a dedicated yard endpoint: **bins, roster (owner-guarded), incidents, clock in/out, job completion (field_job),
  yard weigh, and the yard-processing rich record** (waste class, stream %, gross/tare/net, dump fee — the disposal
  cost-model input). All verified against Render.

---

## 2. IN FLIGHT (loose ends, nothing mid-edit)

- **Disposal margin math** — `yard_processing` records now persist, but `disposal_facility` + `disposal_material`
  tables are **empty**. Need to seed the §9 facility/material list, then write the compute
  (customer charge by waste class − Σ(stream% × stream cost)). Tables built; no data, no compute fn yet.
- **Booking lanes 3–7** (bins, pm, contracts, custom, pallet) — wired by the *generic* bridge (keys off `curType`),
  but only Collect + Invoiced were browser-clicked. Should spot-check each lane's modal in a browser.
- **Yard `#wDone` literal-click** — the save path (`/yard-processing`) is proven from the real page, but the crew/truck
  fields are sheet-closure state, so I set the record as `grab()` would and POSTed via the bridge's exact path rather
  than clicking through the full sheet. A real end-to-end click-through is untested.

---

## 3. NEXT (in order)

1. **Seed disposal facilities/materials (§9)** + build the margin compute on `yard_processing` → real disposal margins.
2. **QuickBooks customer import (§13)** — upload the Customer Contact List export, preview+untick, dedupe on phone/email;
   then `build_customers`/`build_company`/`build_pm` refs → customers/contracts screens go real.
3. **Maintenance + reminders persistence** — build `maintenance` (`ij_maint_v2`) + `reminder` (`ij_reminders_v1`) tables
   + sync handlers to finish write-coverage.
4. **Verify booking lanes 3–7** + the yard `#wDone` click in a browser.
5. **Integrations** — first outbound: Twilio booking-confirmation text OR a Square payment link on the job
   (see `island-junk-SPEC-sms-and-texting.md` for the shared send-only updates line).

---

## 4. OPEN DECISIONS (waiting on Wes)

- **Bin truck's real dispatch number/label** — prototype's "12" is demo; not seeded (`scripts/seed_bins.py`).
- **Real unique PINs for the crew** — all seeded `0000`; owner must set real PINs before crew can log in.
- **Nanaimo-leased bins brand** — the 11 ROSS bins are seeded `brand=victoria` with `leased=True`; when the Nanaimo
  workspace is built, decide whether they move to `brand=nanaimo`.
- **Access-flag canonical list** + the orphan `reminders` flag — proposed in `docs/data-model.md`; confirm.
- **Missing file** — `island-junk-nanaimo-setup-rates-v1.html` is referenced but not in the repo (only its store shape).
- **June-2026 expanded palette** — classic palette has only 3 hand-load colours, so only 3 hand-load trucks can run
  distinctly; the full 24-colour set is needed to colour all of #3–7.
- **Spec §4 `#3 truck` example** — reads like a typo for `Truck #3`; implemented the plain leading-`#` = note rule.
  Confirm (see `app/dispatch/calendar_read.py::is_manager_note`).
- *Resolved this session (in docs/data-model.md):* Flamingo = residential unpaid (CC **or** e-transfer), status-only;
  bin truck = Graphite/Blueberry; Tomato→Flamingo lifecycle; 7 booking lanes; merged bin lifecycle enum; dispatch
  `truck` table separate from a future maintenance `vehicle` table.

---

## 5. GOTCHAS (don't forget)

- **Alembic + shared `brand` enum:** autogenerate emits inline `sa.Enum('victoria','nanaimo', name='brand')` in *every*
  new migration — you MUST hand-edit it to a module-level `postgresql.ENUM(..., name='brand', create_type=False)` and
  reference it, or you get "type brand already exists". New enums: create once with `checkfirst=True` + `create_type=False`
  on columns. (Every migration in `migrations/versions/` shows the pattern.)
- **Owner is `brand=NULL`** (shared across brands). Any brand-scoped employee lookup MUST include brand-null
  (`or_(brand==b, brand.is_(None))`) — otherwise you create a duplicate owner (bug we hit + fixed in `apply_employees`).
- **ORM registry:** `app/models/__init__.py` is intentionally EMPTY (avoids a cycle base→types→enums). Import
  `app.models.all` to register every model; `new_session()` already does. Alembic env + `app.main` import it too.
- **Python 3.14 (bleeding edge):** plain `uvicorn` (not `[standard]`), `psycopg[binary]`, `pbkdf2_sha256` (not bcrypt),
  and `tzdata` (Windows has no tz DB, needed by `zoneinfo` in `gcal.list_events_for_day`).
- **Refs vs sync:** refs inject inline in `<head>` (synchronous, before prototype scripts → no echo); `sync-bridge.js`
  overrides `localStorage.setItem` at end of `<body>` → only *user* writes sync. `reference_bootstrap_script` skips a
  builder returning `None` (no half-empty blobs that break a screen).
- **Booking calc uses a hardcoded `RES` constant, NOT `ij_rates_v1`** — real rates only reach the *crew calculators* +
  contracts, not the booking screen's residential calc.
- **Day board truck lanes** come from `ij_fleet_v1` + `ij_colourmap_v1` (injected from DB) — colour→truck must map to real
  fleet numbers or jobs land on lanes that don't render.
- **Every calendar test creates real TEST-calendar events — always delete them by id afterward.** The guard
  (`app/integrations/gcal.py`) hard-refuses the two live IDs and anything but the configured TEST calendar.
- **Cosmetic only:** Windows console renders `—`/`·`/`≥` as `�` in Bash output (DB stores correct UTF-8); TestClient
  prints a harmless "httpx deprecated" warning (test client only, not the app).

---

## 6. HOW TO RESUME

**Prereqs already in place:** `.env` (Render `DATABASE_URL` + `SESSION_SECRET`), `spike/service-account-key.json`
(Google creds). The Render DB is **already migrated + seeded** — steps 3–4 are only for a fresh DB.

```bash
# from repo root (Windows paths; .venv already exists)
.venv/Scripts/python.exe -m pip install -r requirements.txt         # 1. deps
.venv/Scripts/python.exe -c "import app.main; print('imports OK')"   # 2. sanity
.venv/Scripts/alembic.exe -c alembic.ini upgrade head               # 3. migrate (head = 4cd57b8ea105)
# 4. seed (fresh DB only, in this order):
.venv/Scripts/python.exe -m scripts.seed_owner
.venv/Scripts/python.exe -m scripts.seed_crew
.venv/Scripts/python.exe -m scripts.seed_trucks
.venv/Scripts/python.exe -m scripts.seed_bins
.venv/Scripts/python.exe -m scripts.seed_rates
.venv/Scripts/python.exe -m scripts.seed_colours
.venv/Scripts/python.exe -m scripts.seed_colour_trucks
# 5. run
.venv/Scripts/python.exe -m uvicorn app.main:app                    # http://127.0.0.1:8000/app  (login) · /health
```

Login for the demo: **Manager (demo) / PIN 1111** or **Wes (owner) / PIN 4321**.
Preview config: `.claude/launch.json` (server name `api`).

**Safety confirmed still in place:** calendar guard in `app/integrations/gcal.py` (+ `/spike`) refuses the two live
calendar IDs and writes only to the TEST calendar; `.gitignore` protects `.env`, `**/service-account-key.json`,
`**/.venv/`, `spike/out/`.
