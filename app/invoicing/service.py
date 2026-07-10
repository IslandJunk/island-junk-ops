"""Ready-to-invoice queue (CLAUDE.md §11). Aggregates what's ready for the owner to
invoice — completed commercial field jobs, processed yard bins (with their disposal
margin), and roll-off bins overdue to bill. The app only SURFACES this; it never
invoices or charges a card (guardrail §2).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.bins import Bin
from app.models.enums import BinStatus, Brand
from app.models.field_job import FieldJob
from app.models.rates import DisposalMaterial
from app.models.yard_processing import YardProcessing
from app.yard.disposal import compute_load_margin

OVERDUE_DAYS = 14                         # roll-off out this long = flag to bill / confirm rental
_OUT = {BinStatus.dropped, BinStatus.full}


def _visit_total(visits) -> float | None:
    """Best-effort sum of a field job's visit totals (`visits[].totals.total|sub`)."""
    if not isinstance(visits, list):
        return None
    total = 0.0
    found = False
    for v in visits:
        t = (v.get("totals") if isinstance(v, dict) else None) or {}
        val = t.get("total", t.get("sub"))
        try:
            if val is not None:
                total += float(val)
                found = True
        except (TypeError, ValueError):
            pass
    return round(total, 2) if found else None


def invoice_queue(db: DbSession, brand: Brand, today: date | None = None) -> dict:
    today = today or date.today()

    commercial = [{
        "id": fj.source_id, "customer": fj.customer, "address": fj.address,
        "visits": len(fj.visits or []), "total": _visit_total(fj.visits),
    } for fj in db.scalars(select(FieldJob).where(
        FieldJob.brand == brand, FieldJob.type == "commercial", FieldJob.status == "done"))]

    materials = list(db.scalars(select(DisposalMaterial).where(DisposalMaterial.brand == brand)))
    bins_ready = []
    for yp in db.scalars(select(YardProcessing).where(
            YardProcessing.brand == brand, YardProcessing.processed.is_(True))):
        m = compute_load_margin(yp, materials)
        bins_ready.append({
            "code": yp.code, "customer": yp.customer, "waste_class": yp.waste_class,
            "processed_date": yp.processed_date.isoformat() if yp.processed_date else None,
            "charge": m["charge"], "our_cost": m["cost"], "margin": m["margin"],
            "recorded_dump_fee": m["recorded_dump_fee"],
        })

    cutoff = today - timedelta(days=OVERDUE_DAYS)
    overdue = []
    for b in db.scalars(select(Bin).where(Bin.brand == brand, Bin.status.in_(_OUT))):
        if b.drop_date and not b.pick_date and b.drop_date <= cutoff:
            overdue.append({
                "code": b.code, "customer": b.customer, "address": b.address,
                "drop_date": b.drop_date.isoformat(), "days_out": (today - b.drop_date).days,
            })
    overdue.sort(key=lambda x: x["days_out"], reverse=True)

    return {
        "brand": brand.value,
        "ready_to_invoice": {"commercial": commercial, "bins": bins_ready},
        "bins_overdue": overdue,
        "counts": {
            "ready": len(commercial) + len(bins_ready),
            "commercial": len(commercial), "bins": len(bins_ready),
            "bins_overdue": len(overdue),
        },
    }
