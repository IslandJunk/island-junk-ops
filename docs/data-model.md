# Island Junk — Data Model (v0 design)

**Status:** derived from the approved prototypes + locked specs by a full extraction pass.
This is the target Postgres model for the backed multi-user app. It is a *design*, not yet
migrated — the **[Open decisions](#open-decisions-need-wes)** at the bottom gate finalising the
contested tables (jobs, bins, colour seed). Auth/identity/reference tables are being built first.

Source specs win where they go deeper: `island-junk-SPEC-scheduling-and-dispatch.md`,
`island-junk-SPEC-login-sessions-and-access.md`, `island-junk-SPEC-sms-and-texting.md`, and CLAUDE.md.

---

## Conventions (apply to every table)

- **Brand scoping (CLAUDE.md §3):** every operational table carries `brand ENUM('victoria','nanaimo') NOT NULL`.
  The **only shared/global rows** are the **owner employee** and **owner-security** (brand-null). Crew/manager
  rows always carry exactly one brand. *No prototype store is brand-scoped today* — this column is a production addition everywhere.
- **Type casting:** prototypes store numbers, dates, and times as **strings** from text inputs
  (`gross:"7600"`, `dumpFee:"165.00"`, `date:"2026-07-08"`, time `"7:30am"`/`"HH:MM"`), timestamps as ms-epoch or ISO.
  Cast to real `numeric` / `date` / `time` / `timestamptz` on import.
- **Keys:** add surrogate PKs (UUID). Natural keys that are join keys today are kept `UNIQUE per brand`
  (bin `code`, employee `name`) — but real FKs replace name-matching.
- **Photos:** base64 dataURLs in prototypes → **Dropbox file references** in prod (TEST folder first).
- **Calendar is source of truth for jobs** (colour=truck, vertical stack=route order, time=headline).
  The app **writes only at booking**; everything after is a read/overlay keyed on `gcal_event_id`.

---

## Domain A — Identity, access, sessions, shared references

### `employee` (`ij_employees_v1`) — brand-scoped (owner row = shared)
Login + access source of truth. Union of the three prototype seeds (Owner Hub is richest):

| Field | Type | Notes |
|---|---|---|
| id | uuid PK | prototype matches by `name`; add stable PK, migrate FKs off name |
| brand | enum | null/all-brands for the owner only |
| name | text | display + current join key |
| role | text | free-text, pattern-matched (`/owner/i`,`/manager/i`,`/yard/`,`/bin/`) — keep substrings meaningful. Seen: Owner, Main manager, Truck manager, Yard manager, Truck crew, Bin truck driver, Yard crew, Crew |
| pin | text hash | 4-digit, digits only. **Hash it** (pbkdf2); rely on server-side rate-limit/lockout since the space is only 10k |
| access | text[] | feature flags (see enum below) |
| active | bool | false = login off, history kept |
| time_tracked | bool | (`tracked`) false for Owner + Main manager → excluded from punch clock/payroll |
| pay_type | enum | salaried \| hourly (replaces loose `salaried` bool) |
| can_clock_others | bool | managers/owner |
| see_all_trucks / edit_all_trucks | bool | Day Board reach; edit⇒see |

**Access-flag canonical list (proposed — resolves the 3-way drift):**
`owner, manager, estimate, truck, yard, yardhub, bin, binreg, maint, hours, swing, reminders`
(`yard`≠`yardhub`, `bin`≠`binreg` are intentionally distinct: crew lane vs hub). **Owner-only-grantable:** `owner`, `estimate`, `swing`.

**Owner-only guard (CLAUDE.md §3 — enforce at logic layer, verified real in prototype):** Manager Hub guards
every employee mutator with `isOwnerRow()` (role contains "owner") → cannot edit the owner's name/PIN/access/active.
Owner Hub is the only place the owner's own PIN/access/reach are edited. **Replicate server-side**, not just hidden UI.

### `owner_security` (`ij_owner_sec_v1`) — **GLOBAL / shared, not per-brand**
Owner Hub gate. `password` (separate from the owner's 4-digit employee `pin` — owner has both),
`phones jsonb[]` (2FA destinations), `backup_codes jsonb[]` (one-time), `audit_log jsonb[]` (owner actions, capped 500).

### `session` + `device` (`ij_session_v1`; device model is spec-only, unbuilt)
Prototype has only a coarse 16-h timed session (`{name, at}` + `ij_session_hours_v1`, default 16). The real model from
`island-junk-SPEC-login-sessions-and-access.md` must be built fresh:
- `device`: `{id, brand, type ENUM('shared_tablet','personal_phone') [set once], label}`.
- `session`: `{id, employee_id, device_id, started_at, last_seen_at}`. **No idle timeout ever.**
  Logout depends only on `device.type`: personal phone → clock-out ≠ logout, persists across days;
  shared tablet → clock-out returns to login + "Switch user". **Overnight safety net** forces fresh PIN if a
  session spans a prior workday (mainly shared tablets).

### `form_draft` (spec-only, unbuilt) — continuous autosave
Not in any prototype. Scoped **per (job_id, user_id, form_type)** so a shared-device handoff never mixes drafts.
Every field autosaves continuously; restored exactly after screen-off/kill/reboot.

### `colour_map` (`ij_colourmap_v1`, `v:3`) — brand-scoped, live-synced across hubs
Row per Google colour: `{key, name, hex, google_color_id, assigned_truck fk|null}` +
`custom jsonb[]` (June-2026 custom named colours) + `names jsonb` (renames of classic colours) + `history jsonb[]` (change log).
- **Assignable (6):** lavender(1), banana(5), tangerine(6), peacock(7), graphite(8), **blueberry(9)**. Bin truck = **Graphite/Blueberry** (DECIDED); hands-on = Tangerine/Peacock/Banana.
- **Status-locked (4):** basil(10)=done/on-route, tomato(11)=waiting e-transfer/bin-returned, grape(3)=invoiced, **flamingo(4)=residential unpaid — bin CC *or* e-transfer** (DECIDED — status only, never a truck). Make.com keys on these.
  - **Residential e-transfer lifecycle (DECIDED 2026-07-09):** Tomato = Stage-2 "waiting" (crew just finished, payment expected) → flips to Flamingo = Stage-3 "unpaid" once overdue and needing owner chase/charge. A residential *bin* awaiting its 48h CC window goes straight to Flamingo (`CC? UNPAID (DATE)`). Tomato also still means "bin returned to yard". This transition is computed in the jobs layer.
- **Unassigned-locked (1):** sage(2) — every new job starts here; never assignable.

### `truck` (`ij_fleet_v1`) + `truck_alert_pref` (`ij_truck_alerts_v1`) — brand-scoped
- `truck`: `{num, mgr(lead name), colour_key}`. Seeded dispatch trucks 3,4,5,6,7,12 (3–7 NPRs, 12 bin). *(See decision #4 re: full vehicle list.)*
- `truck_alert_pref`: per-truck notification toggles `{reassign, swap, metal, weigh}` (absence=on). `reassign` = the scheduling-spec reassignment alert toggle.

### Time & attendance — brand-scoped
- `clock_punch` (`ij_clock_log`): `{employee_id, work_date, in_at, out_at, done_at, truck_id}`. (`done_at`=end-of-day checklist; gap=out−done.)
- `break_log` (`ij_breaks_v1`): per employee/date `{total_min, sessions:[{min,method,at}]}`; + `ij_breaks_active_v1` running state.
- `attendance` (`ij_attendance_v1`): per date/employee `{status, note}`. status ∈ yes|late|sick|vacation|stat|off|noshow|other (sick/vacation/stat = paid leave). *Writer path to confirm.*
- `clock_schedule` (`ij_clock_schedule_v1`): default start per crew {Yard 07:00, Truck 07:30, Bin 07:30} + per-person overrides.
- `signin_log` (`ij_signin_log_v1`): audit `{name, role, access, at}` capped 300.

---

## Domain B — Jobs, booking, dispatch, customers, contracts, rates

### `job` — the calendar-mirrored core (brand-scoped)
The booking screen is the **only** calendar writer; the prototype builds a **calendar-event text summary**, not a row.
The fields those builders capture ARE the job model:

- **Identity/link:** `id, brand, gcal_event_id, type (see decision #2), account_type ENUM(residential|commercial|property_mgmt|residential_bin), booking_lane`.
- **Dispatch (read from calendar):** `assigned_truck fk|null`, `status`, `colour_id (computed, never stored as truth)`,
  `stack_order int (vertical order)`, `headline text (carries time)`, `time_start/time_end (nullable — never required; null=untimed)`.
- **Customer:** `customer_ref` (poly → residential_customer | company_customer | pm_building | contract) + denormalized `customer_name/phone/email` snapshot, `address (+geocode)`, `area/town`.
- **Scope/pricing:** `scope`, `est_price`, `quoted_price (hard-quote overrides est)`, `crew (MANDATORY §5)`,
  `equipment_needed jsonb[]`, `photos jsonb[]`, `recurring jsonb`, `demolition jsonb`, `out_of_zone_travel jsonb`,
  `old_materials_gate jsonb (haz/asbestos — unset ⇒ NOT CONFIRMED)`, `po jsonb`, `notes`.
- **Bin-job extras (type=bin):** `bin_action ENUM(drop|pickup|swap)`, `bin_type ENUM(Regular|Roofing|Fill/Concrete|Yard Waste|Demo)`,
  `bin_size ENUM(8|12|16|20 yd)`, `bin_out_code (fk bin.code)`, `paired_stops jsonb[]`, `bin_rental_quote (base+area, computed)`.

### `job_dispatch_state` (day-board overlays, keyed by job/event id)
Because the app never rewrites the calendar, crew edits live separately: `ij_dayboard_status_v1` (status override),
`ij_dayboard_notes_v1` (crew notes), `ij_dayboard_sitelog_v1` (contract `{start,finish,finish_location:yard|landfill|next}`). Model 1:1 on `job`.

### Customers
- `residential_customer` (`ij_customers_v1`): `{first,last,phone,email,addr}`; dedupe = digits-only phone else `first|last`. (Prod: QuickBooks import.)
- `company_customer` (`ij_company_customers_v1`): `{co,name,addr,contact,phone,email,accounts text[],src ENUM(seed|app|qb)}`; dedupe lowercased `co`.
- `pm_company / pm_group / pm_building` (`ij_pm_db_v2`): 3-level PM tree; booking auto-files a new address as a building under the matched company.

### `contract` (`ij_contracts_v1` + built-in constants) — custom customers / municipal
Keyed by slug; built-ins (Oak Bay, Saanich, Longhorn, CRD Trails, EMCON, MCA, CheckSammy) are runtime constants, user adds overlay.
`{key,name,short, pricing ENUM(commercial|hourly|flatmonthly|flatjob), rateKey→rate_customer, divisions text[], routeDivs text[],
divAddable bool, extra ENUM(scale|location|trail|property)|null, bin bool, poReq bool, siteLog bool, shots text[], terms, rates jsonb[], flat, flatUnit, properties jsonb[], note}`.
Municipal terms: Saanich $125/hr day · $225 after-hrs/Sun/holiday · ¾-hr min · net 30. Oak Bay $125/hr + dump/recycle + scale slip · $165 hazardous · net 30.

### Rates (`ij_rates_v1` — one blob today → decompose; make this the single source, drop hardcoded fallbacks)
- `rate_card` scalars: labour 125, demo 165, crew-extra 62.5, recycle 25, diversion surcharge 45 / report 100, gst 5%, card fee 2.4%, parking {cost 3.25/chg 5}, travel {rate 95, roundTrip, minMin}.
- `load_price`: residential {1/8:150 … full:650} + min {75/85/95}; commercial {min:75 … full:550} + included-minutes.
- `special_item[]` {n,price,unit} (TV 5, tire 7, mattress 15, freon 20, paint 25/crate, drywall 25/bag, concrete 20/wheelbarrow, battery=ask).
- `ppe_item[]` {n,price,unit}. `bin_rate` {base 225, roofingBase 250, extraDay 10, maxTonnes 4} + yardWaste {12yd:40,16:75,20:100}.
- `rate_customer[]`: per-custom-customer rate profiles (Saanich, Oak Bay) — links to `contract.rateKey`.
- **Disposal** (`facilities[]`, `disposal[]`) → see Domain C.

### `area_surcharge` + `surcharge_waiver` (adopt the richer Nanaimo shape for BOTH brands)
`area_surcharge {id, brand, area_name, aliases text[], hand_amount numeric NULL, bin_amount numeric NULL, is_base bool}`.
Victoria today = **bin surcharges only** (hand-load flat); Nanaimo = both. Auto-applied on address match; **one-tap waivable when the truck's already headed that way** →
`surcharge_waiver {job_id, area_id, kind, waived_by, at}` (log the waive — a §7 addition).
*(⚠ The Nanaimo rates prototype `island-junk-nanaimo-setup-rates-v1.html` is **referenced but not present in the repo** — only its store shape is documented. Flag.)*

### Crew field forms → job completion
- **Residential calculator** (`CREW-residential-calculator-v25`): load size + on-site minutes + item/PPE steppers + custom "ask" lines + pay method + card-fee toggle (default **OFF** — residential hand-load exempt) + hard-quote override → `{sub, gst, fee, total}` + e-transfer text.
- **Commercial form** (`CREW-commercial-form-v22`): crew[] + trucks[], job timer, `loads[]`, items (required), **6-stream %-breakdown** (junk/wood/metal/concrete/drywall/recycle — §7 says 3; widen), dump fee + weight + unit, extras, PPE, demo, `weighs[]` axle weights, photos {Before|After} → office/invoice summary. No card collection.
- `field_job` / `field_visit` (`ij_jobs_v1`): multi-day accumulated on-site record that rolls up to one invoice. **Link to calendar `job` is unmodeled today (customer-name coupled)** — add FK.

### `route` / `route_stop` (`route-builder-v13`)
`route_stop {id, addr, desc, wo, photo, truck(colour key)}`; a route = one call, many stops split across trucks (one truck = one calendar event). Prod uses Google Route Optimization.

---

## Domain C — Bins, yard/disposal, maintenance, incidents, reminders

### `bins` — unify the THREE divergent prototype shapes (highest-priority reconciliation)
`ij_bins_v1` is written by **bin-registry** (`state` model) and **yard-processing** (writes back `state`,`cleared`), while
**bin-tracker** (the richest driver tool) uses a different `status` model and **never persists** (in-memory only — a prototype gap).
Merge into one table; natural key `code` (`SIZE-NN`, e.g. `16-04`):

- **Identity:** `code, size smallint(8|12|16|20), lidded bool (all 12yd + customLid), leased bool (11 ROSS→Nanaimo: 20-10,20-11,20-14,20-22,20-29,20-41,20-44,16-05,16-06,12-03,12-04), stationed bool, type text, roofing bool, condition {flag,note,photos}`.
- **Assignment:** `customer, address, town, job_id fk` (proto has no link — add).
- **Rental/dates:** `drop_date(=outAt), drop_time, pick_date(=inAt), scheduled_pickup, hq_time, last_dumped, yard_at, base numeric, surcharge numeric`. Billable-day rule: weekdays strictly between drop&pick, first 3 free, weekends + BC stat free, ~$10/day extra, **never auto-charged**.
- **Weigh/disposal:** `gross,tare, gross_f/r,tare_f/r (axle kg), waste_class fk→disposal_materials, dump_fee, fee_split jsonb, extra_time, pickup_by, dump_by, sort_junk/metal, sort_minutes, no_sort, cleared jsonb, notes, photos, contact_log jsonb, repair_note/open/at`.
- **Real fleet = 75** (8×4, 12×16 lidded, 16×11, 20×44) — matches §7. ✓
- **Status enum (proposed merge):** `idle, reserved*, dropped, returning, returned, to_sort, clearing, ready_dump, weighing*, full*, stationed, maintenance, retired`. `leased`/`stationed` stay **flags**, not statuses. (*in §7 but absent from every prototype — decision #3.)

### `yard_processing` — disposal-margin record (prototype keeps it in-memory only → MUST persist)
One row per bin OR hand-load processed. `{code, ref, type ENUM(bin|handload), size, roofing, customer/address/town, pickup_by, truck, hq_time, pick_date, crew text[] (MANDATORY), crew_count, gross_f/r,tare_f/r,gross,tare, waste_class, pct jsonb(junk/wood/drywall/concrete/metal/recycle %), extras jsonb, custom_extras jsonb, contamination, process_notes, dump_by, dump_fee, sort_junk/metal, no_sort, sort_minutes, weighed, weigh_clock, weighed_by_truck, processed/_date/_clock, photos}`.
**Cost model:** customer charge = headline `waste_class` price; our cost (yard-sort classes) = Σ(stream% × stream cost); margin = charge − summed cost.
Supporting: `weigh_log` (`ij_weighlog_v1` append-only truck+bin weights), `tares` (`ij_tares_v1` saved empties keyed `truck|bin`), `weighins` (`ij_weighins_v1` HQ pre-weighs).

### Disposal rate sheet (`ij_rates_v1` → two tables; owner-only)
- `disposal_facilities {name, role ENUM(cost|income|free|sort), note}` (Hartland, DL Disposal, McNutts, Waste Connections, Williams Scrap, Bottle Depot, Yard sort).
- `disposal_materials {m, fac fk, cost numeric NULL, price numeric NULL, unit, note}` (~24 rows; blank cost = computed from streams).
- **`disposal_rate_history`** (effective-dated) — **§9 requires history; prototype has none. Add.**
- ⚠ The hardcoded 13-value `WASTE_CLASSES` list overlaps but ≠ `disposal_materials.m` — **drive the picker from the materials registry** (one source).

### `maintenance` (`ij_maint_v2`) → `maintenance_asset` + `maintenance_item` + `maintenance_history`
- `maintenance_asset {kind ENUM(truck|machine|model), label, unit ENUM(km|hours|time), reading, reading_on, specs jsonb, parts jsonb, model_ref, vin, plate, serial, motive bool}`.
- `maintenance_item {asset_id, id, name, by ENUM(km|hours|time), interval, lead}` (due-status computed, not stored).
- `maintenance_history {asset_id, id, name, on, reading, by}`.
- **`defect_flag`** (`ij_fixes_v1`): bridges daily walk-arounds → repairs `{id, truck, item, note, who, date, open, source:'walk-around'}` (truck-hub writes, yard-hub closes).
- Seeds real fleet trucks #3,4,5,6,7,12 + Bobcat + excavator + Isuzu/Hiab models. **Names/numbers are demo — never hardcode.**

### `incident` (`ij_incidents_v1`)
`{id, at timestamptz, type ENUM(injury|property|vehicle|near_miss|hazard|customer|other), sev ENUM(minor|serious|emergency), told, by (req), who, date, time, where (req), truck, what (req), action, photos (≤6)}` + brand + optional FK to job/truck/bin.

### `reminder` (`ij_reminders_v1`) — shared store, marking done = delete
`{id, text, by, ts, due date, done bool, booking bool, name, addr, draft jsonb}` (booking drafts render "Resume booking").
⚠ **The 48-h residential-bin CC-charge reminder (§9/§11) is NOT built.** Add: `reminder_kind ENUM(general|cc_charge|booking_draft)`,
a `calendar` field (CC-charge reminders live on a **separate off-board reminder calendar**), auto-create on residential-bin completion `due=drop+48h`, owner check-off. **Charge stays manual** (guardrail §2.3).

---

## Open decisions (need Wes)

These gate finalising the contested tables. Auth/identity/reference tables don't depend on them and are being built first.

1. ~~**Colour semantics**~~ **RESOLVED (2026-07-09):**
   a. **Flamingo(4) = STATUS only** — residential unpaid (bin CC **or** e-transfer); never truck-assignable.
   b. **Bin truck = Graphite/Blueberry**; Lavender stays a free assignable colour (not the bin truck). Seeded in `colour_map`.
2. ~~**Job-type taxonomy**~~ **RESOLVED (2026-07-09):** modeled as `booking_lane` (the 7 real lanes) + `account_type` + bin `action(drop|pickup|swap)`; §7's flat 5-value `type` retired. Built in the `job` table.
3. ~~**Bin lifecycle enum**~~ **DECIDED (2026-07-09):** merged set built as `BinStatus` (kept §7's `reserved`/`full`/`weighing`); `leased`/`stationed` are flags, not statuses. Built in the `bin` table.
4. ~~**One vehicle table vs separate**~~ **DECIDED (2026-07-09):** the dispatch `truck` table is separate (built). Non-dispatch equipment (GMC, Bobcat, excavator, bin-truck identity) + maintenance records go in a later `vehicle` table (maintenance domain). Revisit only if a unified asset view is needed.
   - Still needed: the **bin truck's real dispatch number/label** (prototype's "12" is demo) — not seeded.
5. **Access flags:** confirm the canonical 12-flag list + owner-only-grantable set (`owner`,`estimate`,`swing`); the orphan `reminders` value — keep?
6. **Open data:** bin **`3'3`** (Wes mentioned it — size/code?), and the **real crew roster** (all prototype names are demo per the spec).
7. **Missing file:** `island-junk-nanaimo-setup-rates-v1.html` is referenced in CLAUDE.md/CURRENT-VERSIONS but **not in the repo**. Provide it, or is the documented store shape enough?
