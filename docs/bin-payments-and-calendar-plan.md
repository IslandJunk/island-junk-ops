# Plan — Residential bins: lifecycle, calendar auto-paint, card-on-file & QuickBooks

**Status:** proposed, awaiting Wes's approval (2026-07-12). **No code until approved.**
Supersedes the earlier `card-on-file-plan.md` (folded in as Workstream 3).

This is a **four-part build**, done in order, each testable on its own. Everything runs
**manual-first** so nothing depends on an integration being up.

---

## Sanctioned guardrail changes (Wes's explicit decisions this session)

These reverse locked rules in `CLAUDE.md`. They must be written into the brief (§2/§5/§6/§9/§15)
so a future session doesn't "fix" them away:

1. **App may auto-paint status colours** on its **own dedicated calendar** (TEST now, the go-live
   crew calendar later) — a change to "write only at booking." **Still NEVER** the two live
   calendars (`ISLAND JUNK VICTORIA`, `JOBS 2`) — the `gcal.py` guard stays.
2. **Owner-pressed card charging** for residential bins via Square Card-on-File (tokenized; no
   PAN/CVV ever stored) — a change to "charging is always manual." Everything else stays manual.
3. **Live QuickBooks read-only sync** (detect invoice-sent + paid) — a change to "QuickBooks is
   file-upload only." The app still never *creates or sends* invoices.

Make.com stays **disconnected** for now (Wes's call) — but all colour semantics below match what
Make will key on, so it's drop-in when he turns it on.

---

## The bin lifecycle (two calendar events, one invoice)

A bin rental = **one job, two calendar events**, invoiced **once** (after pickup + dump).

### Event 1 — Drop
| Step | Actor | App status | Calendar colour |
|---|---|---|---|
| Book | Manager | created | Sage → bin-truck colour |
| Bin dropped / out on rent | Driver (app) | out | **auto → Red** |
| Invoice drafted, customer data in (unsent) | Owner | drop closed | **you → Purple** (manual) |

### Event 2 — Pickup (booked later, at customer request)
| Step | Actor | App status | Calendar colour |
|---|---|---|---|
| Book pickup | Manager | created | truck colour |
| Bin picked up, HQ time, notes | Driver (app) | returned | **auto → Red** |
| Weigh-in → dump → weigh-out → waste class + extras | Yard (app) | processed → ready-to-invoice | stays Red; enters invoice queue |
| Finalize invoice (weigh slip) + **send** | Owner (QB) | invoiced, **48h clock** | **you → Flamingo** `CC? UNPAID (date)` |
| Paid — e-transfer / card-on-file | Owner (app) | paid/closed | **you → Purple** |

Colours are the *visual board*; the **app runs on its own internal status** (from crew/yard/owner
app-actions + QB), so nothing breaks if a colour is off.

---

## Workstream 1 — Two-event lifecycle + crew status (foundation)

- Model a bin rental as one logical job with a **drop event** + **pickup event** (both linked to
  the same rental record + bin), invoiced once after pickup+dump.
- Crew status is captured **in the app** (day-board / bin-tracker / yard-processing), **not** by
  editing the calendar: driver marks drop done / pickup done + HQ time + notes; yard records the
  weigh/dump/waste. These drive the invoice queue and reminders.
- Owner status buttons (work with every integration off): **"Invoice sent"** (start 48h),
  **"Received as e-transfer"** (paid), and later **"Charge card on file"**.

## Workstream 2 — Auto-paint the calendar (crew-completion colours)

- On a crew-completion app-action, the app sets the job's **status** and **writes the computed
  Google colorId to that job's event** — on the app's dedicated calendar **only**.
- Paint rules: hands-on paid-on-site → **Green**; hands-on awaiting e-transfer → **Red**;
  commercial done → **Green**; bin drop done → **Red**; bin pickup done → **Red**.
- **Never** paints over an owner's manual **Purple/Flamingo**. **Never** touches a live calendar
  (guard). Truck is stored separately so a status repaint doesn't lose the truck assignment.
- Uses the `gcal_event_id` already stored at booking. Reuses `ColourMap` to compute the colorId.
- **New writable target** in `gcal.py` = the app's dispatch calendar, with its own assertion
  (same shape as the TEST/reminder/punch guards). Tested on TEST; pointed at the go-live crew
  calendar at go-live.

## Workstream 3 — Card-on-file charging (Square, owner-pressed)

- **Capture** at bin booking: Square **Web Payments SDK** card field (Square-hosted; we never see
  the PAN) → token → `CreateCard` under a Square customer → store `square_customer_id`,
  `square_card_id`, `card_brand`, `card_last4`, `authorized_at/by`, `auth_note`. **No PAN/CVV.**
- **Charge** from the reminder/owner queue: `POST /square/charge-card-on-file` → `CreatePayment`
  (source = saved card, amount = invoice + 2.4%, idempotency key = job) → mark paid + audit row.
  Confirm dialog; one-charge guard; declines surfaced, no state change.
- New config: `SQUARE_APPLICATION_ID` (public, for the SDK). Needs **MOTO** enabled on the Square
  account + a card-on-file **authorization** checkbox at booking.
- New tables: `stored_card`, `card_charge` (tokens + audit only).

## Workstream 4 — Live QuickBooks sync (read-only) + Owner-Hub toggle

- **Read-only**: you still create + send invoices in QuickBooks. The app *watches* QBO for
  **invoice-sent** (start the 48h + add to reminders) and **payment** (clear the reminder,
  mark paid). The app never creates or sends an invoice.
- **Connect**: a one-time "Connect QuickBooks" OAuth button in the Owner Hub.
- **Matching** (the design question): how the app links a QB invoice to a bin job — a job/PO
  reference on the invoice, or a one-time "link this invoice" step. **Decision needed.**
- **Toggle + manual fallback**: an Owner-Hub **on/off switch** for QB auto-sync. With it off (or
  QB down), the Workstream-1 manual buttons do the same job. Manual is the foundation; QB is a
  layer on top.
- Detection via QBO webhooks (preferred) or polling.

---

## Build order & testing

1. **WS1** (lifecycle + manual buttons) — everything works with all integrations off.
2. **WS2** (auto-paint) — on the TEST calendar; verify it never touches live IDs, never paints
   over manual Purple/Flamingo.
3. **WS3** (card-on-file) — Square **sandbox** first: tokenize → save → charge → refund; double-
   click/idempotency; already-paid + no-card guards. Then production + one small live charge.
4. **WS4** (QuickBooks) — sandbox QBO company: sent + paid detection + matching; then the toggle;
   then production connect.
5. **Security review** before go-live (money + card + calendar writes).

## Decisions (resolved 2026-07-12, approved by Wes)

1. **QB invoice → job matching:** **reference code.** The app shows a short code per bin job
   (e.g. `BIN-4021`); Wes pastes it into the QuickBooks invoice PO/reference field; the app
   matches on it. (Chosen over click-to-link.)
2. **Card scope:** saved at the **customer** level — reusable for that customer's future bins.
3. **Who can charge:** **owner only.** The manager cannot press "Charge card on file."
4. **MOTO:** not a separate toggle for Square — card-not-present / card-on-file is supported on
   any online-enabled account (Wes's is, a real payment link succeeded). Real requirement is the
   customer authorization checkbox at booking. Confirm the keyed charge in sandbox.
5. **Sandbox first:** yes — Square sandbox + a QuickBooks sandbox before production.

### Pre-authorization — considered and rejected (use card-on-file instead)
Wes asked about pre-authing the card at drop. Rejected because it doesn't fit multi-week bin
rentals: (a) Square auth holds **expire (~6 days)** — gone before pickup; (b) you **can't
reliably capture more than the authorized amount**, but the final total (weight/dump) isn't known
until pickup; (c) a pre-auth **holds the customer's credit** (not truly free to them).
**Card-on-file achieves the same goal, better:** saving the card at drop verifies it's valid,
places **no hold**, and lets us charge the **exact final total + 2.4%** at invoice time — or
nothing, if they e-transfer.

## Risks & safeguards (summary)

- **Calendar:** live-ID guard stays; auto-paint only the dedicated calendar; never over manual
  Purple/Flamingo; TEST before go-live.
- **Charging:** tokens only (no PAN/CVV); idempotency + already-paid guard + confirm dialog;
  amount shown before it fires; stored authorization + audit.
- **QuickBooks:** read-only (never sends/creates invoices); toggle + manual fallback so an outage
  never blocks you.
- **Guardrail drift:** brief updated (§ above) so the sanctioned changes aren't reverted later.
