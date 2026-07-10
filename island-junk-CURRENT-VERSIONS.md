# Island Junk — Current Versions & Handoff

_Single source of truth for the latest build of each tool. Last updated: **2026-07-01** (post feature batch: incident report, backup, bin days, haz gate, hard quote, crew gear, surcharge, return-customer, go-live PDF)._

---

## ✅ Canonical — use these

| Tool | Current file |
|---|---|
| **Main Hub** (launcher + login) | `island-junk-main-hub.html` |
| **Booking** (manager front door) | `island-junk-new-booking-v67.html` |
| **Manager Hub** | `island-junk-management-hub-v83.html` |
| **Owner Hub** | `island-junk-owner-hub-v54.html` |
| **Day Board** (dispatch) | `island-junk-day-board-v28.html` |
| **Bin Tracker** (driver) | `island-junk-bin-tracker-v34.html` |
| **Bin Registry** | `island-junk-bin-registry-v6.html` |
| **Yard Hub** (manager) | `island-junk-yard-hub-v19.html` |
| **Yard Processing** (yard crew) | `island-junk-yard-processing-v28.html` |
| **Maintenance Hub** | `island-junk-maintenance-hub-v12.html` |
| **Swing board** | `island-junk-swing-board-v5.html` |
| **Truck Hub** (crew) | `island-junk-truck-hub-v54.html` |
| **Pallet flow** (crew) | `island-junk-pallet-flow-v8.html` |
| **Route Builder** (embedded in booking) | `island-junk-route-builder-v13.html` |
| **Clock-out** | `island-junk-clock-out-v9.html` |
| **Reminders** | `island-junk-reminders-v1.html` |
| **Incident Report** | `island-junk-incident-report-v2.html` ← v2: **photo attachments** (was missing entirely before this batch) |
| **Crew — Commercial form** | `CREW-commercial-form-v22.html` |
| **Crew — Residential calculator** | `CREW-residential-calculator-v25.html` |
| **Rate Sheet** | `island-junk-rate-sheet-v14.html` *(Wes-side)* |
| **Employee Hours** | `island-junk-employee-hours-v6.html` *(Wes-side)* |
| **Estimate Builder** | `island-junk-estimate-builder-v4.html` *(Wes-side)* |
| **Go-live guide** | `island-junk-GO-LIVE-signup-guide.pdf` ← **NEW** |

---

## Feature batch — 2026-07-01 (all shipped + verified)

1. **Incident Report built (v1 → v2 same day)** — was missing; all 8 linking tools resolve. Type/severity/manager-told chips, who/when/where/truck, what-happened + action, **photos: up to 6 per report, auto-shrunk, thumbnails on past reports, tap to enlarge, storage-full guard**. Saves to `ij_incidents_v1`.
2. **Owner Hub v51 — Backup & restore is real.** One tap downloads `island-junk-backup-‹date›.json` with every app store; restore replaces and reloads. Do it after any big day.
3. **Bin rental-day counter** (Bin Registry v5) — every bin with a drop date shows billable weekdays (BC stat holidays + weekends free), first 3 included, extras at $10/day shown as "charge if you want" — never auto-charged. Day Board v28 stamps the return date so finished rentals show a **final** count.
4. **Booking v66 — old-materials gate.** Auto-arms when drywall/demo/plaster/lino/reno words appear in scope (hand-load + bins), or manual. Manager picks: paperwork on file / plan in place / **book testing with us** (same-day $125 first + $80 ea · 24-hr $110/$65 · 4–5 day $85/$45 — flows onto the summary as an invoice add-on). Nothing picked → books flagged **NOT CONFIRMED**.
5. **Booking v66 — bin area surcharge autofill.** Town auto-picked from the address; rental total shown under Area (regular $225 / roofing $250 base + the sheet's surcharge tables — they differ for Sooke); goes on the calendar summary as BIN RENTAL.
6. **Booking v66 — return-customer autofill by phone.** 7+ digits typed in Phone matches past bookings and pulls name, contact & address (on top of the existing name match). Name field also autocompletes from all saved customers.
7. **Hard-quote price field** (Res v25 + Comm v22) — confirmed it was never built before; now it is. Residential: toggle + amount overrides the calculated subtotal, GST on top, breakdown + e-transfer text read "Flat quoted price". Commercial: HARD QUOTE line on the office summary (single- and multi-day) so invoicing uses it.
8. **Truck Hub v54 — crew sees job gear.** Job rows show a 🧰 flag; the peek shows a bold **"Bring:"** card with the job's equipment; opening tool sign-out **pre-loads** the day's job gear (deduped) so they sign it out in one pass.
9. **Go-live signup guide PDF** — Twilio (toll-free verification, 2–3 weeks — start first), website privacy/terms/consent wording, Square, Google Cloud + TEST calendar, Dropbox app, hosting. Costs + timeline table.

**Verification:** full relink sweep · 19/19 files JS-clean, zero encoding errors, **zero stale links** · 19/19 live-load smoke PASS.

10. **Owner Hub v52 — payroll export is fully dynamic.** Victoria rows rebuild from the live Access & people list on every download (name written to both day columns, unused template rows wiped — stale names and their data can't linger). Only the owner is excluded; inactive staff drop off automatically. 14 rows per day on the sheet — a toast warns if the roster ever exceeds it. Nanaimo sheet keeps its template names by design until the Nanaimo workspace exists.
11. **Booking v67 — freon / mattress nudge.** Both hand-load flows watch the scope; type fridge/freezer/AC/water-cooler or mattress/box-spring words and an amber "Heads up" card appears with the price and a one-tap **+ Add 1 to extras** that drives the real item picker (collect `#eItemPick`, invoiced `#estExtra`) — so it lands in the price and the crew sheet. Clears itself when the words leave the scope. Bins flow excluded by design (special-item fees are caught at Yard Processing).
12. **Bin Tracker v34 — dump-fee split** on the pickup direct-dump close-out. "This load had more than one job's material" reveals per-job rows (first row prefills the bin's customer), live tally shows assigned vs unassigned against the fee, add-as-many-jobs, blanks filtered on save. Stored as `feeSplit:[{job,amt}]` on the bin record next to `dumpFee` — capture-only for now; the invoice queue (and the real build) read it from there. **Also fixed:** v33's Pick-up form crashed on open (template referenced `b` before it existed) — v34 binds the selected bin properly.

**Verification (wave 2):** owner v52 / booking v67 / bin-tracker v34 node-clean, zero U+FFFD · functional smokes PASS (roster writer: owner + inactive excluded, stale rows wiped · nudge: detect/add/clear on both flows · split: prefill, live tally, add-row, saved record) · full relink sweep · zero stale links.

**Decisions locked (2026-07-01):**
- **Demo maps stay demo.** The "jobs nearby" popup + bin drop/pick pairing keep their built-in demo lists in the prototype (Wes-approved). **Production build wires them to the live calendar + bin store** — locked requirement, not optional.
- **Drywall markup = Rate Sheet.** No separate form: when ready to mark up DL Disposal's $415/t pass-through, edit the charge fee in the Rate Sheet's disposal section. Confirmed closed.
- **Saanich departments — already full.** `CONTRACTS_BUILTIN` ships Fire, Police, Bylaw, Parks & Rec, Public Works, Roadsides, Other for **both** Saanich and Oak Bay (runtime constant, no migration needed). Closed.
- **Nanaimo = second workspace, after Victoria is live.** The production build is brand-aware from day one (every record carries a brand tag); Nanaimo flips on as its own workspace. One codebase, two brands. Not a prototype item.
  - **Owner:** one login, a Victoria ↔ Nanaimo switch in the Owner Hub (same pattern as the pay-file toggle); everything on screen follows the switch. **Crew/manager logins are locked to one brand** — no switch, no cross-brand mistakes possible.
  - **Separate per brand:** Google Calendar, customers, rate card, bins, trucks, employees, texting number, Dropbox folder, invoice queue, price-sheet PDF library. **Shared:** the software + the owner account.
  - **Spin-up sequence:** Victoria live a few weeks → flip workspace on → new Nanaimo dispatch calendar (never repurpose) → second toll-free texting number + its own verification (2–3 wk clock, start day one) → Dropbox folder → Square second location → load data → people/trucks/bins → train crew → live.
  - **"Set up this workspace" screen (owner-only checklist, cards go green):** ① basics (name/phone/email/towns) ② calendar connect ③ **customer import = QuickBooks Customer Contact List export uploaded as a file**, preview with untick, matched on phone/email so re-imports never duplicate ④ **rates = "Copy Victoria's rate card" button, then edit the differences** (no PDF parsing — the Rate Sheet is live structured data; the five pricing PDFs live in a per-brand collateral library for texting customers) ⑤ people & trucks ⑥ bins & colour map ⑦ texting number. All green → go live.
- **Google Calendar colours (announced June 17, 2026, rolling out now):** event colours went from 11 → **24 defaults + up to 200 custom RGB per user**, on web, mobile **and the Calendar API**; naming comes via Google's colour labels. **Colour-scheme upgrade happens at production build** against the real API palette: every truck gets its own colour, statuses get dedicated colours (Tomato stops double-duty), and the Make.com revenue-signal watch is updated in the same cut-over — proven on the TEST calendar first. Prototype palette untouched by design (the colour→truck map is already editable, so the new palette drops straight in).

---

## Dropbox update list (do this save)

- **Replace (any older number → these):** booking → **v67** · owner hub → **v52** · bin tracker → **v34** · truck hub → **v54** · pallet → **v8** · day-board → **v28** · bin-registry → **v5** · CREW-commercial → **v22** · CREW-residential → **v25** · incident report → **v2**
- **Add if missing:** `island-junk-GO-LIVE-signup-guide.pdf`
- **Re-save (same names, relinked in place):** main-hub · management-hub-v81 · yard-processing-v28 · reminders-v1 · this doc
- Delete every superseded version once saved.

---

## Open items / next

- **Truck Hub "Service due" card** still runs on demo data (legacy `ij_maint_v1` fallback) instead of real Maintenance Hub records — wiring pass needed.
- Manager Hub stub tiles (Revenue, Customers, Weights, Clock & crew, Job edits, Tool registry, Parts & stock) still open blurb sheets — wire or hide via Customize.
- PC desktop spot-check of the responsive layouts (Wes eyeball).
- Backlog: **cleared 2026-07-01** — every item verified done, built today, or closed by decision (see Decisions locked above).
- **Production phase:** work the GO-LIVE PDF — Twilio verification first (2–3 week clock), then Calendar 2-way sync on the TEST calendar only, Square links, Dropbox photo filing. **Plus (locked):** wire nearby-jobs + bin pairing to live data · Nanaimo second workspace · calendar colour-scheme upgrade (24 + custom colours, per-truck colours, Make.com updated same cut-over).

---

## Standing rules (do not drift)

- Single-file HTML prototypes on **localStorage**; **Claude Code** is the production target. Phone-first; desktop-responsive.
- Every functional change → new version + bumped filename. Href-only relinks may be in-place.
- Live Google Calendars (Victoria + JOBS 2) **strictly read-only until go-live**; sync dev on a TEST calendar only.
- Never automate invoicing or card charging. Crew never sees customer pricing.
- Design tokens: Anton + Inter; orange `#F05014`, ink `#141414`, paper `#F4F3F1`, green `#3CA03C`. Standard header = `<img class="logo">` + tool pill.

## Key localStorage stores

`ij_rates_v1` (single rate source) · `ij_company_customers_v1` · `ij_customers_v1` (residential returns) · `ij_pm_db_v2` · `ij_mh_layout_v1` · `ij_bins_v1` (bin state machine; `outAt`/`inAt` drive the rental-day counter) · `ij_jobs_v1` (multi-day) · `ij_contracts_v1` (Saanich/Oak Bay) · `ij_colourmap_v1` · `ij_employees_v1` / `ij_clock_log` · `ij_incidents_v1` (new) · `ij_owner_sec_v1`. Convention: `ij_[store]_v[N]`.

---

## Batch — Jul 2 (Wes's 3 fixes)

**Bin Registry v6 — real fleet loaded.** The registry was still running on a demo handful; v6 carries the whole real fleet from Wes's original list: 8 yd ×4, 12 yd ×16 (all lidded), 16 yd ×11, 20 yd ×44 = 75 bins, with the 11 ROSS bins (20-10, 20-11, 20-14, 20-22, 20-29, 20-41, 20-44, 16-05, 16-06, 12-03, 12-04) flagged as leased to Island Junk Nanaimo. A one-time migration runs on load: strips the six old demo bins (matched on code + demo customer so real records are never touched), adds any missing fleet codes as idle, sets lidded on the 12s and leased on the ROSS set — works on a phone that already has registry data, no reset needed. Idle section now groups by size with counts; leased bins sit in their own "Leased · Island Junk Nanaimo (ROSS)" section, excluded from the available pool, tagged "ROSS lease" on the card. **Open: bin 3'3 — not in any file or chat; awaiting Wes's answer (size + code) to add it.**

**Manager Hub v82 — "Trucks, Bins & Yard" tile fixed at the root.** Cause: a saved tile layout from an older hub version had a group slot without an id; every load minted a fresh random id without saving it back, so the tile's id never matched at tap time and the open call bailed silently. Fix: `mhLoad` now persists the sanitized layout (ids freeze on first load) and `mhEnsureModules` appends any hub tool missing from a saved layout as a visible tile — which is also how the new Colour-map and Incident tiles surface on existing phones without a reset. Proven: legacy layout fails on v81, opens on v82.

**Colour → truck map — it had no door.** The map (shared store `ij_colourmap_v1`, synced across hubs) was fully built in both hubs but nothing ever called `ijcmOpen()` — the open button was never wired, which is why it was unfindable. Now a 🎨 "Colour → truck map" tile exists in **both** the Manager Hub (v82) and Owner Hub (v53). Upgraded for Google Calendar's June 17, 2026 colour update (24 defaults + custom RGB + nameable): every colour has a ✎ rename (match the label given in Google Calendar); an add-row (colour picker + name) creates custom colours, assignable to trucks like the classics and removable with ✕. Store stays `v:3` with additive `custom:[{key,name,hex}]` and `names:{}` fields — day-board/booking/swing read `current` defensively and are unaffected (they paint with the classic hexes until production reads the real Calendar API palette). Fixed en route: `ijcmSetTruck` guards with `hasOwnProperty`, so newly added customs now init their assign slot (dropdown was a silent no-op otherwise).

**Relinks:** main-hub updated in place (3 links). Zero stale links across canon.

**Dropbox re-save:** island-junk-bin-registry-v6.html, island-junk-management-hub-v83.html, island-junk-owner-hub-v54.html, island-junk-main-hub.html, island-junk-CURRENT-VERSIONS.md.

---

## Batch — Jul 2 (registry link + sage lock)

**Manager Hub v83 — Bin Registry now opens directly.** The registry was reachable only from the Main Hub; the Manager Hub had zero link to it. Added a 🗂️ **Bin Registry** module (opens `island-junk-bin-registry-v6.html` directly) — it appears as a top-level tile via the same `mhEnsureModules` heal, so it shows up on existing phones with no reset. Sits next to the Bin Hub for new installs.

**Colour map v83/v54 — Sage locked as the Unassigned colour.** Sage was in the assignable list with a note asking users to leave it Unassigned; now it's pulled out entirely and shown as a **locked "Unassigned" row** (its own block above the status trio) — no truck can be assigned to it. Assignable colours drop 8 → 7. Sage keeps Google id 2 for the production colourId. It never enters the store's `assign`/`current` map, so consumers are unaffected — booking, day-board, route-builder and swing already key off the literal `sage` calendar colour = "no truck picked yet," independent of the map. Applied to both hubs.

**Relinks:** main-hub → MH v83 + owner v54 (in place). In-scope link graph clean (rate-sheet-v14, employee-hours-v6, estimate-builder-v4 remain Wes-side files, referenced as before).

**Dropbox re-save:** island-junk-management-hub-v83.html, island-junk-owner-hub-v54.html, island-junk-main-hub.html, island-junk-CURRENT-VERSIONS.md.

---

## Nanaimo setup — first card built (Jul 2)

**`island-junk-nanaimo-setup-rates-v1.html`** — the Rates step of the "Set up this workspace" screen, built as a standalone preview (not yet wired into a setup shell; the other cards aren't built). Centrepiece is the **editable area-surcharge system** we designed:
- One row per area, each with a **hand-load $** and a **bin $** box (either can be blank). Add/edit/delete areas from the UI. Pre-seeded with Nanaimo's real service-area towns (amounts blank for Wes to fill); "Nanaimo" is the base row (0/0). Optional aliases per area help the address match.
- Editable **bin rental base** (default $225) so the demo total is real.
- **"Copy Victoria's rate card"** action (copies the shared pricing tables — load prices, special items, disposal fees, bin base — represented as a confirmation; full rate-table editing stays the separate Rate Sheet work).
- **Live "Try it" demo:** type a job address → matches the town → shows the hand-load and bin surcharge that would auto-apply, each with a one-tap **Skip (on route)** that waives it and adjusts the total. Base area shows no surcharge; unlisted address shows an add/quote prompt.
- Store `ij_nanaimo_rates_v1` = {binBase, ratesCopied, areas:[{id,name,aliases,hand,bin,isBase}]}. Matches booking v67's existing keyword-in-address approach; production reads the exact street address by GPS (same as the proximity pattern).
- Existing state confirmed in booking v67: bin area surcharges + address keyword auto-detect already live (BIN_SUR_REG/ROOF by town, differs by bin type); this makes that config editable per brand and extends it to hand loads + adds the on-route skip.
