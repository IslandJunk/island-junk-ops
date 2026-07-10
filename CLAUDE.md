# CLAUDE.md — Island Junk Operations App (Build Brief)

This repo is the production build of the Island Junk internal operations app. It replaces Workiz.
The prototypes in `/prototypes` are the visual + behavioural reference — every screen has already been
designed and approved there. Your job is to turn them into a real, multi-user, backed app **without
changing how anything looks or behaves**.

Start with **Victoria only**. Nanaimo is a second workspace added later (see §13). Build brand-aware
from day one so Nanaimo drops in without a rewrite.

> **READ THIS FIRST — do not start a new app from scratch.** The app already exists as finished,
> approved HTML screens in `/prototypes` (listed in §12). Every screen is designed and signed off.
> You are **porting** these to a backed multi-user app, not reinventing them. Open each prototype file
> and reproduce its layout, wording, and behaviour. All the files are already in this repo — you never
> need to ask anyone to upload them; read them directly with your file tools.

## 0. Reference documents (authoritative — already in this repo)

These sit beside this file. This brief is the overview; where a spec goes deeper, **the spec wins.**

- **`island-junk-SPEC-login-sessions-and-access.md`** — locked spec for login, sessions, autosave, device
  types, logout behaviour, the overnight safety net, and the roster/access model. Authoritative for §3.
- **`island-junk-SPEC-scheduling-and-dispatch.md`** — locked spec for how the app reads Google Calendar:
  colour = truck, recolour = reassignment, vertical stack = route order, headline = time (fixed
  7:30am–3:30pm, parser + safeguard), per-truck reassignment-notification toggles, and the read-vs-write
  table. Authoritative for §6.
- **`island-junk-SPEC-sms-and-texting.md`** — locked spec for customer texting: one shared send-only
  "updates" line for both brands, the manager's main lines left untouched, reply auto-routing, and the
  Canadian number/compliance rules (this **supersedes any "A2P 10DLC" wording** below). Authoritative for §10 SMS.
- **`island-junk-CURRENT-VERSIONS.md`** — the living index of the latest version of every prototype. If
  it and §12 ever disagree, trust this index (it's maintained continuously).

---

## 1. What this app is

An internal, phone-first ops tool for a junk-removal + roll-off-bin-rental company. It runs:
bookings, dispatch, bin tracking, residential pricing, job photos, and customer texting — for two
brands (Island Junk Solutions / Victoria, and Island Junk Nanaimo). Owner does all invoicing and
card charging **by hand**; the app only surfaces what's ready.

Roles the app serves: **Manager** (books jobs, assigns trucks, enters details), **hands-on crews**
(load junk, collect residential, fill job details), **bin-truck drivers** (drop/pick bins), **yard crew**
(weigh, sort, classify waste), **owner/Wes** (invoicing + charging, all manual).

---

## 2. HARD GUARDRAILS — never violate

1. **Never touch the live Google Calendars.** Read only. Never create/edit/move/recolour/delete an
   event or change settings/sharing on:
   - ISLAND JUNK VICTORIA — `c_f35b41c1bf665fba2fef6fd34c0581a41c682867550cb30abf7228051622d987@group.calendar.google.com`
   - JOBS 2 — `c_77fcdcaa4570ff7ea0bf898fbd6153deed641acb49381380375c6555f6e9820e@group.calendar.google.com`
2. **All calendar write/sync testing happens on a dedicated TEST calendar only.** At go-live, a brand-new
   calendar is created and the crew migrated; the live calendar is never repurposed.
3. **Never automate invoicing or card charging.** The owner does both manually. The app surfaces a
   "ready to invoice" queue and prepares payment links — it never sends an invoice or charges a card.
4. **Never store full card numbers or CVVs.** The legacy calendar does this in event descriptions —
   replace with a Square payment link. Priority security fix.
5. **Crew names on every job are mandatory** and all job data is tracked permanently + searchably.
6. Outbound SMS runs from **one dedicated Canadian local "updates" line, shared by both brands** — send-only. The manager's main lines (Victoria 778-966-5865, Nanaimo 778-977-5865) are **never** hosted, ported, or sent from by the app. US A2P 10DLC does **not** apply (that's for texting US recipients). See the SMS spec.

---

## 3. Architecture — one app, two brand workspaces (NOT two apps)

Every record carries a **brand tag** (`victoria` | `nanaimo`). One codebase, one deploy, two datasets.
- **Owner** gets a Victoria ↔ Nanaimo switch; everything on screen follows it.
- **Crew/manager logins are locked to one brand** — no switch, no cross-brand mistakes.
- **Separate per brand:** Google Calendar, customers, rate card, area surcharges, bins, trucks,
  employees, Twilio texting number, Dropbox folder, invoice queue, price-sheet PDF library, Square location.
- **Shared:** the software itself + the owner account.

Login is **PIN-based per device**; the **owner login additionally carries 2FA**. Access management is
**owner-only** — the Manager Hub must not expose editing the owner's PIN, access flags, or account row
(enforce at the logic layer, not just hidden UI).

> **Sessions, autosave & device behaviour are fully specified in
> `island-junk-SPEC-login-sessions-and-access.md` — build to it.** In short: once signed in, a person
> stays signed in with **no idle timeout ever**; in-progress forms **autosave every field continuously**
> and are restored exactly after screen-off / app-kill / reboot; each device is set once as a **shared
> tablet** or **personal phone**, which is the only thing that changes logout (personal phone: clock-out
> ≠ logout; shared tablet: clock-out returns to login + a "Switch user" button); an **overnight safety
> net** forces a fresh PIN login if a session was left open from a prior day (mainly shared tablets);
> and form drafts are scoped **per job and per user** so a shared-device handoff never mixes work.

---

## 4. Tech stack (decided)

- **Backend/DB:** web app + **Postgres**, deploy on **Render** with automatic backups.
- **Calendar:** Google Calendar API — **read continuously; write ONLY at booking.** Source of truth is
  the calendar (see §5). Test against the TEST calendar exclusively.
- **SMS:** **Twilio**. One shared Canadian local **updates line** sends all automated customer texts for **both** brands (send-only); replies auto-route to the right brand's main line. No A2P 10DLC (US-only); no toll-free verification for a local number. See the SMS spec + §10.
- **Payments:** **Square** — payment links + Square API. (Switched from Clover.) Charging stays manual.
- **Photos:** **Dropbox API** (Wes's existing business account) — auto-file job photos per job. TEST
  folder first.
- **Books:** **QuickBooks** — manual invoicing. No live charging hookup. Customer import is via an
  uploaded QuickBooks export file (see §13), not a live sync.

Out of v1 scope (v2 later): Motive GPS, Notion, CallRail, Meta ad-conversion signals, Make.com writes.

---

## 5. Source-of-truth principle (do not break the revenue signal)

The **ISLAND JUNK VICTORIA calendar is already wired into a marketing automation stack via Make.com**
("the revenue signal"): Make reads job status (e.g. **Paid**) off the calendar and fires
ad-conversion + proximity-ad signals. A walled-garden replacement would break this.

Therefore: **the app augments the calendar, it never replaces it.** The calendar stays the manager's
working board. The app reads it, mirrors it, and writes to it **only at the moment a job is booked**.
Preserve the exact colours/statuses Make keys on.

---

## 6. Dispatch / calendar model (calendar-authoritative)

> Full detail — reassignment notifications (per-truck toggle), exact headline time format, parser
> safeguard, and the read-vs-write table — is in `island-junk-SPEC-scheduling-and-dispatch.md`. This is the summary.

The manager runs dispatch on Google Calendar after booking; the app reads/mirrors it.
- **Colour = which truck.** Recolouring an event **is** the truck reassignment.
- **Vertical stacking order on the calendar = route order.** Read events top-to-bottom exactly as the
  manager stacks them.
- **Time lives in the event headline, not the calendar slot.** Slots are positional/fake — ignore event
  start/end entirely. Time is never required; a single time = start only; a range = exact window.
- The app **never rewrites the headline** on recolour/reorder. The booking screen has its own optional
  time field that stamps a clean standard-format headline at creation.

> **HIGHEST-RISK UNKNOWN — prove this first, on the TEST calendar, before building anything on top:**
> reliably capturing the manual **top-to-bottom stack order** from Google Calendar. Everything in dispatch
> depends on it. Spike it, confirm it holds, then proceed.

### Colour → status lifecycle (store truck + status as separate fields; compute the Google colorId)
- **Stage 1 — Booked, coloured by assigned truck** (changeable up to & including job day):
  bin truck = Graphite/Lavender · hands-on truck = Peacock/Banana/Tangerine.
  **Sage is locked = Unassigned** (no truck picked yet; every new job starts sage).
- **Stage 2 — Crew completes, coloured by status:** Basil (done/on route) · Tomato (hands-on = chase
  e-transfer; bin = returned, now yard's responsibility — Tomato is intentionally overloaded, job type
  disambiguates).
- **Stage 3 — Owner closes out:** Grape (invoiced/charged) · Flamingo (residential bin awaiting CC
  charge; title also reads `CC? UNPAID (DATE)`).

The colour→truck map is editable in-app (Manager + Owner hubs), synced via one shared store, and now
supports Google Calendar's June-2026 colour set (24 defaults + custom named colours). Sage is a locked
Unassigned row and can't be assigned to a truck.

---

## 7. Data model (target)

- **Job** — id, brand, type (load | bin_drop | bin_pick | recurring | admin), account_type
  (residential | commercial | property_mgmt | residential_bin), assigned_truck, status, colour (computed),
  time window, address + geocode, customer ref, **crew (required)**, scope/items, est_time,
  est_price | quoted_price, equipment_needed[], photos[], on-site time, load size, %-breakdown, extras[],
  dump_fee, payment method/amount, invoice status, notes, linked Google Calendar event id.
- **Bin (asset ledger)** — code `SIZE-NUMBER` (e.g. 16-04, 20-32, 08-04), size, lidded flag, leased flag,
  status (in_yard/idle | reserved | dropped | full | returning | weighing | maintenance), current
  location/job, drop date, pick date, HQ-return time, gross/tare/net, waste class, roofing fields.
  **Real fleet = 75 bins**: 8yd×4, 12yd×16 (lidded), 16yd×11, 20yd×44. Eleven **ROSS** bins are leased
  to Nanaimo (own section): 20-10, 20-11, 20-14, 20-22, 20-29, 20-41, 20-44, 16-05, 16-06, 12-03, 12-04.
- **Customer / Crew / Truck** — editable references; never hardcode names. Crew includes Paul, Jesse,
  Brody (salaried), Zack, Riley, Owen, Ashton, + others. Fleet = 9 vehicles: Trucks #3–7 (Isuzu NPRs),
  Bin truck (Hino 2018), GMC 2000, Bobcat S185, Wacker Neuson excavator.
- **Rates / Area surcharges / Contracts / Colour map** — all editable per brand from the UI (see §9, §11).

**Tracking is maximal and permanent.** Assigned truck persists even after the colour moves to a status
colour (so "what did truck #6 do today" stays answerable). Everything searchable forever.

Prototype localStorage keys (become DB tables/rows, brand-scoped): `ij_rates_v1`,
`ij_company_customers_v1`, `ij_customers_v1`, `ij_pm_db_v2`, `ij_bins_v1`, `ij_colourmap_v1`,
`ij_fleet_v1`, `ij_employees_v1` + `ij_clock_log` + `ij_breaks_v1` + `ij_attendance_v1`,
`ij_incidents_v1`, `ij_maint_v2`, `ij_contracts_v1`, `ij_nanaimo_rates_v1` (area surcharges).

---

## 8. Booking workflow (manager)

Sources: phone, text, Facebook, email. Prompt for every field that gets forgotten today: customer name,
company (if commercial), phone, email, scope, est. time on site, est. or hard-quoted price, assigned
truck (sets initial colour), account type, equipment needed from yard (tools, blankets, straps, rolling
bins), and job photos (customers send these — bring them into the job instead of a separate Messenger group).

**Proximity popup (key feature):** when booking, surface other jobs already booked near that address
(day, size, type) so the manager can cluster routes and catch conflicts before confirming. In the
prototype this matches on the town in the address; **production geocodes the exact street address**
(Google Maps/Routes API) against zones — same screens, no rework.

**Custom Booking / Contracts flow is already built** (in the booking prototype): Saanich (RFQ 25-155) and
Oak Bay (GSA) seeded as custom customers with per-customer rate profiles layered over the rate sheet,
mandatory department picker per district, hourly billing mode, and UI to add custom customers with no
code edit. Municipal terms: Saanich $125/hr day, $225/hr after-hours/Sun/holiday, ¾-hr min, net 30;
Oak Bay $125/hr + dump/recycle + scale slip, $165/hr hazardous, net 30.

---

## 9. Pricing (in-app scope = residential + area surcharges)

- **GST 5% on everything.** 2.4% card fee applies to commercial + all bins; **residential hand-load is
  exempt** (calculator defaults the fee OFF).
- **Residential field calculator** (built): load size + on-site time + special-item steppers + custom
  "ask" lines → subtotal + GST + optional 2.4% → generates (a) the customer e-transfer text and (b) an
  internal job summary to paste into the calendar event. Crew collects on site.
  Load prices (flat, incl. travel/disposal/recycling/donation): min $75–95, 1/8 $150, 1/4 $225, 1/3 $275,
  1/2 $350, 2/3 $425, 3/4 $550, 7/8 $600, full $650. Specials: TV $5, tire $7, paint/chem/propane $25/crate,
  freon $20, mattress $15, concrete/soil $20/wheelbarrow min, drywall $25/bag then $415/ton, batteries/food = ask.
- **Area surcharges** (editable per brand, per service type): each area has a **hand-load $** and a
  **bin $** (either blank). **Auto-applied when the address matches an area; manager can one-tap skip it
  when the truck's already headed that way** (log the waive). Victoria: bin surcharges only today
  (hand-load flat). Nanaimo: both. Reference the built system in `island-junk-nanaimo-setup-rates-v1.html`
  and the existing Victoria bin-surcharge logic in the booking prototype.
- **Commercial, bin, roofing, pallet pricing stay as manager-sent collateral (PDFs)** — the app does NOT
  compute these. Keep the five PDFs in a per-brand library for texting to customers.
- **Disposal rate sheet is fully editable from the UI** (add/edit facilities + materials, set our-cost and
  customer-charge dump fees, ripple through forms, keep history). Cost model: customer charge by headline
  waste class; our cost on mixed loads = sum of sorted streams from Yard Processing; margin = charge − summed
  stream costs.

**Residential-bin payment rule (special):** residential bins are invoiced, 48 h to pay by e-transfer, else
the card on file is charged + 2.4%. The app creates a 48-hour CC-charge reminder on a separate reminder
calendar (kept off the main board) that the owner checks off. The charge itself is always manual.

---

## 10. Integrations — detail

- **Google Calendar:** two-way but **write only at booking**; read continuously for the board. TEST
  calendar only until go-live. Preserve Make.com's status signal.
- **Twilio (SMS), customer-facing only — full detail in `island-junk-SPEC-sms-and-texting.md`:**
  the app sends from **one shared, send-only "updates" line** (a fresh Canadian local number, both brands)
  — booking confirmation · "on our way" · **next-customer ETA** (crew-entered estimate, never raw map
  distance) · reminders · residential completion text (photo + price + GST + e-transfer email + "put your
  address in the memo"). Each message names its brand in the text. **Replies auto-route:** STOP/HELP handled
  first, then an "unmonitored line" auto-reply that points the customer to the right **main** line by
  recognising who they are (Victoria → 778-966-5865, Nanaimo → 778-977-5865, unknown → both). The
  manager keeps all real two-way texting on those main lines, untouched by the app.
- **Square:** payment links surfaced on the job; no auto-charge. 48-hour residential-bin rule above.
- **Dropbox:** auto-file each job's photos into a per-job folder in Wes's account. TEST folder first.
- **QuickBooks:** manual invoicing; customer import via uploaded export file (§13).

---

## 11. Completion flows by job type (from the prototypes)

- **Residential (hands-on):** collect on site (usually e-transfer). Calculator handles it. Colour green
  (done/on route) or red (awaiting e-transfer).
- **Commercial (hands-on):** invoiced, not collected. Crew fills time on site, load size, est. weight/dump
  fee, %-breakdown (junk/wood/recycle), extras. Colour green when done.
- **Bin pickup (driver):** return to yard; min required = HQ time + which truck; note billable extra time.
  Colour red → yard's responsibility.
- **Yard crew (bin processing):** weigh (official time, gross/tare/net → owner computes net), sort, record
  extras + %-breakdown → waste charge class. Roofing bins: top-down sort time, junk/metal amounts, roofing
  gross/tare/net, landfill dump price charged to us. **Yard Processing form** feeds the disposal cost model.
- **Owner invoicing (manual):** commercial, bins, sometimes residential. Colour grape when charged out.
  Surface a "ready to invoice" queue; never auto-invoice/charge.
- **Follow-up reviews** handled in-app by the followup-reviews tool. (NiceJob is no longer used.)

---

## 12. The prototypes are the spec for each screen

`/prototypes` holds the current, approved single-file HTML for every screen. **Match them exactly** for
layout, wording, flows, and the design system below. They use localStorage (becomes Postgres) with no
backend. Current files:

| Area | File |
|---|---|
| Main Hub (launcher + PIN login) | `island-junk-main-hub.html` |
| Owner Hub | `island-junk-owner-hub-v54.html` |
| Manager Hub | `island-junk-management-hub-v83.html` |
| Booking (+ Route Builder view) | `island-junk-new-booking-v67.html`, `island-junk-route-builder-v13.html` |
| Day Board (dispatch mirror) | `island-junk-day-board-v28.html` |
| Swing Board | `island-junk-swing-board-v5.html` |
| Truck Hub (crew) | `island-junk-truck-hub-v54.html` |
| Residential calculator (crew) | `CREW-residential-calculator-v25.html` |
| Commercial form (crew) | `CREW-commercial-form-v22.html` |
| Pallet flow (crew) | `island-junk-pallet-flow-v8.html` |
| Bin Tracker (driver) | `island-junk-bin-tracker-v34.html` |
| Bin Registry (fleet ledger) | `island-junk-bin-registry-v6.html` |
| Yard Hub | `island-junk-yard-hub-v19.html` |
| Yard Processing | `island-junk-yard-processing-v28.html` |
| Maintenance Hub | `island-junk-maintenance-hub-v12.html` |
| Clock-out / hours | `island-junk-clock-out-v9.html` |
| Reminders (CC-charge etc.) | `island-junk-reminders-v1.html` |
| Incident report | `island-junk-incident-report-v2.html` |
| Nanaimo setup — Rates card | `island-junk-nanaimo-setup-rates-v1.html` |
| Owner-side: Rate Sheet, Employee Hours, Estimate Builder | (Wes-side files) |

**Design system:** Anton headlines + Inter body. Orange `#F05014`, near-black `#141414`, paper `#F4F3F1`,
green `#3CA03C`, amber `#E8A317`. Phone-first. Crew never sees customer pricing on job forms.

---

## 13. Nanaimo — phase 2 (build Victoria first, drop this in later)

Nanaimo is a second **workspace**, switched on after Victoria is running. Spin-up: new Nanaimo dispatch
calendar → second Twilio number + its own A2P registration (2–3 wk) → Dropbox folder → Square location →
load data. Owner-only **"Set up this workspace"** screen (cards go green): ① basics ② calendar
③ **customer import = uploaded QuickBooks Customer Contact List export**, preview + untick, matched on
phone/email so re-imports never duplicate ④ **rates = "Copy Victoria's rate card" then edit differences**
(mostly area surcharges — the Nanaimo Rates card is already prototyped) ⑤ people & trucks ⑥ bins & colour
map ⑦ texting number.

---

## 14. Recommended build sequence

1. **Repo skeleton + Postgres + brand-tagged data model + PIN auth** (owner-only access guards at the
   logic layer). No integrations yet.
2. **Google Calendar TEST-calendar spike** — prove the top-to-bottom stack-order capture (§6), read the
   board, write a single booking. Do not build dispatch features until this holds.
3. **Booking screen** — the entry point; it's the only thing that writes to the calendar.
4. **Hubs + field tools reading real data** — Manager/Owner/Truck/Yard hubs, bin tracker + registry,
   residential + commercial forms, yard processing, maintenance, incident, reminders.
5. **Wire integrations** — Twilio (once A2P live), Square payment links, Dropbox photo filing.
6. **Nanaimo workspace + setup screen** (§13).

---

## 15. The never-list (quick reference)

Never write to a live calendar. Never auto-invoice or auto-charge. Never store full card numbers/CVVs.
Never let a job save without a crew name. Never hardcode staff/truck names. Never show customers a
staging URL or the wrong-brand phone number. Never mix Victoria and Nanaimo data. Never break the
calendar status signal Make.com reads.
