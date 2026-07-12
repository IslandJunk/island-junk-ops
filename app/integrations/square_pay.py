"""Square — payment links + card-on-file (WS3).

Historically LINKS only. WS3 adds card-on-file for residential bins (Wes's sanctioned guardrail
change — docs/bin-payments-and-calendar-plan.md): store a customer's card in SQUARE (Cards API,
so we only ever hold a TOKEN, never the PAN/CVV) and charge it with ONE **owner-pressed** call.
Still NO auto-charge (the charge fires only from an owner tap) and NO refund call. Card capture
is via the Web Payments SDK — the card field is Square-hosted, so the raw card never touches us.

Creds in `.env`; absent → dry-run (calls nothing). Uses httpx directly (already a dep) rather
than the Square SDK, to stay light on Python 3.14.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from app.core.config import settings


def is_configured() -> bool:
    return settings.is_square_configured


def _base_url() -> str:
    return ("https://connect.squareupsandbox.com"
            if settings.square_environment != "production"
            else "https://connect.squareup.com")


def create_payment_link(*, amount: Decimal | float | str, name: str,
                        note: str | None = None, currency: str = "CAD") -> dict:
    """Create a Square hosted payment link for `amount` (dollars). Returns
    {url, id, dry_run}. In dry-run (no creds) returns a placeholder and calls nothing.
    NEVER charges — the customer pays via the returned URL."""
    cents = int(round(float(Decimal(str(amount))) * 100))
    if cents <= 0:
        return {"url": None, "id": None, "dry_run": True, "error": "amount must be > 0"}
    if not is_configured():
        return {"url": None, "id": None, "dry_run": True, "amount_cents": cents, "name": name}

    import httpx
    body = {
        "idempotency_key": str(uuid.uuid4()),
        "quick_pay": {
            "name": name[:255],
            "price_money": {"amount": cents, "currency": currency},
            "location_id": settings.square_location_id,
        },
    }
    if note:
        body["description"] = note[:2000]
    resp = httpx.post(
        f"{_base_url()}/v2/online-checkout/payment-links",
        headers={
            "Authorization": f"Bearer {settings.square_access_token}",
            "Content-Type": "application/json",
            "Square-Version": "2025-01-23",
        },
        json=body, timeout=20,
    )
    resp.raise_for_status()
    link = resp.json().get("payment_link", {})
    return {"url": link.get("url"), "id": link.get("id"), "dry_run": False, "amount_cents": cents}


# ── Card-on-file (WS3) — store a card in Square, charge it owner-pressed ─────────

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.square_access_token}",
        "Content-Type": "application/json",
        "Square-Version": "2025-01-23",
    }


class SquareError(RuntimeError):
    """A Square API error (declined card, bad token, etc.) surfaced to the caller."""


def _post(path: str, body: dict) -> dict:
    import httpx
    resp = httpx.post(f"{_base_url()}{path}", headers=_headers(), json=body, timeout=30)
    if resp.status_code >= 400:
        errs = (resp.json().get("errors") or [{}]) if resp.headers.get("content-type", "").startswith("application/json") else [{}]
        detail = errs[0].get("detail") or errs[0].get("code") or resp.text[:200]
        raise SquareError(f"Square {resp.status_code}: {detail}")
    return resp.json()


def create_customer(*, given_name: str | None = None, family_name: str | None = None,
                    company_name: str | None = None, email: str | None = None) -> dict:
    """Create a Square customer to hang a card-on-file on. Returns {customer_id}."""
    if not is_configured():
        return {"customer_id": None, "dry_run": True}
    body: dict = {"idempotency_key": str(uuid.uuid4())}
    if given_name:
        body["given_name"] = given_name[:255]
    if family_name:
        body["family_name"] = family_name[:255]
    if company_name:
        body["company_name"] = company_name[:255]
    if email:
        body["email_address"] = email[:255]
    return {"customer_id": _post("/v2/customers", body).get("customer", {}).get("id"), "dry_run": False}


def save_card_on_file(*, source_token: str, customer_id: str,
                      cardholder_name: str | None = None) -> dict:
    """Store a card on file in Square (Cards API). `source_token` is the Web Payments SDK token
    (a sandbox test nonce in tests). Returns {card_id, brand, last4, exp_month, exp_year}. We
    NEVER receive or store the card number — Square keeps it; we hold only the returned card id."""
    if not is_configured():
        return {"card_id": None, "dry_run": True}
    card: dict = {"customer_id": customer_id}
    if cardholder_name:
        card["cardholder_name"] = cardholder_name[:96]
    body = {"idempotency_key": str(uuid.uuid4()), "source_id": source_token, "card": card}
    c = _post("/v2/cards", body).get("card", {})
    return {"card_id": c.get("id"), "brand": c.get("card_brand"), "last4": c.get("last_4"),
            "exp_month": c.get("exp_month"), "exp_year": c.get("exp_year"), "dry_run": False}


def charge_card_on_file(*, card_id: str, customer_id: str, amount: Decimal | float | str,
                        currency: str = "CAD", note: str | None = None,
                        idempotency_key: str | None = None) -> dict:
    """Charge a saved card (Payments API). THE ONE charge call in the app — fired ONLY from an
    owner tap, never automatically (guardrail change, plan §7). `idempotency_key` (pass the job
    id) makes a double-tap safe. Returns {payment_id, status, amount_cents}. Raises SquareError
    on decline/failure so the caller can show the reason and leave the job unpaid."""
    if not is_configured():
        return {"payment_id": None, "dry_run": True}
    cents = int(round(float(Decimal(str(amount))) * 100))
    if cents <= 0:
        return {"payment_id": None, "error": "amount must be > 0"}
    body: dict = {
        "idempotency_key": idempotency_key or str(uuid.uuid4()),
        "source_id": card_id,
        "customer_id": customer_id,
        "amount_money": {"amount": cents, "currency": currency},
        "location_id": settings.square_location_id,
        "autocomplete": True,
    }
    if note:
        body["note"] = note[:500]
    p = _post("/v2/payments", body).get("payment", {})
    return {"payment_id": p.get("id"), "status": p.get("status"),
            "amount_cents": (p.get("amount_money") or {}).get("amount"), "dry_run": False}
