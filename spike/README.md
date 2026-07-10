# Stack-Order Spike — Island Junk dispatch

**Question this answers (CLAUDE.md §6 / scheduling spec §2, the "highest-risk unknown"):**
Can we reliably read Google Calendar and recover the manager's **manual top-to-bottom
stacking order** of events — where colour = truck, vertical stack = route order, and the
real time lives in the headline, not the slot?

**Answer: YES, for the real-world case.** See the verdict below.

---

## How it works

Google Calendar's day/week grid positions an event vertically by its **slot start time**.
When the manager drags a job "under" another to set route order, the *only* thing that
persists is that event's start/end time — the Calendar API event resource has **no
separate "position" / z-order field** (only `start`, `end`, `created`, `updated`,
`colorId`, `summary`, …). So the vertical stack order *is* encoded as start-time order,
and `events.list(orderBy="startTime")` hands the stack back in the exact order it was built.

Two different uses of the slot time, kept separate (as the spec requires):

| Slot time used as…       | Verdict                                             |
|--------------------------|-----------------------------------------------------|
| the job's **real time**  | **Ignored** — real time is parsed from the headline |
| the **vertical order**   | **Read** — this is the route order                  |

## What the test creates (TEST calendar only, date 2026-09-15)

- **Main stack (6 events, distinct start times):** timed + untimed headlines interleaved,
  three same-colour pairs, **created in a deliberately shuffled order** so a pass can't be
  creation-order coincidence.
- **Tie block (3 events, identical start time):** the pathological case, to characterise
  what the API does when there's a true tie.

## Result (this run)

```
MAIN STACK  intended [0,1,2,3,4,5]  →  API returned [0,1,2,3,4,5]   PASS
            (created shuffled as [1,7,4,0,6,2] — so it's genuinely recovered, not echoed)
TIE BLOCK   3 events @ identical time → deterministic but NOT intent-meaningful order
```

- Same-colour pairs sorted correctly → **colour does not perturb order.**
- Untimed-headline events ("Yard pickup", "Property sweep") sort by slot exactly like timed
  ones → **untimed jobs hold their stack position** (no fake time invented).

## The one edge case: exact start-time ties

Two events on the **identical** start time return in a deterministic-looking but
**manager-meaningless** order. This does **not** bite in practice because a true tie renders
**side-by-side (columns)** in the UI, not as a clean vertical stack — so a real vertical
stack never contains an exact tie by construction.

**Production mitigation (belt & suspenders):**
1. At booking the app writes a **distinct** start time per event (it already owns the slot).
2. The read-sync **detects equal start times** and surfaces a tiny "these share a slot —
   nudge one" hint, turning the only ambiguity into a handled UX instead of a silent bug.
3. Do **not** depend on the API's tie order being meaningful (it isn't) — depend on times
   being distinct, which the UI's side-by-side rendering already enforces visually.

## Manual UI confirmation — DONE (passed)

The seeded events were written via the API, but a UI drag's *only* persisted effect is that
same start-time write, so the two are equivalent. To close the loop anyway, the events were
hand-manipulated directly in the Google Calendar UI and read back:

- **Drag / reorder** within a day → recovered in exact top-to-bottom order.
- **Stretch / spread** across the day (03:00–05:00 block spread out to 03:30–13:00) → recovered.
- **Move to a different day** → `read` finds them (wide window) and groups into a separate
  per-day board, each in correct route order.

The `read` explorer groups output **by day**, then shows a **per-truck (colour) slice** —
exactly how a truck's route is built (filter to colour → read stacked order). It flags only
**same-truck ties** (same colour AND same exact time), the sole case that is actually
ambiguous; a same-time collision across different colours is harmless (separate routes).

Re-run any time with `read` (below).

## Running it

```bash
# from repo root
spike/.venv/Scripts/python.exe spike/stack_order_spike.py all      # cleanup+seed+verify
spike/.venv/Scripts/python.exe spike/stack_order_spike.py read     # read-only, no writes
spike/.venv/Scripts/python.exe spike/stack_order_spike.py cleanup  # remove spike events
```

## Safety

- Talks to **one** calendar: the TEST id, hard-coded. The two live ids (Victoria, JOBS 2)
  are hard-coded as **forbidden**; the script aborts before any read or write if the target
  isn't exactly the TEST calendar (`assert_safe_target`).
- Only deletes events it created (matched by a private `ij_spike` tag) — never a blind wipe.
- `service-account-key.json` is git-ignored and never printed.
