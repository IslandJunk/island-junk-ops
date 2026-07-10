# Island Junk — SPEC: SMS & Customer Texting

**Status:** Locked decision (Wes, 2026-07). Supersedes any earlier "A2P 10DLC" wording in the notes.
**Applies to:** the production app built in Claude Code. Authoritative for all SMS behaviour.

---

## 0. The one-line principle

**The app sends automated customer updates from one dedicated "updates" line. The manager's real
back-and-forth texting stays on the main brand lines, on his own phone, exactly as it works today —
the app never sends from, hosts, or ports those.**

---

## 1. The numbers (three, with clear jobs)

| Line | Number | Who uses it | In the app? |
|---|---|---|---|
| **Victoria main line** | 778-966-5865 | The manager, by hand, for real two-way customer texting + calls. Public number on trucks/ads. | **No.** Stays with the current carrier (Rogers), untouched. The app does not send from or host it. |
| **Nanaimo main line** | 778-977-5865 | Same, for Nanaimo. Public number on Nanaimo trucks/ads. | **No.** Same — untouched. |
| **App updates line** | **778-906-5865** (fresh local Island number, Voice+SMS+MMS) | The **app only**, to send automated updates. **Shared by both brands.** | **Yes** — this is the only number the app sends from. |

There is **one** app updates line total, not one per brand. Wes confirmed both brands run their
automated texts off the same number. Brand is made clear in the message text, and replies are routed
by which customer sent them (Section 3), so one shared number never blurs the two brands.

## 2. What the updates line sends (outbound, send-only)

All automated, all from the updates line, for both brands:
- Booking confirmation
- "On our way" when the crew heads out
- **Next-customer ETA** (crew marks a job done + enters ETA to the next stop → that customer is texted an approximate arrival; the crew-entered estimate is the source, never raw map distance)
- Bin-pickup / appointment reminders
- Residential completion text (photo + price + GST + e-transfer email + "put your address in the memo")

Every message names the brand in its own text, e.g. "Hi, it's **Island Junk Solutions** — on our way…"
or "…**Island Junk Nanaimo**…", so the customer knows who it's from even though the sending number
isn't the one on their invoice.

## 3. What happens when a customer replies to the updates line

The line is send-only by intent, so an inbound text is handled automatically:

1. **STOP / HELP first.** If the message is an opt-out (STOP/UNSUBSCRIBE/etc.) or help (HELP) keyword,
   handle it per compliance **before** anything else — STOP opts the number out of future sends; HELP
   returns the business info. (Section 5.)
2. **Otherwise, auto-reply** — an "unmonitored line" message that points the customer to the right
   **main** line. The app looks up the sender in the customer list:
   - Recognised **Victoria** customer → give **778-966-5865**.
   - Recognised **Nanaimo** customer → give **778-977-5865**.
   - **Not recognised** → list both numbers.

   Example (recognised Victoria customer):
   > "Thanks for the reply! This is Island Junk's automated text line, so it isn't monitored. To reach
   > our crew, call or text us at 778-966-5865 and we'll help you out."

3. **Log + optional nudge.** Record the inbound message on the job, and optionally notify the manager
   (in-app notification and/or a copy to his phone/email) as a safety net so a reply is never missed —
   even though the intent is that customers use the main lines.

The per-customer routing is the reason a single shared updates line is safe across both brands: the app
sorts every reply by the recognised customer's brand.

## 4. Number type, registration & deliverability (Canada)

- The updates line is a **Canadian local number**. **US A2P 10DLC does not apply** — that framework is
  for messages sent to **US** recipients; Island Junk texts Canadian customers only.
- A Canadian local number needs **no toll-free verification** and **no US-style 10DLC campaign
  registration** to send domestically. Twilio may require proof of a **local business address** to
  activate a Canadian number (have the business address + Canadian Business Number ready).
- **Deliverability trade-off:** Canadian carriers filter application-to-person traffic on local numbers
  more aggressively than on verified toll-free numbers. For this app's traffic — low-volume,
  transactional, opted-in — a local number typically delivers fine. **If delivery ever degrades, the
  fallback is a verified toll-free number** (business profile + toll-free verification, ~2 weeks, BRN
  required as of Feb 2026 — the company's Business Number satisfies this).

## 5. Compliance (build it in)

- **STOP/HELP always honoured**, and handled *before* the auto-reply redirect. Use Twilio's Advanced
  Opt-Out or the app's own handling — either way STOP opts out and HELP returns business info.
- **Opt-in:** customers hand over their number to book a job, which supports transactional messages;
  keep the consent record. (Canada's CASL — confirm consent practices with the business; not legal advice.)
- **No card numbers in any message.** Payment goes through a Square link, never card digits over SMS.

## 6. Two-brand / setup-screen note

The **shared updates line is set up once** and serves both brands. Each brand still has its own **main
public line** (Victoria 778-966-5865, Nanaimo 778-977-5865) that the manager runs by hand — those are
the per-brand "texting numbers" in the workspace/setup model. Standing up Nanaimo does **not** require a
second app updates line; it reuses the shared one, with replies routed to the Nanaimo main line for
Nanaimo customers.

---

*This spec captures the locked SMS decision so the Claude Code build implements it directly. The
operational steps to create the account and buy the number are in the Twilio setup guide.*
