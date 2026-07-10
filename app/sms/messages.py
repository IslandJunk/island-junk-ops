"""Outbound message composition (SMS spec §2). Every message NAMES ITS BRAND in the text
(the sending number isn't the one on the customer's invoice), and NO message ever contains
card numbers (§5 — payment always goes through a Square link).

Pure functions: given the facts, return the message body. No I/O — trivially unit-testable.
"""
from __future__ import annotations

from app.models.enums import Brand

# Brand as the customer should see it in the text (spec §2 examples).
BRAND_NAME: dict[Brand, str] = {
    Brand.victoria: "Island Junk Solutions",
    Brand.nanaimo: "Island Junk Nanaimo",
}
_STOP = "Reply STOP to opt out."


def brand_name(brand: Brand) -> str:
    return BRAND_NAME.get(brand, "Island Junk")


def _money(x) -> str:
    try:
        return f"${float(x):,.2f}"
    except (TypeError, ValueError):
        return str(x)


def booking_confirmation(brand: Brand, *, name: str | None = None, when: str | None = None,
                         address: str | None = None) -> str:
    """Sent when a job is booked."""
    hi = f"Hi {name}," if name else "Hi,"
    when_txt = f" for {when}" if when else ""
    where = f" at {address}" if address else ""
    return (f"{hi} it's {brand_name(brand)}. You're booked{when_txt}{where}. "
            f"We'll text you when we're on our way. {_STOP}")


def on_our_way(brand: Brand, *, name: str | None = None, eta: str | None = None) -> str:
    """Sent when the crew heads out."""
    hi = f"Hi {name}," if name else "Hi,"
    eta_txt = f" We expect to arrive around {eta}." if eta else ""
    return f"{hi} it's {brand_name(brand)} — we're on our way!{eta_txt}"


def next_customer_eta(brand: Brand, *, eta: str, name: str | None = None) -> str:
    """Crew marks a job done + enters the ETA to the NEXT stop; that next customer gets this.
    The crew's estimate is the source — never raw map distance (spec §2)."""
    hi = f"Hi {name}," if name else "Hi,"
    return (f"{hi} it's {brand_name(brand)}. Our crew is finishing up the job before yours and "
            f"expects to reach you around {eta}. See you soon!")


def reminder(brand: Brand, *, what: str, name: str | None = None, when: str | None = None) -> str:
    """Bin-pickup / appointment reminder."""
    hi = f"Hi {name}," if name else "Hi,"
    when_txt = f" on {when}" if when else ""
    return f"{hi} a reminder from {brand_name(brand)}: {what}{when_txt}."


def residential_completion(brand: Brand, *, total, gst, etransfer_email: str,
                           name: str | None = None, subtotal=None, card_fee=None) -> str:
    """Residential completion text: price + GST + e-transfer email + "put your address in the
    memo" (spec §2). The job photo is attached as MMS media by the sender. NEVER any card
    number (§5) — e-transfer only; a Square link is sent separately if a card is used."""
    hi = f"Hi {name}," if name else "Hi,"
    lines = [f"{hi} thanks from {brand_name(brand)} — all done!"]
    if subtotal is not None:
        lines.append(f"Subtotal {_money(subtotal)}")
    lines.append(f"GST {_money(gst)}")
    if card_fee:
        lines.append(f"Card fee {_money(card_fee)}")
    lines.append(f"Total {_money(total)}")
    lines.append(f"Please e-transfer to {etransfer_email} and put your address in the memo. Thank you!")
    return "\n".join(lines)
