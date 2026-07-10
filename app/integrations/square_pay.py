"""Square — payment LINKS only. The app surfaces a pay-by-card link for a job amount; it
NEVER charges a card and never sends an invoice (guardrails §2/§3). This wrapper only ever
calls Square's Payment Links endpoint (a hosted checkout the CUSTOMER completes) — there is
deliberately no charge/refund call here.

Creds in `.env`; absent → dry-run (returns a placeholder link, calls nothing). Uses httpx
directly (already a dep) rather than the Square SDK, to stay light on Python 3.14.
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
