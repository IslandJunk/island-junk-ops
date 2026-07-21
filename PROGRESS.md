# Island Junk — Build Progress & Handoff

**2026-07-21 (⭐ RESUME POINT — Phase 1b PROVEN + closed; booking phone/address pickers live on ALL lanes; NEXT: rest of booking backlog)** —
**START HERE.** Everything below is done, committed, and deployed. Repo clean, HEAD **`9bcff75`** (code), migration head
**`d7a3f9c2e1b8`** (unchanged), prod at `island-junk-ops.onrender.com`.

- **Phase 1b PROVEN — the payoff (booking → TEST calendar → Dropbox folder, end to end):** Wes booked a windowed
  residential job via the app → real green "✓ Booked — event `kluspr5nq2pjp5enqp5cec2qbg` on TEST". Read the event
  off the TEST calendar (`check_app_event.py`): it carries the `[app job 8bba501b-…]` marker AND a `Photos: <dropbox
  link>` line, appears in `list_events_for_day`, colour Sage/2, `ij_app=1`. Wes clicked the link → it opens the job's
  Dropbox folder. **Calendar + Dropbox chain both fire.** ✅
- **Dropbox folder names now searchable (`a7da706`, deployed):** `<root>/<brand>/<date name town phone short-id>`,
  e.g. `2026-07-20 Tom Sooke 642-7911 8bba501b` — findable by ANY of date/name/town/phone/id. Town parsed
  best-effort from the address (two-word towns OK; strips prov+postal), phone added, empty parts dropped, short-id
  always kept (cross-refs the calendar `[app job]`). `dropbox_files.py::job_folder_path` + `_town_from_address`.
- **Booking pickers — DONE on ALL lanes (`4bf0ec3` residential, `9bcff75` commercial+bin; deployed, give them a
  live spin):** Phone + Address (and the commercial **Company** / bin **Customer**) now use the SAME pick-only
  dropdown as Name — a row per match (name · address · phone), fills ONLY on an explicit tap; the old silent
  autofill-on-typing/change is gone on every lane. Residential `makeCustPick`; commercial `makeCoPick`→`applyQBco`
  (new `force` mode); bin `makeBinPick` (matches commercial accounts AND residential customers) — all built on a
  shared `custPickCore`. Whole script esprima-parse-clean; every matcher logic-tested vs the demo accounts+customers.
  **Live-spin check** (browser tooling hung on the local file, so Wes confirms live): /app/new-booking → Collect →
  Phone `250 555 0148` → tap Dave Mercer; Address `oxford` → tap; type-without-tapping → nothing fills. Then a
  commercial job → Company `hyundai`, and a bin drop → Customer `bmw`, behave the same.

> ▶▶ IMMEDIATE NEXT STEP — rest of the booking backlog (Wes's requests, all one screen), then Dropbox Phase 1c:
> 2. **Quick-pick**: search-by-name instead of the giant scroll list.
> 3. **Commercial (Proline)**: pick a location → auto-fill its address + save a NEW location per company (persist).
> 4. Make the **"Job ready" popup SCANNABLE** (sections/labels, not a monospace wall) + a note/edit step in it.
> 5. Minor: afternoon arrival windows parse to an AM *slot* time (5 PM → 05:00). Cosmetic (slot is positional).
> Then **Dropbox Phase 1c** — repoint the photo STORE from Postgres `job_photo` → the Dropbox job folder (now
> unblocked by 1b); then Phase 2 (crew capture) + Phase 3 (yard + bin truck; bin damage → bin folder + alert).

**2026-07-20 (booking 422 fixed + LIVE — Wes then booked to prove the calendar+Dropbox chain; DONE, see above)** —
Everything below is done, committed, and deployed. Repo clean, HEAD **`c32d153`**, migration head
**`d7a3f9c2e1b8`**, prod healthy at `island-junk-ops.onrender.com`. The arrival-window en-dash bug that made every
windowed booking 422 is FIXED + live — so bookings should finally reach the board (and trigger the Dropbox folder+link).

> ▶▶ IMMEDIATE NEXT STEP — Wes does this first in the new chat, then hands the result to Claude:
> 1. **Hard-refresh** the New Booking page (Ctrl+Shift+R) at `island-junk-ops.onrender.com/app/new-booking`.
> 2. Book a job **WITH an arrival window** → **CREATE JOB** → tap **"Book it — writes to TEST calendar"**.
> 3. It should go **REAL green "✓ Booked (…) — event <id> on TEST"** (a real id, not "?").
>
> ▶▶ THEN Claude verifies **Phase 1b** end-to-end (this is the payoff):
> - Read the TEST calendar (`app.integrations.gcal` locally — the local `.env` points at prod DB + the same
>   TEST cal `google_test_calendar_id`) for the app event: it should have a `[app job …]` line **AND** a
>   `Photos: <dropbox link>` line. Quick script: for `date.today()` ±1, `gcal.list_events_for_day(d)` then
>   `gcal._svc().events().get(calendarId=settings.google_test_calendar_id, eventId=ev['id'])` and grep the
>   description for `[app job` + `Photos:`. (The scratchpad `check_app_event.py` from the last session is gone —
>   re-create it; ~15 lines.) Confirm the Dropbox link opens the job folder (Wes clicks it).
> - If the button is **amber/red** instead: the bridge now shows the REAL error ("Booking failed: <field>: <msg>"
>   or "Job saved, calendar write FAILED: <err>") — paste it and fix from there. (create_event itself is FINE;
>   the earlier "create_event failing" theory was wrong — see the entry below.)

**BOOKING-SCREEN BACKLOG (Wes's requests — do AFTER Phase 1b is proven; all one screen):**
1. Make **PHONE + ADDRESS** auto-find a customer the same pick-only way NAME does now (reuse `makeCustPick`,
   residential + commercial). Name picker is done (`e58ab02`): dropdown of matches w/ address+phone, fills ONLY on
   explicit click, click-out = new customer, single list.
2. **Quick-pick**: search-by-name instead of the giant scroll list.
3. **Commercial (Proline)**: pick a location → auto-fill its address + **save a NEW location per company** (persist).
   The immediate hard-block is already fixed (`19fb410`: Account/location is editable + optional now) — this is the
   fuller location→address model.
4. Make the **"Job ready" popup SCANNABLE** (sections/labels, not a monospace wall) + add a **note / edit** step in it.
5. Minor: afternoon arrival windows parse to an AM *slot* time (5 PM → 05:00). Cosmetic (slot is positional; the
   real time is in the headline) — add AM/PM to `parseStart` when convenient.

**DROPBOX PHOTO SYSTEM status:** 1a (durable OAuth connect) LIVE + **Wes CONNECTED his Dropbox**. 1b (per-job
folder + shared link written into the booking's calendar event) BUILT + deployed but **UNTESTED until a booking
runs** — that's the verification above. 1c (repoint the photo STORE from Postgres `job_photo` → the Dropbox job
folder) is HELD until 1b is proven. Then Phase 2 (crew capture) + Phase 3 (yard + bin truck; bin damage → bin
folder + alert). Design rule locked: the folder LINK rides into the calendar event **at booking only** (never
per-photo edits — honors the write-only-at-booking guardrail); crew before/after photos STAY in Messenger.

**2026-07-20 (BOOKING BUG ROOT CAUSE FOUND + FIXED — arrival-window en-dash broke time_start -> 422)** —
The earlier "create_event failing on live" guess was **WRONG**. The error-surfacing fix (`bcba6c1`) revealed the
truth: `/booking` was returning a **422** ("Booking failed: [object Object]"). Captured the exact bridge payload —
`time_start` was **"12002:00"** (garbage). Cause: the arrival-window `<option>` values use an **EN-DASH "–"
(U+2013)** (e.g. "12:00–2:00 PM"), but `parseStart()` in `booking-bridge.js` split on a plain hyphen "-" -> no
split -> it mangled the whole string into digits -> invalid time -> Pydantic `time` rejected it (422). **So every
UI booking WITH an arrival window has been silently 422ing** (masked by the old false-green button); create_event
was never reached and is fine. FIX (`booking-bridge.js`): `parseStart` now splits on `/[-–—]/` (hyphen/en/em
dash) -> valid times ("12:00", "07:00", ...); verified via captured payloads + a logic unit-test + clean console.
Also made the "Booking failed" message extract the real Pydantic error (`field: msg`) instead of "[object Object]".
Known minor follow-up: PM windows parse to an AM slot time (5 PM -> 05:00) — cosmetic only (the slot is
positional; the real time is in the headline). **This unblocks bookings reaching the board AND the Dropbox
folder/link (Phase 1b), which never ran because the request 422'd first.**

**2026-07-20 (BOOKING — false-green fixed + error surfaced; led to the root cause above)** —
Wes booked via the app and got a green "✓ Booked — event ? on TEST", but **no calendar event was created**
(scan of the TEST calendar found none). Root: `booking-bridge.js` only checked 401/403, so it showed green even
on a 500 — `gcal.create_event` is **raising on the LIVE server** (local booking + create_event work fine with
the local Google key, so this is live-specific — likely the Render Google Secret File key / write access, TBD).
Shipped a fix to expose it: (1) `create_booking` now wraps `create_event` in try/except — the Job still saves,
`gcal_event_id=None`, and the error is stashed in `job.details['_calendar_error']` + logged; (2) `BookingOut`
returns `calendar_error`; (3) the bridge checks `r.ok` and shows the real outcome ("Booking failed: …" on a 500,
"Job saved, calendar write FAILED: <err>" when the event didn't write, green only on real success). NEXT: Wes
re-books once -> the button shows the actual `create_event` error -> fix the root cause. THEN Wes's 3 booking-UX
requests (phone+address pickers like the name one; make the "Job ready" popup scannable not a text blob; add a
note/edit option in that popup).

**2026-07-20 (Booking — residential customer picker fixed, per Wes)** — The New-Booking residential lane's
customer autofill was hijacking the form: it auto-filled on typing AND on blur/enter via a first-name match
(grabbing the wrong person), showed TWO dropdowns, and gave no way to tell duplicate names apart. Fixed in
`prototypes/island-junk-new-booking-v67.html` (`collectWire` + new `makeCustPick`): ONE dropdown showing each
match as **name + address + phone**, and the form fills **ONLY when a row is explicitly clicked** (never on
typing/blur/enter), from that exact customer object so duplicate names resolve correctly. Removed the dead native
`qbList` datalist + the duplicate `makeAuto('fname')`. Kept the phone-number autofill (unambiguous). Verified live
against the 2,173 real imported customers (multiple "Aaron"s: typing+blur filled nothing; picking "Aaron Hopwood"
filled his exact record — `250-588-7235`, `1008 Pandora Ave`). This edits the approved prototype directly (the
behavior is too coupled to override from the bridge) — owner-directed change. NOTE: the commercial (`#company`) +
bin (`#binCust`) lanes still have the old auto-fill-on-change pattern; apply the same fix there when confirmed.

**2026-07-14 (Dropbox Phase 1b — per-job folder + calendar link at booking; built dry-run, repoint held)** —
At booking the app now creates the job's Dropbox folder + a stable shared link and writes the link into the
calendar event description (`Photos: <link>`), so searching the job in Calendar -> click -> the folder. Honors
the write-only-at-booking guardrail (one event write; photos accumulate in the folder, NO per-photo edits).
- `app/integrations/dropbox_files.py`: `job_folder_path` (`<root>/<brand>/<date customer short-id>`),
  `create_folder` (idempotent, 409=exists), `ensure_shared_link` (create or fetch existing),
  `ensure_job_folder(db, job, on_date)` (get_valid_access_token -> create folder + link -> stash {folder, link}
  on `job.details['dropbox']` -> return link; **None/no-op when Dropbox isn't connected**). Wired into
  `app/booking/service.py::create_booking` after the flush (best-effort try/except — never fails a booking);
  `_description` appends the `Photos:` line when a link exists.
- **CREDS-GATED + SAFE:** unconnected -> `ensure_job_folder` returns None before any API call, so booking is
  byte-for-byte unchanged. Verified: imports; parse; `job_folder_path` output. The folder/link API calls
  (`create_folder_v2`, `create_shared_link_with_settings`) are **untested until Wes connects** — test live then
  (watch parent-folder auto-creation + the 409 'link exists' path).
- **STILL HELD (Phase 1c):** repoint the photo STORE from Postgres `job_photo` to the Dropbox job folder —
  deliberately NOT done yet, so today's working in-app photos don't break until Dropbox is proven connected.

**2026-07-14 (Dropbox photo SYSTEM — Phase 1a: durable OAuth connect shipped)** — Wes refined the photo plan
into a fuller system: Dropbox as the per-job store, with a **stable folder LINK dropped into the job's Google
Calendar event AT BOOKING** (honors the "calendar write only at booking" guardrail — NO per-photo event
edits), so searching a job in Calendar -> click the link -> all its photos (befores, afters, yard, bin issues,
customer sends). Crew before/after **stay in Messenger**. This supersedes the in-app Postgres storage from the
prior entry — the booking-photo button + Day Board strip become the front-end; the store moves to Dropbox.
- **Phase 1a (this commit) — durable Dropbox OAuth connect, mirrors QuickBooks.** New `dropbox_connection`
  table (single row — ONE account; brand = folder path; migration **`d7a3f9c2e1b8`, new head**), tokens
  Fernet-encrypted (same `qbo_token_key`). `app/integrations/dropbox_oauth.py` (authorize/exchange/refresh/
  get_current_account + `get_valid_access_token` on-demand refresh; Dropbox refresh tokens don't rotate,
  access ~4h). Owner-only `app/api/dropbox.py`: `/dropbox/connect|callback|status|disconnect` (2FA on
  connect/disconnect; signed, time-boxed CSRF state; SameSite=Lax cookie survives the redirect). Owner-Hub
  **"Linked apps"** tile -> real **Connect Dropbox** card (`owner-hub-bridge.js`). Config: `DROPBOX_APP_KEY` /
  `DROPBOX_APP_SECRET` / `DROPBOX_REDIRECT_URI` (`is_dropbox_oauth_configured`). Removed the legacy
  static-token `/dropbox/job-photo` + `/dropbox/status` from `integrations.py`. Verified: imports; migration
  linear; owner-hub parses clean; Dropbox sheet renders (shows "not set up" until app creds exist).
- **TO ACTIVATE (Wes):** create a Dropbox app (App Console -> Scoped access -> Full Dropbox), scopes
  `account_info.read files.metadata.read files.content.write files.content.read sharing.write`, add redirect
  URIs (`http://localhost:8000/dropbox/callback` + `https://island-junk-ops.onrender.com/dropbox/callback`),
  set `DROPBOX_APP_KEY` + `DROPBOX_APP_SECRET` in Render -> Owner Hub -> Linked apps -> Connect Dropbox.
- **STILL TO BUILD (after connect):** per-job Dropbox folder + shared link into the booking calendar event
  (at booking only); repoint the booking photos + Day Board strip from Postgres `job_photo` to the Dropbox job
  folder. Then Phase 2 (crew capture) + Phase 3 (yard + bin truck; bin damage -> bin folder + alert).

**2026-07-14 (Job reference photos — manager attaches, crew see on the Day Board; Dropbox NOT used)** —
Started as "set up Dropbox photo filing," but talking through the real workflow we landed somewhere simpler
and better. The crew's before/after photos **stay in Facebook Messenger** (fast, searchable by address —
don't break a working flow). The actual gap was the **manager bringing the customer's reference photos into
the job** so the crew see them (§8) — and that needs **no Dropbox at all**; the photos live in the app.
- **NEW `job_photo` table** (migration **`c4d9e1a2b3f5`, new head**) — image bytes stored in-app, compressed
  **client-side** (canvas downscale to 1600px / JPEG 0.7) so rows stay small. Router `app/api/job_photos.py`:
  `POST /jobs/{id}/photos` (attach, any signed-in crew), `GET /jobs/{id}/photos` (list), `GET /job-photos/{id}`
  (serve bytes), `DELETE /job-photos/{id}` (manager/owner). Brand-isolated (a crew member can't reach a
  cross-brand job's photos, §15).
- **Attach at booking:** `booking-bridge.js` — on a successful `/booking`, the manager's attached photos (the
  "+ Add photo from phone" button -> the prototype's `mgrPhotos`) are compressed + uploaded onto the new job
  (best-effort; the button shows "N/M photos filed").
- **Crew view on the job:** `day-board-bridge.js` — each Day Board stop now carries `job_id` (added to
  `app/dispatch/day_board.py::_job_view`); opening a stop shows a **"Reference photos"** strip (tap to enlarge)
  above the on-our-way button. Silent when a stop has no linked job or no photos.
- **Decisions:** photos in Postgres (`bytea`) — fine for the low volume (manager reference shots, NOT the crew
  stream); move to object storage if it ever grows. **No Dropbox app / OAuth needed** (saved Wes that setup).
  The existing `app/integrations/dropbox_files.py` + `/dropbox/job-photo` stay built-but-unused (dry-run).
- **Verified** locally (prod DB): backend imports; migration linear (`c4d9e1a2b3f5`); booking + day-board
  bridges parse clean; `openStop` wrapped so the photo strip injects on stop-open. Full store->display
  end-to-end verifies **live** (needs the migration, which Render applies on deploy). NOTE: the **Truck Hub is
  a launcher with no job data** (`bridge: None`) — the crew's real per-job view is the **Day Board stop detail**,
  so photos live there.

**2026-07-14 (Email 2FA ACTIVATED + in-hub Security panel + QuickBooks tidy)** —
- **Email 2FA is LIVE + activated.** Wes set up SendGrid (verified single sender `wes@islandjunk.com`, Mail-Send-only
  API key; `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL` set in Render), added `wesroberts@hotmail.ca` as the recovery
  email, and verified an **emailed code end-to-end on prod**. Email is now the phone-loss recovery path (no backup codes).
- **In-hub "Security - sign-in" panel (NEW).** The Owner-Hub **Security** settings tile now opens a REAL sheet (was the
  prototype's simulated one) via an `openSheet` override in `owner-hub-bridge.js`: manage the 2FA SMS number
  (`/auth/2fa/set-phone`), add/change the recovery email (`/auth/2fa/set-email`, shown when `email_channel_ready`), and
  **Lock the Owner Hub now**. New owner-only `POST /auth/2fa/lock` clears the session's `owner_2fa_verified` so the next
  load re-prompts the real gate; the hub's existing "Lock" button is overridden to use it (it previously fell back to the
  simulated password gate). No migration. Fixes the earlier gap where recovery email could only be set from the signed-out gate.
- **QuickBooks placement (Wes's call).** QB controls (Connect/Sync/Auto-sync/Disconnect) are now wired into the prototype's
  intended **"Auto-invoicing"** settings tile (`openSheet('autoinvoice')` -> `qboSheet`). In **"Needs you"**, QB shows ONLY
  when it needs attention (configured but **disconnected**); connected + auto-syncing -> stays out of the action list. WS4 QB
  itself is done + live (only Nanaimo's company left to connect when that workspace is built).
- **Verified** in-browser against the prod DB: bridge parses clean (no console errors); Security sheet renders in both
  SendGrid-on and -off states with phone+email wired to live endpoints; QB absent from "Needs you" while connected; the
  Auto-invoicing tile opens the QB sheet. Files: `app/api/auth.py` (+`/2fa/lock`), `app/static/owner-hub-bridge.js`.

**2026-07-14 (Owner 2FA — EMAIL channel added; dormant until SendGrid is set)** — Built a second 2FA delivery
channel so email can be the owner's phone-loss recovery path (Wes chose email over backup codes; recovery address
= wesroberts@hotmail.ca, to be stored via the gate's "Add a recovery email" once the channel is live). The 2FA
engine was already channel-agnostic (`issue_code`/`verify_code` don't care about delivery), so this is a delivery
add-on, not a crypto change:
- **New/changed:** `app/integrations/email_send.py` (SendGrid v3 via lazy `httpx`, creds-gated → `EmailNotConfigured`
  when absent, never a silent "sent"); `owner_security.emails` JSONB column (**migration `b8e4f2a1c9d3`, new head**) +
  `owner_email`/`set_owner_email`/`mask_email` in `app/auth/twofa.py`; owner-only `POST /auth/2fa/set-email`;
  `POST /auth/2fa/request` now takes `{channel:"sms"|"email"}` (SMS default, opt-out bypass unchanged);
  `GET /auth/2fa/status` adds `email_set`/`email_masked`/`email_channel_ready`. Gate UI (`owner-hub-bridge.js`) gains
  "Phone unavailable? Email me a code" / "Add a recovery email" — but these render ONLY when `email_channel_ready`
  (SendGrid configured), so the SMS gate is byte-for-byte unchanged until then.
- **Config:** `SENDGRID_API_KEY` + `SENDGRID_FROM_EMAIL` (+ optional `SENDGRID_FROM_NAME`) in `app/core/config.py`;
  `settings.is_email_configured`. NOT set yet → email channel dormant; SMS 2FA fully live + unaffected.
- **Verified:** app imports clean; alembic head linear (`b8e4f2a1c9d3`); gate JS loads with **zero console errors**
  and degrades gracefully. The only gap was the DB column (browser test hit exactly `owner_security.emails does not
  exist`). Migration applies on Render deploy via `preDeployCommand` (migrate-then-serve; a failed migration aborts
  the deploy, so no lockout window). Full endpoint + live-email test pending SendGrid creds.
- **TO ACTIVATE (Wes, when ready):** create a SendGrid account → verify a single sender → set `SENDGRID_API_KEY` +
  `SENDGRID_FROM_EMAIL` in Render → the gate's email options appear → add wesroberts@hotmail.ca as the recovery email
  → live test (request an email code → verify). Then email is the phone-loss recovery path; no backup codes needed.

**2026-07-14 (SECURITY — public-repo PIN exposure CLOSED)** — Confirmed the GitHub repo `IslandJunk/island-junk-ops`
is **public** (`"visibility":"public"`) and the owner+manager PINs were hardcoded in the *current* `scripts/seed_owner.py`
(not just git history). **Rotated the owner + manager PINs in the live prod DB** (Wes chose the new values; NOT stored in
this doc) → the published `4321`/`1111` no longer authenticate; verified new-works + old-dead. **Scrubbed `seed_owner.py`**
to env-driven `0000` placeholders (`SEED_OWNER_PIN` / `SEED_MANAGER_PIN` / `SEED_OWNER_PASSWORD`); the owner-hub password
`owner` was already dead code (2FA is the real gate) but was scrubbed too. Crew stay `0000` until Wes assigns real per-person
PINs from the Owner Hub at go-live. Old history values are now inert (PINs changed) — **no history rewrite needed**. The
seed-script edit is uncommitted on `main` pending Wes's OK to push.

**2026-07-14 (RESUME POINT — Owner SMS 2FA COMPLETE + live-tested; WS4 fully live)** — Wes verified real owner 2FA
end-to-end on production (set his cell → real texted code → Verify → hub unlocked). Everything below is DONE, deployed,
and confirmed working on the REAL books. Migration head **`206c2604ac57`**; latest commit **`641037f`**.
- **Owner SMS 2FA — DONE + LIVE.** Gate: `app/static/owner-hub-bridge.js` prepends a real SMS gate that replaces the
  prototype's *simulated* password/code gate (on load: verified session → reveal hub; else set cell first-time → text
  a 6-digit code → verify → reveal). Backend: `app/auth/twofa.py` (HMAC-hashed codes keyed by the session secret,
  10-min expiry, single-use backup codes), `Session.owner_2fa_verified`+`twofa_code_hash`+`twofa_expires_at` (migration
  `206c2604ac57`), owner-only `/auth/2fa/status|set-phone|request|verify` (code from the updates line,
  `respect_opt_out=False`). Enforcement: `require_owner_2fa` (deps) on **`/square/charge-card-on-file`** +
  **`/quickbooks/connect` + `/disconnect`** (reads — status/sync/invoice-queue/reminders — stay owner-only so the hub
  loads behind the gate; the auto-sync scheduler is a trusted background job, unaffected). Crew keep fast PIN login.
  Commits `041f107` (backend) + `641037f` (gate+enforcement). **Wes's 2FA cell is now set** in `owner_security.phones`.
- **WS4 QuickBooks — LIVE on the real Victoria company** ("Island Junk Solutions Ltd", realm `193514598077864`),
  read-only, tokens Fernet-encrypted (`gAAAAA…`, prod `QBO_TOKEN_KEY`). **In-app auto-sync** = `app/quickbooks/scheduler.py`
  (15-min lifespan loop; Owner-Hub Auto-sync toggle per brand; no separate cron). Twilio + Square also live.
- **ACCESS / RECOVERY (important for the next session):** local `.env` `DATABASE_URL` points at the **Render PRODUCTION
  DB** — so all DB checks/fixes are run from local (`.venv/Scripts/python.exe`). Local `.env` = SANDBOX QBO creds +
  sandbox `QBO_TOKEN_KEY`; Render dashboard = PRODUCTION QBO creds + prod `QBO_TOKEN_KEY` (never in git). Prod:
  `island-junk-ops.onrender.com`. Owner login = **Wes** (owner PIN not stored in this handoff). **If ever locked out of the Owner Hub:** clear
  `auth_session.owner_2fa_verified` isn't needed — instead set a session's flag true, or fix `owner_security.phones`,
  directly in the DB.
- **OPEN FOLLOW-UPS (all optional, none blocking):** (1) rotate the SANDBOX client secret (chat-exposed; the PRODUCTION
  secret Wes typed straight into Render, so it's safe); (2) add a "generate backup codes" flow for 2FA (owner has none —
  phone-loss recovery is DB-only today); (3) extend `require_owner_2fa` to more owner endpoints if wanted (sync / toggle
  / reads); (4) optional `intuit_tid` logging on QBO errors; (5) connect Nanaimo's QB company ("Island Junk Solutions
  Nanaimo Ltd.") from the Nanaimo workspace when it's set up; (6) ~~**SECURITY (do soon):** rotate the exposed PINs~~ —
  **DONE 2026-07-14** (see the security entry at the top of this file): repo confirmed **public**, owner+manager PINs
  rotated in the live prod DB, `seed_owner.py` scrubbed to placeholders; crew `0000` until owner-set at go-live.
  **Day-to-day QB use:** put the `BIN-####` from the owner
  Ready-to-invoice list on the real QuickBooks invoice (Message field) → tap "Sync QuickBooks now" (or flip Auto-sync ON).

**2026-07-14 (WS4 auto-sync live + owner SMS-2FA backend)** —
- **In-app auto-sync SHIPPED** (commit `9ccb854`): `app/quickbooks/scheduler.py` — a background loop started from the
  FastAPI lifespan runs `poll_all` every 15 min for brands with the Owner-Hub auto-sync toggle ON (no-op when OFF).
  Replaced the `render.yaml` cron (no separate service to configure — the web service already has the QBO creds/key).
  Prod healthy after deploy. **Sync test on the REAL books passed**: owner-login API → `POST /quickbooks/sync` scanned
  **102 real invoices**, 0 BIN matches, read-only, no errors.
- **Owner SMS 2FA — BACKEND done + tested** (migration `206c2604ac57`). Wes chose SMS (crew keep fast PIN login;
  2FA is owner-only). `Session.owner_2fa_verified` + `twofa_code_hash`/`twofa_expires_at`; `app/auth/twofa.py`
  (HMAC-hashed 6-digit codes keyed by the session secret, 10-min expiry, single-use backup codes); owner-only
  `/auth/2fa/status|set-phone|request|verify` (code texted from the updates line, `respect_opt_out=False`). Tested:
  right/wrong/expired code, backup-code single-use, owner-only (+ manager 403). **Deployed but DORMANT** — nothing
  enforces or calls it yet, so no lockout risk.
- **2FA STILL TO DO (activation — do WITH Wes's real phone so there's no lockout):** (a) owner-hub **GATE UI** —
  replace the prototype's simulated `unlock()` gate: on load call `/auth/2fa/status`; if unverified, prompt set-phone
  (owner phone is currently unset, `phones: []`) → text code → verify → reveal the hub; (b) **ENFORCE**
  `require_owner_2fa` (is_owner + `session.owner_2fa_verified`) on the sensitive owner endpoints (QuickBooks router +
  `/square/charge-card-on-file`). Recovery if ever locked out: clear the flag / phones directly in the DB (I have access).

**2026-07-12 (WS4 LIVE in production — real Victoria QuickBooks connected)** — Deployed to Render (commits
`7ec9ae3` WS4 + `5816fa8` legal pages) and Wes connected the **real Victoria company**: `qbo_connection`
brand=victoria, realm **193514598077864**, company **"Island Junk Solutions Ltd"**, tokens **Fernet-encrypted
at rest** (`gAAAAA…`, prod `QBO_TOKEN_KEY`), read-only, auto-sync OFF. Production env vars set on the Render web
service (QBO_CLIENT_ID/SECRET production, QBO_ENVIRONMENT=production, QBO_REDIRECT_URI = onrender callback,
QBO_TOKEN_KEY). Added public **`/legal/privacy` + `/legal/eula`** pages (served from the app) — Intuit's app
profile requires public EULA + privacy URLs to unlock production keys; completed the App Assessment questionnaire.
**Gotchas:** (a) a leftover SANDBOX connection in the shared DB showed as "connected" and masked the real connect
— had to **Disconnect** first; (b) the onrender redirect URI must be added under the Intuit **Production** keys
(Development ≠ Production); (c) Wes has TWO QB companies (Victoria = "Island Junk Solutions Ltd", Nanaimo =
"Island Junk Solutions Nanaimo Ltd.") — Nanaimo connects later from its own workspace.
**Day-to-day use:** put the `BIN-####` from the Ready-to-invoice queue on the real invoice → tap **"Sync
QuickBooks now"** → 48h clock starts; paid → Sync → cleared. MANUAL for now — the auto-poll cron is in
`render.yaml` but needs a **Render blueprint sync** + its own env vars + the Google Secret File to run hands-off.
**Open follow-ups:** (1) **rotate the sandbox client secret** (chat-exposed; regenerate Development secret in
Intuit + update local `.env`); (2) **real owner 2FA** — the owner-hub 2FA is still the prototype's *simulated*
gate (server-side owner protection = PIN + owner-only checks, single factor); build real SMS-code 2FA (model
already has phones + backup_codes); (3) optional: `intuit_tid` logging on QBO errors; deploy the auto-poll cron.

**2026-07-12 (WS4 security review DONE + auto-poll shipped)** — Full WS4 built, sandbox-proven end-to-end, and reviewed.
- **Security review** of `app/api/quickbooks.py`, `app/quickbooks/*`, `app/integrations/qbo.py`. **Fixed:** (1) reflected XSS —
  the `/quickbooks/callback` page echoed the Intuit `?error` param (+ company name + exception) into HTML unescaped, and the
  error branch runs *before* any signature check → now `html.escape`d; (2) bounded the invoice matcher to `BIN-\d{1,15}` so an
  over-long code can't overflow `varchar(20)` and 500 the sync batch (same class as the `source_id` bug); (3) numeric-`realmId`
  guard in the callback + `max_length=20` on the manual cc-charge input. **Verified clean:** read-only by construction (QBO
  client only GETs + token grants — no POST to any invoice/payment), owner-only on every `/quickbooks/*` route, signed +
  time-boxed CSRF state bound to the owner, no auto-charge path, calendar live-ID guard intact, no injection, secrets git-ignored.
  **Open recommendation before a REAL company (Wes's call):** OAuth access+refresh tokens sit plaintext in `qbo_connection` —
  recommend Fernet encryption at rest (~15 min). Minor: sync reads ≤1000 changed invoices/run (add paging if exceeded).
- **Auto-poll shipped** — `app/quickbooks/poll.py::poll_all` + `scripts/qbo_poll.py` + a `render.yaml` `*/15` cron; no-op unless a
  brand's auto-sync toggle is ON; tested locally (Victoria toggled on → synced → restored to OFF). Activates on the next deploy.
- **Left before real QB:** deploy to Render (commit + push; set production Intuit keys + point `QBO_REDIRECT_URI` at the
  onrender callback; connect the real company) and, recommended, the token encryption above. Live preview: `preview_start` (`api`).

**2026-07-12 (WS4 QuickBooks — Connect LIVE + BIN-xxxx DONE)** — Building WS4 (live read-only QB sync).
**Shipped + verified this session:**
- **QBO OAuth Connect** — `app/integrations/qbo.py` (authorize / callback / refresh / read-only query + companyinfo),
  `QboConnection` token table (migration `bb14991c2fcc`), owner-only `/quickbooks/connect|callback|status|disconnect|sync-toggle`
  (`app/api/quickbooks.py`), Owner-Hub **QuickBooks** card (`owner-hub-bridge.js`). CSRF `state` signed to the owner emp id +
  time-boxed; `ij_session` cookie is SameSite=Lax so it survives the Intuit round-trip. **Wes connected the QB SANDBOX live**
  (company "Sandbox Company US 0ab4", realm 9341457448289097) — proves the token AND a read-only companyinfo GET. Sandbox
  creds in the local `.env` (`QBO_CLIENT_ID/SECRET`, `QBO_ENVIRONMENT=sandbox`,
  `QBO_REDIRECT_URI=http://localhost:8000/quickbooks/callback`; use `localhost`, not 127.0.0.1). Auto-sync default OFF (manual-first).
- **BIN-xxxx reference code (migration `1c7ca647e84a`)** — anchored to the **bin's out-period** (Wes's steer: the app already
  tracks which bins are out and the pickup picks from that list, so bin code = the drop↔pickup link — no booking-flow rebuild).
  `apply_bins` mints `reference_code` (`BIN-####` from the `bin_ref_seq` sequence) + `rental_group_id` when a bin goes OUT
  (dropped/full from a non-out state); stable through the rental, re-mints on a fresh drop; safety-mints legacy out-bins.
  Surfaced in the invoice-queue and carried onto the cc_charge `Reminder` (the WS4 match key); Owner-Hub Ready-to-invoice +
  Bins-awaiting-payment show **"QuickBooks PO: BIN-#### [Copy]"**. Backfilled current out-bins. Verified end-to-end
  (mint/keep/re-mint, reminder stores it, refChip renders, live test bin snapshotted + restored). Migration head now **`1c7ca647e84a`**.
- **WS4 read-only sync engine — DONE + proven against the live sandbox.** `app/quickbooks/sync.py::sync_brand`: refreshes the
  token, queries QBO invoices changed since `last_synced_at` (`MetaData.LastUpdatedTime`, 90-day first-run lookback), extracts
  `BIN-####` from memo / PO / DocNumber / custom-field / line, and — matching a cc_charge `Reminder` by `reference_code` (so the
  manual + QB paths never double-create) — starts the 48h clock on an unpaid invoice and clears it + marks paid when
  `Balance == 0`. READ-ONLY: no POST to any QBO invoice/payment. Owner-only `POST /quickbooks/sync` + a **"Sync QuickBooks now"**
  button in the Owner-Hub QB sheet. Live sandbox run scanned **31 invoices, 0 matched** (QBO sample data) with token refresh, no
  errors. **Sandbox loop PROVEN end-to-end** (2026-07-12) — invoice #1038 with `BIN-4021`: Sync started the 48h clock → payment
  received → Sync marked it paid + cleared the queue (reminder `by=quickbooks`, `done=True`). The test surfaced + fixed a real
  bug: `Reminder.source_id` was `varchar(60)` and a QB customer name + full billing address overflowed it → widened to 500
  (**migration `7ee94fa5e7d8`**, new head; also fixes the latent manual-flow case). **Remaining before real QB:** (a) **security
  review** of the WS4 surface (tokens at rest, read-only enforcement, charge + calendar guards); (b) **deploy to Render** + set
  production Intuit keys + connect the real QB company; (c) optional **scheduled auto-poll** (Render cron) so the toggle polls
  without a manual "Sync now". Local preview runs via `preview_start` (name `api`, `localhost:8000`); QBO code is uncommitted on `main`.

**2026-07-12 (bin payments + calendar build IN PROGRESS)** — Wes approved a **4-workstream build** (spec:
`docs/bin-payments-and-calendar-plan.md`) that reverses three guardrails *deliberately* (auto-paint status
colours on the app's own calendar — never live; owner-pressed card charging via Square tokens; live
read-only QuickBooks sync). Decisions locked: two calendar events per bin rental (drop + pickup, invoiced
once after pickup), reference-code QB matching, customer-level saved card, **owner-only** charge, pre-auth
rejected (auth expiry) in favour of card-on-file. **Shipped + verified:**
- **WS1** — Owner-Hub **"Bins awaiting payment"** queue + **"Received as e-transfer"** close-out
  (`owner-hub-bridge.js`, uses existing `/reminders` endpoints).
- **WS2** — auto-paint **live end-to-end**: `gcal.recolor_event` (TEST-calendar-only) + `app/dispatch/paint.py`,
  **wired** into `apply_dayboard_status` (crew marks a stop done → linked Job status + paint: bins→Tomato/red,
  hands-on→Basil/green; transition-only; owner close-out colours never auto-painted).
- **WS3 card-on-file BACKEND + ENDPOINTS — DONE + verified (sandbox).** `square_pay.py`: `create_customer`
  / `save_card_on_file` (Cards API, token only — never the PAN/CVV) / `charge_card_on_file` (Payments API,
  owner-pressed, idempotent, raises `SquareError`). Tables `stored_card` + `card_charge` (migration
  `28c686247d41`, applied). Endpoints: `POST /square/save-card` (manager), `GET /square/card-on-file`,
  `POST /square/charge-card-on-file` (**owner-only** — 403 for managers). All verified against **Square
  SANDBOX** end-to-end (save VISA ••5858 → owner charge $25.60 COMPLETED + audit row → manager blocked).
  **WS3 is COMPLETE + proven live.** Owner "Charge card on file" button (check card → invoice total → +2.4%
  shown → charge → reminder closed; sandbox VISA ••5858, $100→$102.40 COMPLETED, audit row). Card **capture**
  field: `/app/save-card` page + `save-card-bridge.js` loads Square's Web Payments SDK, renders Square's own
  secure card iframe, tokenizes → `/square/save-card` — Wes entered a real Square test card and it saved
  (VISA ••1111, `ccof:` token only, no PAN/CVV). `square_application_id` + `location_id` on `/square/status`
  for the SDK. **Follow-on (small):** the card field is a standalone page today — link/embed it into the bin-
  booking bin lane. NOTE: astral emojis corrupt to lone surrogates on serve here — keep bridge text ASCII.
  Sandbox test card 4111… is US so the field shows US "ZIP" (Square has no CA test card); real CA cards show
  a postal-code field automatically.

**Square SANDBOX connected LOCALLY** — sandbox creds in the git-ignored local `.env`
(`SQUARE_ENVIRONMENT=sandbox`, app id `sandbox-sq0idb-…`, location `L57750E6QHVHF` "Default Test Account" CAD).
**Render still has PRODUCTION Square** (untouched). Test nonce `cnon:card-nonce-ok`.

**Still to build (in order):**
1. **WS4 — QuickBooks (read-only sync)**: detect **invoice-sent** → start the 48h clock + reminder; detect
   **payment** → clear the reminder + mark paid. **Owner-Hub on/off toggle + manual fallback** (the manual
   buttons already work, so QB is a layer on top). Needs Wes's QB **developer app + sandbox company**
   (dev.intuit.com; redirect URIs `http://localhost:8000/quickbooks/callback` +
   `https://island-junk-ops.onrender.com/quickbooks/callback`). Match a QB invoice to a bin job by the
   **`BIN-xxxx` reference code** Wes pastes into the invoice PO field.
2. **WS1 — two-event bin link + `BIN-xxxx` reference code** (do this WITH WS4 — it's the QB match key).
3. **Follow-ons (small):** embed the `/app/save-card` field into the bin-booking bin lane (standalone today);
   auto-paint from the **bin-tracker** drop/pickup + the **residential calculator** (payment-aware green/red).

Migration head **`28c686247d41`**. Make.com stays off. **OPEN QUESTION for next session:** Wes's screenshot
showed a *"QuickBooks Connections · Victoria ✓ Connected (production)"* page — that is **NOT** built in
island-junk-ops (WS4 isn't started). Ask Wes what that page is (another app? a QB dev app he already made?)
before building WS4 — he may already have the QB developer app/sandbox we need.

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
`migrations/versions/`, NOT `alembic/versions/`). 12 routers, 34 synced keys. Login: **Manager** or **Wes (owner)** (PINs not stored in this doc). Preview server: `.claude/launch.json` (name `api`) runs plain uvicorn with **no `--reload`** →
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

> **Priority now = the bin-payments/calendar build at the TOP of this file (WS4 QuickBooks next).** The
> items below are the *separate, still-open v1 integrations* (Dropbox, Nanaimo) — do them when they come up.

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

Login: **Manager** or **Wes (owner)** (PINs not stored in this doc). In browser tests the owner-hub's second gate is skippable via
`unlock()`; prefer the API for auth (`POST /auth/login {pin, brand}` sets the cookie). Preview server: `preview_start`
(name `api`) — restart it after any Python edit (no `--reload`).

**Safety confirmed this session:** `app/integrations/gcal.py` still hard-refuses the two live calendar IDs (`LIVE_VICTORIA`,
`LIVE_JOBS2`) + `primary` and writes ONLY to the configured TEST / reminder / punch calendars; `.gitignore` still protects
`.env`, `spike/service-account-key.json`, and customer PII exports (verified they are ignored).
