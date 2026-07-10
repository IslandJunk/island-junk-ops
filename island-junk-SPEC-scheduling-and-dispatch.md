# Island Junk — Scheduling & Dispatch Spec

_Section for the build doc. Source of truth for how the app reads Google Calendar to build truck schedules, handle reassignment, and read job times. Last updated this session._

---

## 0. The one-line principle

**Google Calendar is the manager's hub. The app reads it and mirrors it. The app only writes to the calendar at booking — never when the day is being reorganised.**

After a job exists, the manager manages it on the calendar exactly as he does today: colour it, drag it into the running order, edit its headline, add notes, change its time. The app watches all of that and keeps the truck schedules, crew views, notifications, and downstream signals in sync. The app is not a second place to re-manage jobs — it's the booking screen plus the tools the calendar can't do (field calculators, yard processing, weights, invoicing queue).

---

## 1. Colour = which truck (recolour = instant reassignment)

Colour is the **input**, not a label. On the calendar the manager sets/changes an event's colour, and that act **is** the truck assignment.

- Each truck maps to one colour (per the colour → truck map). Hand-load and bin trucks both.
- **Recolouring an event reassigns the job, automatically and instantly.** Orange (Truck A) → Blue (Truck B) means the job leaves Truck A's schedule and lands on Truck B's. No second step, no app round-trip.
- Each truck's day is built by filtering the calendar to that truck's colour.
- Status colours (done / awaiting e-transfer / bin returned / invoiced / CC-unpaid) overwrite truck colour later in the lifecycle, per the existing colour system — unchanged here.

This is the whole reason the colour scheme exists: one recolour is a complete, unambiguous instruction the app can act on with no extra input.

### 1a. Reassignment notifications (per-truck toggle)

When a recolour moves a job between trucks:

- The crew **losing** the job and the crew **gaining** the job both get a heads-up notification that their day changed.
- In the **Management Hub**, each truck has its own **notifications on/off toggle**. Off = that truck's crew stops receiving these reassignment alerts; everyone else keeps theirs. Manager-controlled, lives in the hub, per-truck.

---

## 2. Running order = vertical stacking on the calendar

The manager builds each truck's route by stacking events: book a job, colour it, drag it under the previous job; drag the next under that; and so on — for every truck, hand-load and bin.

- **Top-to-bottom stacking order IS the running order.** The app reads the sequence exactly as stacked.
- The app does **not** sort by the calendar's time slot, and does **not** sort by the time in the headline. Hand-stacked position wins.
- Each truck's day = (filter to that truck's colour) → (read in the manager's vertical order) → that ordered list is the route.

This resolves untimed jobs completely: a no-time bin-yard pickup sits wherever it was dropped in the stack — not forced early, not forced late. Timed and untimed jobs interleave naturally because position comes from the drag, not the clock.

**Build risk to nail on the TEST calendar:** Google Calendar reads stacking within a slot by start time first, then position. The production sync must capture the manual top-to-bottom order the way the manager sees it on the board. Behaviour is well-defined; the wiring needs careful testing before go-live.

---

## 3. Time = the headline, never the calendar slot

The calendar's clock is **fake**. Events are parked in early slots (a real 8–10am job may sit in the 3am slot) purely to fit everything on the board visually.

**Rules:**

- **Ignore the calendar event's start/end time entirely.** Never read it as the schedule, never display it, never sort by it.
- The real time is whatever the manager typed into the **headline**. The app parses the time out of the headline text and uses that everywhere — crew views, "on our way" texts, display.
- **When a job is shuffled (recoloured, dragged, reordered), the app never touches the headline or the event's time.** Shuffling changes the truck and/or the order — never the title or the clock.
- When the manager edits the headline to change the time, the app re-reads the new time from the headline. **Headline is the source of truth for time.**

### 3a. Headline time format (fixed day, no AM/PM)

Workday is fixed **7:30am–3:30pm**, so numbers never cross noon and no AM/PM is needed.

- Accepts: a single time (`8`, `1230`) or a range (`8-9`, `1-3`, `1230-2`), with or without a trailing am/pm (ignored if present).
- Interpreted against the fixed day: `1-3` = 1:00–3:00pm, `8-9` = 8:00–9:00am, `1230-2` = 12:30–2:00pm.
- A single number = a start with no window. A range = exactly that window (1-hour, 2-hour, or anything the manager types).
- **Time is never required.** No time pattern in the headline = the job is **untimed** ("anytime"). It still shows and still holds its place in the stack; no fake time is invented. (Common for bin-yard pickups, property sweeps.)

### 3b. Parser safeguard (booking-screen time field)

Reading time from free-typed headlines is reliable until something odd is typed (`8 til done`, `noon`, `8-`, a unit/address number that looks like a range, etc.). Safeguard:

- The **booking screen has its own optional time field**: start + optional end (for a window) + a clear "no time" option.
- When set there, the app owns the time as real data **and** stamps it into the headline in the standard format — so every booked job starts clean and machine-readable.
- After that, headline edits on the calendar are re-read by the parser. New jobs are clean by construction; the parser is the fallback for hand-edits, not the only line of defence.

---

## 4. Manager-only notes on the calendar (the `#` rule)

The manager keeps non-job entries on the calendar: the daily truck roster (which truck, its colour, who's driving it), and loose reminders ("gate code at Harris", "call supplier"). These are **for the manager's eyes on Google Calendar only** and must be **completely invisible to the app**.

**The rule — a leading `#` in the title.**

- Any calendar entry whose **title's first non-whitespace character is `#`** is a **manager note, not a job**. The app **ignores it entirely**.
- "Ignored entirely" means everywhere, not just as a job: it is **never** read in as a job, **never** placed in any truck's colour filter, **never** given a spot in the stacked route order, **never** parsed for a time, and **never** included in any crew view, "on our way", or ETA text. It does not exist to the app.
- The app also **never writes to, edits, recolours, or deletes** a `#` entry — same as every other calendar entry (the app only writes at booking, and it never creates notes).
- **Position doesn't matter.** These notes appear as all-day banner items, at the top of a day, or at the bottom of a day — the rule is title-based, so it catches all three the same way.
- **Colour doesn't matter.** A `#` note can be any colour, including a truck colour, without ever being mistaken for that truck's job. The `#` wins over colour.

**Guard against false positives.** The marker only counts at the **start** of the title. A job whose title merely contains a `#` elsewhere (`Load #42`, `#3 truck`) is a normal job and is **not** skipped — only a leading `#` marks a note. (Trim leading spaces first, then test the first character, so an accidental leading space doesn't defeat the rule.)

**Already-synced calendars:** entries created before this rule won't have the `#` yet. Adding `#` to the front of existing manager-notes (from today forward, which is all the app reads) is a **one-time manual pass by the manager** on Google Calendar — the app never edits the live calendar to do it.

---

## 5. What the app reads vs. writes

| Action | Where it happens | App behaviour |
|---|---|---|
| Create a job | Booking screen | App **writes** the event to the calendar (only write after booking) |
| Assign / change truck | Recolour on calendar | App **reads**, moves job to that truck's schedule instantly, fires notifications |
| Set running order | Drag/stack on calendar | App **reads** vertical order as the route |
| Set / change time | Headline text | App **reads** time from headline; ignores calendar slot |
| Add notes / scope | Event body or headline | App **reads** and surfaces to the right crew |
| Manager note (title starts with `#`) | Anywhere on the calendar | App **ignores completely** — not a job, no colour filter, no route slot, no time, no text; never edited |

The app is a reader for everything after booking. It writes once (booking), then mirrors the calendar.

---

## 6. Hard boundaries (unchanged standing rules)

- **Live "ISLAND JUNK VICTORIA" calendar is READ-ONLY until go-live.** All two-way-sync development and testing happens on the dedicated **TEST calendar** only. At go-live a brand-new calendar is created and the crew migrated; the live calendar is never repurposed.
- **No edit ever touches money.** Reassigning, reordering, recolouring, adding/removing a truck — none of it charges a card or sends an invoice. Invoicing and card-charging stay manual, owner-only.
- The colour/status scheme drives the Make.com revenue signal. The app must preserve the exact status colours Make keys on. Reassignment changes which truck colour an event carries; that's expected and fine — what must not break is the status-colour semantics the signal depends on.

---

## 7. Open items to confirm later

- **Per-truck crew view** (future pass): each crew opens to just their own stops, derived from their colour's stacked events.
- Exact notification channel + copy for the reassignment heads-up (SMS via the shared updates line — see the SMS spec).
- Production capture of manual stacking order on Google Calendar — prove on TEST calendar.
- Whether "no time" jobs need any visual marker in crew view beyond sitting in stack position.
