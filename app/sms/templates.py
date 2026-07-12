"""Message composition with OWNER-EDITABLE templates. The single place every outbound
message is worded: if the owner has edited the template for this message in the Owner Hub
(persisted as `ij_owner_cfg_v1` → `brand_setting`), use their wording; otherwise the
built-in default (`messages.py`). So "change the texts" = edit them in the Owner Hub.

Owner template keys (owner-hub `templates`) → message kind:
  confirm → booking_confirm · enroute → on_our_way · reminder → reminder · complete → completion
Placeholders the owner can use: {name} {date} {total} {subtotal} {address} {etransfer} {crew} {eta}
(the owner puts the literal `$` before {total} themselves, matching the prototype's seed).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.enums import Brand
from app.models.settings import BrandSetting
from app.sms import messages

_KIND_TO_TEMPLATE = {
    "booking_confirm": "confirm",
    "on_our_way": "enroute",
    "reminder": "reminder",
    "completion": "complete",
}


def _num(x) -> str:
    if x is None or x == "":
        return ""
    try:
        return f"{float(Decimal(str(x))):,.2f}"
    except (TypeError, ValueError, InvalidOperation):
        return str(x)


def _builtin(brand: Brand, kind: str, p: dict) -> str:
    if kind == "booking_confirm":
        return messages.booking_confirmation(brand, name=p.get("name"), when=p.get("when"), address=p.get("address"))
    if kind == "on_our_way":
        return messages.on_our_way(brand, name=p.get("name"), eta=p.get("eta"))
    if kind == "eta":
        return messages.next_customer_eta(brand, eta=p["eta"], name=p.get("name"))
    if kind == "reminder":
        return messages.reminder(brand, what=p["what"], name=p.get("name"), when=p.get("when"))
    if kind == "completion":
        return messages.residential_completion(
            brand, total=p["total"], gst=p["gst"], etransfer_email=p["etransfer_email"],
            name=p.get("name"), subtotal=p.get("subtotal"), card_fee=p.get("card_fee"))
    raise ValueError(f"unknown message kind '{kind}'")


def _owner_cfg(db: DbSession, brand: Brand) -> dict:
    row = db.scalar(select(BrandSetting).where(
        BrandSetting.brand == brand, BrandSetting.key == "ij_owner_cfg_v1"))
    return row.value if (row and isinstance(row.value, dict)) else {}


def _fill(tmpl: str, p: dict, profile: dict) -> str:
    sub = {
        "{name}": p.get("name") or "there",
        "{date}": p.get("when") or "",
        "{when}": p.get("when") or "",
        "{total}": _num(p.get("total")),
        "{subtotal}": _num(p.get("subtotal")),
        "{address}": p.get("address") or "",
        "{etransfer}": (profile.get("etransfer") or p.get("etransfer_email") or ""),
        "{crew}": p.get("crew") or "the crew",
        "{eta}": p.get("eta") or "",
    }
    out = tmpl
    for k, v in sub.items():
        out = out.replace(k, str(v))
    return out


def render(db: DbSession, brand: Brand, kind: str, params: dict) -> str:
    """The owner's edited template for this message (rendered), else the built-in default."""
    okey = _KIND_TO_TEMPLATE.get(kind)
    if okey:
        cfg = _owner_cfg(db, brand)
        tmpl = ((cfg.get("templates") or {}).get(okey) or "")
        if tmpl.strip():
            return _fill(tmpl, params, cfg.get("profile") or {})
    return _builtin(brand, kind, params)
