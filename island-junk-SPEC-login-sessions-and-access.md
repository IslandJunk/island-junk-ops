# Island Junk — SPEC: Login, Sessions & Access

**Status:** Locked decision (Wes, 2026-06-15)
**Applies to:** the production app built in Claude Code. The HTML prototypes only demo the login screens; the full session + autosave layer described here is a production requirement, not something the prototype enforces.

---

## 1. The core principle

Once a person signs in, they **stay signed in and nothing they're doing is lost** until a deliberate end-of-day logout. There is **no idle timeout** — ever. The day's work stays put exactly as it was left until the shift is closed out.

---

## 2. Device types — set once per device

Each device is marked **one time, at setup**, as one of:

- **Shared work tablet** (lives in a truck / the yard; different people use it)
- **Personal phone** (one person's own device)

This is the only thing that changes how logout behaves (Section 4). Everything in Section 3 is identical on both.

---

## 3. What NEVER logs someone out or loses their work (both device types)

- **Screen off, phone in a pocket, app backgrounded, or a full device restart** → still signed in. They tap the device and land back on the **exact same screen** they left.
- **In-progress forms autosave continuously** — every field is saved the moment it's filled or tapped, not on a submit button. A half-filled drop form, residential calculator, weigh-in, etc. survives screen-off, an app being killed by the OS, or a reboot, and is **restored exactly** on reopen.
- **No idle timeout.** There is no "X minutes of no activity and you're logged out." Sitting idle never signs anyone out and never clears a form.

---

## 4. When it actually logs out

- **Personal phone:** clocking out does **NOT** log out — it just stops the clock. The person stays signed in (it's their own device; no PIN every morning).
- **Shared tablet:** clocking out **returns to the login screen** for the next person. Plus a **"Switch user"** button so the tablet can be handed off mid-day without anyone having to clock out.
- **Manual logout** is always available on any device ("Log out / Switch user"), regardless of type.

---

## 5. Overnight safety net

- If a session is still open from a **previous workday** because someone forgot to clock out or log out, the app forces a **fresh PIN login** the first time it's opened the next day. This stops a device from showing yesterday's person as still on shift.
- Primarily for **shared tablets**. **Personal phones** stay logged in across days and do **not** ask for a PIN every morning — the only time a personal phone forces a re-login is to close out a shift that was left running overnight.
- A clock left running past end of day (forgot to clock out) is handled per the payroll rules — see the payroll spec. This section is only about the login session, not the time math.

---

## 6. Roster & access model (current build — carries into production)

This is already built in the prototype and is the source of who can log in and what they can open.

- **Single source of truth:** the employee roster. (`ij_employees_v1` in the prototype; a proper DB table in production.) Each person record holds: **name, role, 4-digit PIN, access flags** (which hubs/tools they're allowed to open), and an **active** flag.
- **The owner manages it** in **Owner Hub → Employees & access**: add a person (name + PIN), edit anyone, tick which hubs each can open, and set someone **Inactive**.
- **The Main Hub login reads the roster** — it shows the active people for PIN sign-in. No names are hard-coded into the Main Hub; it always reflects whoever is in the roster.
- **No limit** on number of people. The six seeded names are demo data only.
- **Inactive** turns a login off while keeping that person's full history (for someone who leaves, or seasonal crew).
- **PINs are owner-set.** The demo PIN hint shown on the prototype login screen is removed in production.
- **Access flags gate the launcher** — after login, a person only sees the tiles/hubs they're cleared for. Manager and Owner tiles stay gated above the basic crew lanes.

---

## 7. Security notes for the build

- 4-digit PINs are for **speed on shared devices** — treat them as low-friction convenience auth, not high security. Sensitive areas (invoicing, payroll, access management, owner settings) sit behind the **Owner/Manager gate**, and the owner login carries 2FA (per the owner hub).
- **No card numbers stored anywhere.** Payments run through Square links. (Legacy plaintext card numbers in calendar event descriptions are a go-live cleanup item — see the punchlist.)
- **Form drafts are scoped per job and per user**, so a shared-device handoff never mixes two people's half-finished work. When a new person logs in on a shared tablet, they see their own work, not the previous user's unsaved draft.

---

*This spec captures the locked session/login decision plus the existing roster/access model so the Claude Code build implements them directly.*
