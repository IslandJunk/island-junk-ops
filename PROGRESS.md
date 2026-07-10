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
- **30 tables** on Render via 9 Alembic migrations (+ maintenance_doc, defect_flag, reminder): employee, owner_security, device, auth_session,
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
- **Maintenance + reminders persistence + 48h CC-charge reminder LIVE + tested.** Migration `46d1bfdb249d` adds
  3 tables (Render migrated). **Maintenance** (`ij_maint_v2`) persists as one JSONB **doc per brand** (`maintenance_doc`)
  — the whole `{order,m,_v}` verbatim, so the prototype's structure + client-side migrations are untouched.
  **Defect flags** (`ij_fixes_v1` walk-arounds → `defect_flag`): upsert-by-id, closed via `ij_fixes_resolved_v1`.
  **Reminders** (`ij_reminders_v1` → `reminder`): upsert-by-id + "done = removed from list" reconcile, scoped to
  app kinds so it never clobbers owner CC-charge rows. New sync handlers (`apply_maint/fixes/fixes_resolved/reminders`)
  + `sync-bridge.js` whitelist + refs (`build_maint_v2/fixes_v1/reminders_v1`) wired to the maintenance/reminders/truck
  screens. **§9/§11 48-hour CC-charge reminder** (`app/reminders/service.py`): auto-created at booking for
  `residential_bin` (due = drop+48h, `kind=cc_charge`, "CC? UNPAID (DATE)…manual"), owner-only queue
  `GET /reminders?kind=cc_charge` + `POST /reminders/{id}/done` + manual `POST /reminders/cc-charge`. **The charge
  stays manual** (guardrail §2). **Verified end-to-end** on Render (blob round-trip, flag add+resolve, reminder
  reconcile leaving CC-charge intact, auto-create due=drop+48h, owner check-off, manager 403; all test rows deleted).
- **QuickBooks customer import (§13) — core LIVE + tested.** `app/customers/qb_import.py` parses a **QuickBooks
  Customer Contact List** CSV (skips the report preamble, BOM; **alias-mapped headers** cover QBO *and* Desktop
  wordings; stitches split billing address). Classifies commercial vs residential (Company column ⇒ company; splits
  `Last, First`/`First Last`), **dedupes on digits-only phone / email / name** vs the DB *and* within the batch, and
  `apply_import` inserts only the new — **re-importing the same export inserts nothing.** Owner-only
  `POST /customers/import/preview|apply` + `GET /customers/summary`; `scripts/import_customers.py <file> [--apply]`
  CLI. `build_customers/company/pm` refs feed the booking screen. **Verified end-to-end** on Render (QBO + Desktop
  samples: 3 residential + 2 company classified, cross-format phone dedupe, idempotent re-apply, refs shape-checked,
  all test rows deleted). *Caveat:* header map is against the **standard** QB export — confirm vs Wes's real file;
  PM tree isn't in a flat contact list (stays app-entered); demo `QB_CUST/QB_COMM` consts still coexist (see §2/§4).
- **Disposal cost model LIVE** — `scripts/seed_disposal.py` seeds Victoria's **7 facilities + 24 materials + 24
  rate-history rows** (from `island-junk-rate-sheet-v14.html`, idempotent, every material FK'd to a facility).
  `app/yard/disposal.py::compute_load_margin` turns a `yard_processing` load into a margin: customer charge =
  headline `waste_class` price × net tonnage; our cost = the class's own `cost` × tonnage (pass-through) **or**
  Σ(stream% × tonnage × stream cost) for a blank-cost Yard-sort class; margin = charge − cost. Costs pulled **live**
  from the registry (edit a rate once → re-prices everywhere). `build_rates_v1` now emits the real facilities/disposal
  into `ij_rates_v1`. Owner-only `GET /disposal/margins` reads it. **Verified end-to-end** on Render (POST yard load →
  margins showed charge 550 / cost 208 / margin 342; streams + explicit + label-normalization + no-weight + unknown-class
  paths all checked; test row deleted).

---

## 2. IN FLIGHT (loose ends, nothing mid-edit)

- **QuickBooks import — real-file confirmation + demo suppression.** The importer works against the *standard*
  QuickBooks Customer Contact List columns (alias-mapped). To lock it: drop Wes's **actual export** at a path and run
  `python -m scripts.import_customers <file>` (preview) — if any column isn't recognised, add it to
  `COLUMN_ALIASES` in `app/customers/qb_import.py` (one-line change). Also: the booking screen's hardcoded `QB_CUST`
  (4 residential) + `QB_COMM` (5 commercial) demo **consts** still concat with the injected real data — fully
  retiring them needs a booking-screen/bridge edit (they're `const`, so a localStorage ref can't override them).
- **Yard waste-class picker still hardcoded** — the disposal cost model is live, but the yard-processing screen's
  `WASTE_CLASSES` list (13 labels) is still a hardcoded array that *overlaps but ≠* `disposal_material.m` (24 rows).
  The compute reconciles the two via `WASTE_CLASS_ALIAS` + whitespace normalization, but two picker labels have **no
  registry material** (`Mixed drywall (≥31%)`, `Concrete/clay tile`) → a load booked under those returns
  `cost_basis:"unknown"` with a warning. The proper fix (flagged in `docs/data-model.md`) is to drive the picker from
  the materials registry so there's one source. Deferred — needs a careful yard-screen edit.
- **Booking lanes 3–7** (bins, pm, contracts, custom, pallet) — wired by the *generic* bridge (keys off `curType`),
  but only Collect + Invoiced were browser-clicked. Should spot-check each lane's modal in a browser.
- **Yard `#wDone` literal-click** — the save path (`/yard-processing`) is proven from the real page, but the crew/truck
  fields are sheet-closure state, so I set the record as `grab()` would and POSTed via the bridge's exact path rather
  than clicking through the full sheet. A real end-to-end click-through is untested.

---

## 3. NEXT (in order)

1. **Verify in a browser** — booking lanes 3–7, the yard `#wDone` click, and now the maintenance-hub / reminders /
   truck-hub screens reading + writing real data (the sync round-trips are proven at the API layer, not yet clicked through).
2. **Integrations** — first outbound: Twilio booking-confirmation text OR a Square payment link on the job
   (see `island-junk-SPEC-sms-and-texting.md` for the shared send-only updates line). Then the **off-board Google
   reminder-calendar mirror** for CC-charge reminders (write-only to a dedicated reminder calendar — needs its id, §4).
3. **Drive the yard waste-class picker from the disposal registry** (retire the hardcoded `WASTE_CLASSES` — see §2).
4. **Confirm QB import vs Wes's real export** + retire the `QB_CUST/QB_COMM` demo consts (see §2).

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
- **Disposal stream→cost mapping** (`app/yard/disposal.py::STREAM_MATERIAL`) — the 6 yard-sort streams are costed
  against chosen materials: junk→"General refuse (sorted)" $160, **wood→"Clean wood" $80** (could be "Treated/dirty
  wood" $110 for C&D), drywall→"Drywall — clean/tested new" $415, concrete→"Clean concrete" $41, metal→$0 (income),
  recycle→"Cardboard" $0. All editable via the rate sheet; **confirm wood especially** (clean vs dirty changes margins).
- **Two waste-class picker labels have no priced material** — `Mixed drywall (≥31%)` and `Concrete/clay tile` aren't in
  the 24-row registry, so loads under those can't be margin-costed. Add the missing material rows, or map them.
- **QuickBooks export format** — importer built against the *standard* Customer Contact List columns (alias-mapped for
  QBO + Desktop). **Provide a real export** to lock the mapping (any unrecognised header → add to `COLUMN_ALIASES`).
  Also: businesses entered in QB with a **blank Company column** import as residential (a flat contact list can't tell)
  — the preview's untick lets the owner catch these. Confirm this is acceptable.
- **CC-charge reminder — two open points.** (a) The **off-board reminder calendar id** isn't set, so the reminder lives
  only in the app's `reminder` store for now; the Google-calendar mirror (write-only) is deferred until the id exists.
  (b) `due = drop + 48h` uses **plain calendar days** (weekend/stat handling like the bin billable-day rule isn't applied)
  — confirm 48h means calendar hours. Also the auto-trigger fires **at booking** (planned drop date); if a real
  "residential-bin dropped" completion event is added later, call `add_cc_charge_reminder` there instead/again.
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
.venv/Scripts/alembic.exe -c alembic.ini upgrade head               # 3. migrate (head = 46d1bfdb249d)
# 4. seed (fresh DB only, in this order):
.venv/Scripts/python.exe -m scripts.seed_owner
.venv/Scripts/python.exe -m scripts.seed_crew
.venv/Scripts/python.exe -m scripts.seed_trucks
.venv/Scripts/python.exe -m scripts.seed_bins
.venv/Scripts/python.exe -m scripts.seed_rates
.venv/Scripts/python.exe -m scripts.seed_colours
.venv/Scripts/python.exe -m scripts.seed_colour_trucks
.venv/Scripts/python.exe -m scripts.seed_disposal
# 5. run
.venv/Scripts/python.exe -m uvicorn app.main:app                    # http://127.0.0.1:8000/app  (login) · /health
```

Login for the demo: **Manager (demo) / PIN 1111** or **Wes (owner) / PIN 4321**.
Preview config: `.claude/launch.json` (server name `api`).

**Safety confirmed still in place:** calendar guard in `app/integrations/gcal.py` (+ `/spike`) refuses the two live
calendar IDs and writes only to the TEST calendar; `.gitignore` protects `.env`, `**/service-account-key.json`,
`**/.venv/`, `spike/out/`.
