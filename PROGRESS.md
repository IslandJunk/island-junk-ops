# Island Junk — Build Progress & Handoff

**2026-07-10 (session 3, cont.)** — Owner invoicing **"start 48-hour e-transfer clock"** button wired into the ready-to-
invoice sheet (fires `POST /reminders/cc-charge`, idempotent, mirrors to the reminder calendar, charge stays manual).
Then persisted the first slice of the **operational tail**: **follow-up reviews** (`ij_reviews_v1`, §11) + **consumables
usage ledger** (`ij_usage_v1`) — both suppress their prototype demo-seeds by injecting `[]` (verified the manager-hub no
longer persists Bonnie-Reyes demo rows). Two items **deferred with reasons** (need a product/Wes decision, not code): the
yard waste-class picker (needs a `headline_class` flag + wording reconciliation) and the Nanaimo setup screen (no approved
prototype → would violate the port-only guardrail; also depends on the deferred integrations). More tail keys remain
(stock, PO#, hands-on pre-check, yard clock, sign-in log) — see §3.

**2026-07-10 (session 3)** — Finished the **rest of field/dispatch persistence** (§3 NEXT #1): the **day-board crew
overlays** (`ij_dayboard_status/notes/sitelog_v1` — status override, crew note, on-site log, all keyed by calendar
event id), **attendance** (`ij_attendance_v1`) + **breaks** (`ij_breaks_v1`), and the office **day notes**
(`ij_daynotes_v1`) + long-out **threshold config** (`ij_binsout_cfg_v1`, in a new generic `brand_setting` KV). 5 new
tables (migration `84b98fe168ce`). Caught + fixed a concurrency bug on the way: the three day-board overlays share one
`(brand, event_id)` row, so two near-simultaneous crew writes raced on the unique constraint and one was lost — now an
atomic Postgres `ON CONFLICT` upsert. Verified end-to-end (API + client `setStatus`/`setNote` path + reconcile-clear).
Also gave Wes the steps to share the new **punch-time test calendar** with the service account (mirror wiring queued
until it's shared). Integrations still last, per Wes.

**2026-07-10 (session 2)** — Persisted the **bin-tracker driver tool** (§3.1 NEXT #1's headline piece — it was the last
big in-memory-only screen). Two parts: **(A)** the driver's own outputs now save — the whole driver day (`ij_binday_v1`),
field bin weights (`ij_tares_v1` / `ij_weighins_v1`), and the morning gear-check log (`ij_tooldaily_v1`) — plus a fix so
the driver's weigh events keep their bin code; **(B)** the tracker now reads the **real 75-bin fleet** from the DB instead
of its hardcoded in-memory `seed()`, and every driver action (drop / pick / return / weigh / mark-fixed / pull-to-service)
persists back through `apply_bins`. Verified end-to-end in the browser + DB (a pull-to-maintenance survived a reload) with
no regression to the registry / yard screens that share `ij_bins_v1`.

**2026-07-10 (session 1)** — Finished the **reference-data write-back** cluster (every owner-editable screen now saves to
Postgres *and* the booking consumes those saved rates), retired the booking's demo customers, added two empty editable
waste-class spots, and built the **§11 ready-to-invoice queue** on the owner hub. Also fixed a serving bug that was
silently breaking the owner-hub dashboard. Victoria is now a broadly complete, backed, multi-user app behind the
approved prototypes; the remaining big pieces are the rest of field/dispatch persistence (day-board overlays, breaks +
attendance), the external integrations (Twilio/Square/Dropbox — need creds), and Nanaimo phase 2.

**Stack:** FastAPI + SQLAlchemy 2 + Alembic + Postgres (Render, via `.env`). Python 3.14. Serves the approved
`/prototypes` HTML **untouched** — real DB data is injected inline as `localStorage` in `<head>` before each page's
scripts run, and per-screen **bridges** (appended before `</body>`) swap `localStorage` writes for API calls and
override the prototype's hardcoded constants with real data. Deploy target: Render.

**Repo state:** clean working tree, Alembic head **`70f23a968aa0`**
(migrations live under `migrations/versions/`, NOT `alembic/versions/`). Login: **Manager / PIN 1111** or **Wes (owner) /
PIN 4321**. Preview server config: `.claude/launch.json` (name `api`); it runs plain uvicorn with **no `--reload`**, so
restart the preview server after any Python edit. Owner Hub has a *second* gate (owner password + simulated 2FA) — it's
the prototype's own client-side demo; in browser tests call `unlock()` to skip it.

Reference docs (authoritative; a spec wins where it goes deeper): `island-junk-SPEC-scheduling-and-dispatch.md`,
`island-junk-SPEC-login-sessions-and-access.md`, `island-junk-SPEC-sms-and-texting.md`, `docs/data-model.md`,
`island-junk-CURRENT-VERSIONS.md`, and `CLAUDE.md`.

---

## 1. DONE (whole build, verified against Render)

**Foundation & data**
- Calendar **stack-order spike PROVEN** (`/spike`): `orderBy=startTime` recovers the manager's manual top-to-bottom stack.
- Brand-tagged base/mixins, config, **PIN auth + owner-only guard** (logic layer, not just hidden UI).
- **30 tables via 11 Alembic migrations.** Seeded: 75-bin fleet, 15-person roster (PINs `0000` placeholder), Victoria
  rate card, trucks #3–7, colour map + starter colour→truck, disposal facilities/materials + rate history, area surcharges.
- **Reference data from DB** (`app/web/refs.py`): fleet, colour map, bins, employees, rates (facilities/materials/
  **surcharges/custom-customers**), incidents, clock, field-jobs, weigh, maintenance doc, defect flags, reminders,
  residential/company customers, PM tree, contracts. None-until-data so a screen keeps its demo until real rows exist.

**Booking / dispatch**
- **Booking engine** — `POST /booking` writes the Job + **ONE Sage event to the TEST calendar** (live-calendar guard
  enforced). All 7 lanes wired via `booking-bridge.js`; a **full Bins booking** was driven end-to-end in the browser.
- **Day-Board reader** — `GET /day-board` drops `#` manager notes → colour→truck → **stack order = route order** →
  headline time. (`is_manager_note` + `parse_headline_time` unit-tested.)
- **Booking now reads the saved rate sheet** (`booking-bridge.js::applyRateSheet`): residential `RES` (loads/min/labour/
  GST/parking/items), commercial `COMM` (loads + included-minutes), and `binBase`/`binSurFor` all read `ij_rates_v1`
  (added to the new-booking ref keys). Browser-verified live (edited a DB rate → booking reflected it → tracked back).
- **Demo customers retired** — `retireDemoCustomers` empties the const `QB_CUST`/`QB_COMM` in place once real customers
  are injected; only the imported 2,173 + 824 show, nothing demo merges/syncs.

**Crew/yard/owner day → Postgres (write-coverage)**
- Whole crew day persists via generic `/sync` (`sync-bridge.js` whitelist) + a dedicated yard endpoint: **bins, roster
  (owner-guarded), incidents, clock in/out, field-job completion, yard weigh, and the rich yard-processing record**
  (waste class, stream %, gross/tare/net, dump fee). Yard `#wDone` full sheet click-through browser-verified → margin.
- **Maintenance + reminders + defect flags** persist: `maintenance_doc` (whole `ij_maint_v2` JSONB doc/brand),
  `defect_flag` (`ij_fixes_v1` + `ij_fixes_resolved_v1`), `reminder` (`ij_reminders_v1`, done=absent reconcile).

**Bin-tracker driver tool → Postgres (was in-memory only) — COMPLETE**
- **Part A — the driver's own outputs persist** (3 new tables in migration `44049978642e`): `bin_driver_day`
  (`ij_binday_v1`, the whole sign-in→walk-around→gear→odo→clock→EOD day, verbatim JSONB, keyed brand+driver+date,
  **write-only** — a shared tablet must not restore another driver's day, and same-device localStorage already restores);
  `bin_weigh` (`ij_tares_v1` + `ij_weighins_v1`, current field weight per bin, row-per-key, per-key upsert so a concurrent
  device isn't clobbered, **echoed back** to the driver + yard); `tool_daily_log` (`ij_tooldaily_v1`, morning gear check,
  keyed brand+truck+date, write-only). Also **fixed `apply_weigh`**: the driver writes `ij_weighlog_v1` with `code`/`kind`
  (yard uses `bin`/`source`) — the handler now accepts either, so driver weigh events keep their bin code (was landing as
  `bin=NULL`).
- **Part B — the tracker reads + persists the REAL fleet.** The prototype built its fleet in memory (`let bins=seed()`)
  and never touched `ij_bins_v1`, so the injected fleet was ignored and every driver action vanished on reload. New
  `bin-tracker-bridge.js` reassigns the shared `bins` global from a rich, tracker-shaped injection (`ij_bins_full_v1`, new
  builder `build_bins_full_v1`) and wraps `render()` (the choke point every board action funnels through) to write `bins`
  back to `ij_bins_v1` → sync → `apply_bins`. `apply_bins` was expanded to absorb the tracker's rich write (`status` +
  drop/pick/weigh/repair fields) **present-key-only**, accepting `status` (tracker) OR `state` (registry/yard); it also now
  persists the yard's `cleared` roofing summary. **`build_bins_v1` stays lean on purpose** — registry + yard-hub +
  yard-processing read that unchanged, so they're untouched (regression-verified: they still load the lean `state` shape).
  Browser-proven: real 75-bin fleet loads (16-04 shows DB state, not the seed's demo rental), a pull-to-maintenance +
  repair note synced to the DB and survived a reload; lean registry/yard write path also re-verified via API.

**Field/dispatch persistence — day-board overlays + attendance/breaks + office notes/config (COMPLETE)** — migration
`84b98fe168ce` (5 tables):
- **`dayboard_overlay`** (one row per brand+calendar-event-id) collapses the three day-board crew overlays:
  `ij_dayboard_status_v1` (status override), `ij_dayboard_notes_v1` (crew note), `ij_dayboard_sitelog_v1`
  (`{start,finish,loc}`). Notes + sitelog **reconcile-clear on absence** (the prototype deletes the key when emptied;
  the injected full set makes the device authoritative); status is grow-only. Because 3 sync keys write the SAME row,
  the upsert is an **atomic `ON CONFLICT`** (`_overlay_upsert`) — a plain select-then-insert raced + dropped a column
  when two overlays were set in the same 400 ms debounce window.
- **`attendance`** (`ij_attendance_v1` → row per brand+date+name; status/note/lateTime) and **`break_log`**
  (`ij_breaks_v1` → row per brand+name+date; verbatim doc + `total_minutes` lifted out). Upsert-only (permanent HR).
- **`day_note`** (`ij_daynotes_v1` → row per brand+date; bin/yard/handson columns, **per-shift present-key** so a hub
  setting one shift never blanks the others) and **`brand_setting`** (generic brand KV; homes `ij_binsout_cfg_v1` =
  `{days}` and future 1-off settings).
- Injected on the screens that read them: day-board (overlays), owner/manager hubs (attendance/breaks/daynotes/binsout),
  bin-tracker + truck-hub + yard-hub (daynotes), employee-hours (breaks), bin-registry (binsout). All None-until-data.

**Owner invoicing — 48-hour clock button** — the ready-to-invoice sheet (`owner-hub-bridge.js`) now shows a
"Residential? Start 48-hour e-transfer clock" button per processed bin; it fires `POST /reminders/cc-charge` (idempotent
per customer+addr+day), shows the due date inline, and the charge stays manual (§2). Queue bin items now carry `address`.
Browser-verified: button → reminder (due skips the weekend) → mirrored to the reminder calendar → cleaned up.

**Trucks + colour→truck map now editable/persisted (§6)** — `apply_fleet` (`ij_fleet_v1` = `{num:{mgr}}`) upserts the
dispatch-truck roster by (brand, num) with its lead; a truck dropped from a present non-empty set is **soft-removed**
(`active=False`, history survives §7). `apply_colourmap` (`ij_colourmap_v1`) sets `assigned_truck` on **assignable**
colours ONLY — **status + sage colours are never touched** (Make.com keys ad-conversion off the status colours, §5/§15).
Verified: a payload trying to reassign flamingo(status) was skipped while banana(assignable) updated; both models already
existed (no migration) and their builders already inject on the hubs, so this closes the §13 "people & trucks / bins &
colour map" editing gap for **both** brands. (Follow-up: creating owner-added **custom** colour rows needs their hex/
colorId — skipped for now, not lost.)

**Global brand-switching — the Nanaimo keystone (§3, approved by Wes 2026-07)** — the owner-hub's existing
Victoria↔Nanaimo switch is now THE workspace switch: everything the owner sees/edits follows it.
- **`POST /auth/brand`** (owner-only) sets `session.active_brand`; **`app/api/deps.py`** gains `active_brand_for`
  (owner → session brand, crew → locked brand, default Victoria), `get_active_brand`, and `optional_brand` (resolves a
  served page's brand without requiring auth). Serving (`app_screen`/`main_hub`) + owner reads (invoice-queue, disposal,
  reminders, customers, yard) now resolve the active brand.
- **Never-mix (§15) safeguard:** each served page is stamped `window.__IJ_BRAND`, and **`sync-bridge.js` sends that brand
  with every write** — the sync endpoint writes to the *page's* brand for the owner, but **hard-forces crew to their own
  brand** regardless of payload (a Victoria page can never write to Nanaimo). Verified: owner switch routes Nanaimo edits
  to Nanaimo, Victoria untouched; a crew member sending `brand:nanaimo` was forced to Victoria; crew `POST /auth/brand` →
  403. `owner-hub-bridge.js` aligns the prototype's client `BRAND` to the served brand and makes the switch persist +
  reload so every screen follows. Browser-verified end-to-end + reversible.
- **This unblocks Nanaimo setup via the existing approved screens** (rate-sheet, employees, bins, customers) — no new
  "setup" screen needed (Wes's call). **Caveats:** the day-board + booking still resolve brand the old way (calendar-bound;
  Nanaimo has no calendar yet — integration phase). Multi-tab: a stale page still syncs to the brand IT was served with
  (that's the safe behavior); reads use the session brand.

**Operational tail — hands-on truck pre-check** — migration `70f23a968aa0`: **`precheck_log`** (`ij_precheck_v1`, one row
per brand+truck+date; who/when/flagged + items JSONB). The parallel to the bin driver's walk-around (which rides in
`bin_driver_day`); flagged items already raise `ij_fixes_v1` defect flags — this keeps the full inspection record.
**Write-only** (in SYNCED, not injected — a shared tablet mustn't restore another crew's check). Round-trip verified.

**Operational tail (slice 1) — reviews + consumables usage** — migration `e7b266ed5ed6`:
- **`followup_review`** (`ij_reviews_v1`, §11 follow-up-reviews tool) — upsert by `id`, verbatim doc + name/sent/skipped
  lifted. **`usage_event`** (`ij_usage_v1`) — append-only consumables ledger, deduped by (item, timestamp, type) both
  against the DB **and within the payload** (a re-sync or a doubled event would otherwise 500 on the unique key).
- Both builders return **`[]` (not None) when empty on purpose** — the injected empty array suppresses the prototype's
  demo-seed *write* (`revList()`/`seedUsage()` persist fake rows to localStorage otherwise). Verified the manager-hub no
  longer leaks demo reviews to the DB. Injected on the crew forms + hubs that read/write them.

**Disposal cost model**
- `scripts/seed_disposal.py`: 7 facilities + **26 materials** (24 + 2 empty editable spots) + rate history.
- `app/yard/disposal.py::compute_load_margin`: charge = waste-class price × net tonnes; cost = the class's own cost, or
  Σ(stream% × tonnes × stream cost) for a yard-sort class; margin = charge − cost. Costs read **live** from the registry.
- Owner-only `GET /disposal/margins`. **Model confirmed w/ Wes:** mixed rates ($275 <50% wood / $245 ≥50%) = what we
  charge (yard); clean/dirty wood ($80/$110) + sorted rates = what we pay (landfill).

**QuickBooks customer import (§13)** — `app/customers/qb_import.py` reads a Customer Contact List in **CSV or Excel**
(openpyxl; alias-mapped headers; multi-line address stitch; multi-number "Phone Numbers" → first number; field-length
caps). Classifier handles a **no-Company-column** export via `infer_kind` (keyword/number/name-shape). Owner-only
`POST /customers/import/preview|apply`, `GET /customers/summary`; `scripts/import_customers.py "<file>" [--apply]`.
**Wes's `Victoria Customers.xlsx` imported: 2,173 residential + 824 company.**

**CC-charge reminder (§9/§11)** — invoice-triggered, **48h = 2 working days** (`app/core/dates.py` skips weekends + BC
stat holidays; Fri invoice → Tue). `POST /reminders/cc-charge` (invoice_date defaults today) → owner queue
`GET /reminders?kind=cc_charge` + `POST /reminders/{id}/done`. **Off-board Google reminder calendar is LIVE** (calendar
"CC Charge Reminders" shared with the service account): a new reminder creates a Flamingo all-day event on the due date;
marking paid recolours it **purple/Grape**. Guarded to that calendar ONLY (dispatch + TEST calendars hard-refused). The
charge itself is always manual.

**Reference-data write-back — CLUSTER COMPLETE (every owner edit saves)**
- **Rate sheet** (`apply_rates`, owner-only): rate_card scalars + JSONB, disposal facilities + materials (rate history on
  change; owner-authoritative reconcile within a present non-empty list), **area surcharges** (regular + `roofing_bin_amount`),
  and **custom customers** (`ij_rates_v1.customers[]` → `contract` `rc_*`, extras in `properties`). Screen registered at
  `/app/rate-sheet`.
- **Customers** (`apply_customers` / `apply_company_customers`): upsert-only (never delete-by-absence; the list is thousands).
- **PM tree** (`apply_pm`): nested company→group→building upsert, matched by DB-uuid id else name (no dup on re-sync).
- **Contracts** (`apply_contracts`, `ij_contracts_v1`): near-1:1 model upsert; `build_contracts_v1` feeds the booking.

**Owner ready-to-invoice queue (§11)** — `app/invoicing/service.py::invoice_queue`: completed commercial `field_job`s +
processed yard bins (**with disposal margin**) + roll-off bins **overdue** (14+ days). Owner-only `GET /invoice-queue`.
`owner-hub-bridge.js` replaces the hub's demo alerts with real counts + detail sheets (dropped the fake unpaid-invoices
tile — that's QuickBooks data). **Never invoices/charges.** Browser-verified.

**Endpoints:** `/auth/*`, `/booking`, `/day-board`, `/sync`, `/yard-processing`, `/disposal/margins`,
`/customers/import/*` + `/customers/summary`, `/reminders*`, `/invoice-queue`.

---

## 2. IN FLIGHT (nothing is mid-edit / broken — these are small open loops)

- **Yard-waste "min $24" row** — Wes described yard-waste dump prices as min $24 / small $40 / medium $75 / large $100.
  The size prices ($40/$75/$100) already live in the rate sheet's `yardWaste` rows and are editable/persisted. The distinct
  **min $24** row is NOT added yet — waiting on Wes to confirm he wants it, then it's a small `yardWaste`-shape + rate-sheet
  wire-up.
- **Two empty waste-class prices** — `Mixed drywall (≥31%)` and `Concrete/clay tile` are seeded with a **blank** per-ton
  charge (editable spots in the rate sheet). They cost out as soon as Wes fills the price; until then the margin marks them
  uncosted (by design).
- **CC-charge "start 48h clock" UI** — the endpoint + calendar mirror work; there's no button yet on an owner invoicing
  screen to fire it when he sends a residential-bin invoice. Add the button when the owner invoicing UI is built.

---

## 3. NEXT (in order)

1. **Field/dispatch persistence — DONE** (bin-tracker in session 2; day-board overlays + attendance/breaks + day
   notes/config in session 3). The bin-tracker's shared punch mirror (`ij_punches_v1`) and its device-local day-board
   handoff (`ij_active_day_v1`) were **intentionally left unpersisted** — the authoritative clock record already syncs
   via `ij_clock_log`, and the handoff is ephemeral per-device state.
   - **Remaining sub-item: the punch-time calendar mirror.** Wes created a dedicated **punch-time TEST calendar**
     (`c_1033bcf8590acc0d57229b30e59d0169c4211883dd51ad18acb15476cc0193aa@group.calendar.google.com`) to mirror clock
     in/out onto a Google Calendar. **Blocked on sharing:** share it (writer / "Make changes to events") with the
     service account `ij-calendar-spike@island-junk-spike.iam.gserviceaccount.com` (checked 2026-07-10 → 404, not shared
     yet). Then wire `google_punch_calendar_id` into config + a `_assert_punch_calendar` guard (live dispatch calendars
     stay hard-refused) + a graceful `punch_calendar_accessible()` skip (mirror the CC-charge reminder pattern), and
     confirm with Wes whether he wants **one event per punch** or **one per-day hours event**.
2. **Operational-tail persistence (IN PROGRESS — the safe, non-integration continuation).** Done this session: reviews +
   usage + **precheck**. Remaining user-authored keys worth persisting (skip device-local/ephemeral ones):
   **`ij_stock_v1`** (supplies stock levels — pairs with usage; note: its "seed" is the real consumable catalog with demo
   quantities, so persist the `{items}` doc but expect the catalog to carry through), **`ij_po_needed_v1`** (PM PO#s —
   DEFERRED for a seed-guard: its demo is gated by `ij_po_seeded_v1`, so injecting `[]` won't suppress it; inject the guard
   flag or skip the seed in the handler), **`ij_yard_clock_v1`/`ij_yard_workers_v1`** (yard self-clock — hours-adjacent;
   check overlap vs `ij_clock_log` first), **`ij_checklists_v1`**, **`ij_bin_notes_v1`/`ij_bin_done_v1`**, **`ij_swing_log_v1`**.
   Same model→migration→handler→ref pattern. **Intentionally NOT persisted** (device-local/ephemeral or already covered):
   `ij_active_day_v1`, `ij_session_v1`, `*_seeded*` guards, `ij_resume_*` drafts, `ij_*_collapsed/open` UI state,
   `ij_weighin_skips`, `ij_maint_snooze_v1`, `ij_punches_v1` (clock is authoritative via `ij_clock_log`), `ij_signin_log_v1`
   (the `AuthSession` table is already the authoritative sign-in record).
3. **Integrations** (need creds from Wes) — Twilio from the shared send-only **updates line** (booking confirm · on-our-way ·
   crew-entered next-customer ETA · reminder · residential completion) per `island-junk-SPEC-sms-and-texting.md`; Square
   payment links on the job; Dropbox photo auto-filing (TEST folder first). No A2P 10DLC for the local CA number. **Punch-time
   calendar mirror** rides here too (blocked on the calendar share above).
4. **Global brand-switching — DONE this session** (owner-hub switch is now global; owner-only; never-mix enforced).
   **Trucks + colour map now syncable — DONE this session too** (`apply_fleet`/`apply_colourmap`, status colours protected).
   Follow-ups: respect the active brand in the **day-board + booking** endpoints (deferred: calendar-bound, Nanaimo calendar
   TBD); create owner-added **custom colour** rows on colour-map sync (needs hex/colorId); optional hardening — send the
   page brand from the day-board/other read fetches too (multi-tab read consistency).
5. **Nanaimo setup — now via EXISTING screens (Wes's call).** No dedicated "Set up this workspace" screen (no prototype +
   would invent UI). With brand-switching live, the owner switches to Nanaimo and uses the existing rate-sheet (has a
   "Copy Victoria's rate card" path via `apply_rates`), employee, bins, and customer-import screens. Blockers before it's
   fully usable: the trucks/colour-map sync gap above, and the Nanaimo **calendar + Twilio + Dropbox + Square** (integration
   phase). Nanaimo rate/customer/bin/employee data entry works today once switched.
6. **Yard waste-class picker from the registry — DEFERRED (product decision).** The picker's `WASTE_CLASSES` is a curated
   13-item list whose wording differs from `disposal_material.m` (e.g. "Construction/demo" vs "Construction / demo";
   "Rubble" vs "Rubble (brick / tile / mortar)"), so a naive merge adds conceptual duplicates (13→~25). Needs a
   `headline_class` flag on `disposal_material` + Wes confirming the pickable set + exact wording. Pricing is unaffected
   meanwhile (the margin already reconciles labels).

---

## 4. OPEN DECISIONS (waiting on Wes — context in `docs/data-model.md`)

- **Colour semantics that touch Make.com** (high-stakes — Make reads job status colour off the ISLAND JUNK VICTORIA
  calendar and fires ad-conversion signals). Resolved in `docs/data-model.md` (2026-07-09) but **confirm before go-live**:
  **Flamingo(4) = STATUS only** (residential unpaid — CC *or* e-transfer; never a truck), and the **bin truck = Graphite/
  Blueberry** (Lavender stays a free assignable colour, NOT the bin truck). Preserve the exact colours Make keys on.
- **7 booking lanes vs the brief's 5 types** — modeled as `booking_lane` (collect/invoiced/bins/pm/contracts/custom/pallet)
  + `account_type` + bin `action`; §7's flat 5-value `type` was retired. Confirm this is the intended taxonomy.
- **Real crew PINs** — all seeded `0000`; owner must set real per-person PINs before crew can log in.
- **Bin truck's real dispatch number/label** — prototype's "12" is demo; the maintenance seed labels it "Bin truck (Hino) · #12".
- **Two empty waste-class prices** + the **yard-waste `min $24` row** (see §2).
- **QuickBooks export** — his real export had **no Company column** (handled by name-shape inference). A re-export *with*
  the Company Name column would give an authoritative company/residential split; and **wood default** is clean $80 (Wes: no
  preference) — flip to $110 in the rate sheet if mixed-load wood is usually treated.
- **Access-flag canonical list** (`docs/data-model.md`) — confirm the 12 flags + owner-only-grantable set (owner/estimate/swing).
- **Missing file** — `island-junk-nanaimo-setup-rates-v1.html` is referenced but not in the repo (only its store shape).
- **June-2026 expanded palette** — the classic palette has only 3 hand-load colours, so only 3 of trucks #3–7 colour
  distinctly; the full 24-colour set is needed to colour all five.

---

## 5. GOTCHAS (don't forget)

- **Scheduling spec §4 — the "#" rule (STANDING RULE):** a **leading `#` in a Google Calendar event title = a manager-only
  note the app ignores completely** (not a job, not dispatch). The day-board reader already drops these
  (`app/dispatch/calendar_read.py::is_manager_note`). Build it into every future calendar reader too. *(Open: the spec's
  `#3 truck` example reads like a typo for `Truck #3`; we implemented the plain leading-`#` = note rule — confirm.)*
- **Calendar guard (NEVER weaken):** `app/integrations/gcal.py` hard-refuses the two live IDs (`LIVE_VICTORIA`, `LIVE_JOBS2`)
  + `primary`. Booking writes ONLY the configured TEST calendar; CC-charge writes ONLY the configured reminder calendar
  (each guard refuses the other's target too). Every calendar test creates a **real** event on those calendars — delete it
  by id afterward.
- **`_serve_prototype` injects before the LAST `</body>` only** (not replace-all) — some prototypes embed `</body>` inside
  JS export-template strings (owner hub's PDF/print docs); a replace-all injects a `<script>` mid-string and kills that whole
  script block. (`</head>` uses the FIRST match, which is the real page head.)
- **Bridges mutate `const`s in place** — you can't reassign a top-level `const` (RES, QB_CUST, WASTE_CLASSES, OWNER_ALERTS)
  from a later script, but you CAN mutate its properties / `.length`. That's how the booking/owner-hub bridges retrofit real
  data without touching the prototype files.
- **…but a top-level `let`/`function` you CAN reassign from a later appended classic script** — all classic (non-module,
  sloppy-mode) scripts on a page share one global lexical environment, so `bin-tracker-bridge.js` reassigns the prototype's
  `let bins = seed()` to the real fleet and wraps `function render()` to persist. Confirm the target prototype is classic
  (no `type="module"`, no `use strict`) before relying on this. Persist on **change only** (snapshot-compare) so the
  initial injected-fleet repaint doesn't echo the whole fleet back every load.
- **`ij_bins_v1` is served in TWO shapes on purpose.** `build_bins_v1` = the **lean** registry `state` shape that
  bin-registry + yard-hub + yard-processing read/write (unchanged — don't "unify" it into those screens). `build_bins_full_v1`
  = the **rich** driver-tracker `status`+fields shape, injected ONLY on the bin-tracker as `ij_bins_full_v1` (inject-only,
  NOT in the sync whitelist). Both derive from the same `Bin` row; the tracker persists its rich write back to `ij_bins_v1`.
  `apply_bins` accepts BOTH (`status` wins over `state`) and is strictly **present-key-only**, so a lean write never blanks a
  rich field it omits — this is the one guard that keeps the two shapes from clobbering each other. The `Bin` model already
  carried every rich column (its docstring calls out the three-shape unification); only the two adapters needed widening.
- **Alembic + shared `brand` enum:** autogenerate emits inline `sa.Enum('victoria','nanaimo', name='brand')` in every new
  migration — hand-edit to a module-level `postgresql.ENUM(..., name='brand', create_type=False)`. New enums: create once
  with `checkfirst=True` + `create_type=False` on columns (see the `reminder_kind` migration).
- **Owner is `brand=NULL`** (shared). Any brand-scoped employee lookup MUST include brand-null
  (`or_(brand==b, brand.is_(None))`) or you duplicate the owner.
- **Brand resolution (post brand-switching): NEVER write `emp.brand or Brand.victoria` again.** Reads/actions resolve the
  working brand via `app.api.deps.active_brand_for(request, emp)` (owner → `session.active_brand`, crew → locked
  `emp.brand`); served pages via `optional_brand(request, db)`. **Writes (sync) use the PAGE's brand** (`body.brand` /
  `window.__IJ_BRAND`), and the sync endpoint **hard-forces crew to `emp.brand`** — a page can never write another brand
  for locked crew. New owner endpoints must thread `request` + use `active_brand_for`, not the old hardcode. (day-board +
  booking are the two still on the old path — calendar-bound, intentionally deferred.)
- **ORM registry:** `app/models/__init__.py` is intentionally EMPTY (avoids a base→types→enums cycle). Import
  `app.models.all` to register every model; `new_session()` + Alembic env + `app.main` already do.
- **Python 3.14 (bleeding edge):** plain `uvicorn` (not `[standard]`), `psycopg[binary]`, `pbkdf2_sha256` (not bcrypt),
  `tzdata` (Windows has no tz DB), and **`openpyxl`** (xlsx import). All in `requirements.txt`.
- **Refs vs sync:** refs inject inline in `<head>` (synchronous, before prototype scripts → no echo); `sync-bridge.js`
  overrides `localStorage.setItem` at end of `<body>` → only *user* writes sync, and only for the `SYNCED` whitelist keys.
  A builder returning `None` is skipped (no half-empty blob).
- **Windows console renders `—` / `·` / `≥` / `≤` as `�`** in Bash output (DB stores correct UTF-8) — prefix Python one-liners
  with `PYTHONIOENCODING=utf-8` when printing those. TestClient prints a harmless "httpx deprecated" warning.
- **PII stays out of git:** `.gitignore` excludes `.env`, `**/service-account-key.json`, `**/.venv/`, `spike/out/`, and
  customer exports (`*Customers*.xlsx` / `*.csv`). Verified: `.env`, the key, and `Victoria Customers.xlsx` are ignored.

---

## 6. HOW TO RESUME

**Prereqs in place:** `.env` (Render `DATABASE_URL` + `SESSION_SECRET`), `spike/service-account-key.json` (Google creds).
The Render DB is already migrated + seeded — steps 3–4 are only for a fresh DB.

```bash
# from repo root (Windows paths; .venv already exists)
.venv/Scripts/python.exe -m pip install -r requirements.txt          # 1. deps (incl. openpyxl)
.venv/Scripts/python.exe -c "import app.main; print('imports OK')"    # 2. sanity
.venv/Scripts/alembic.exe -c alembic.ini upgrade head                # 3. migrate (head = d83e4b664737)
# 4. seed (fresh DB only, IN THIS ORDER — colour_trucks needs trucks+colours):
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

Login: **Manager / 1111** or **Wes (owner) / 4321**. In browser tests, the owner hub's second gate (owner password + sim
2FA) can be skipped by calling `unlock()`; prefer the API for auth (`POST /auth/login {pin, brand}` sets the cookie).

**Safety still in place (confirmed this session):** the `app/integrations/gcal.py` guard refuses the two live calendar IDs
and writes only to the configured TEST + reminder calendars; `.gitignore` protects `.env`, the service-account key, and
customer PII exports.
