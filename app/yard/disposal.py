"""Disposal cost model — turn a `yard_processing` close-out into a margin.

The model (CLAUDE.md §9, data-model.md Domain C):

    customer charge = the headline `waste_class` material's price × net tonnage
    our cost        = headline material's own `cost` × net tonnage        (pass-through class)
                      OR, for a blank-cost "Yard sort" class, Σ over the six sorted
                      streams (junk/wood/drywall/concrete/metal/recycle) of
                      stream% × net tonnage × that stream's per-ton cost
    margin          = charge − cost

Every per-ton cost/price is read from the live `disposal_material` registry, so an owner
editing a rate on the rate sheet re-prices every load — one source of truth. This computes
the *disposal-class* margin only; per-item extras (TV $5, metal recycle fee, …) are billed
as separate lines and are out of scope here.

Net weight: prefer the record's `gross`/`tare` totals, else fall back to the axle pairs.
A tonne here is 1000 kg (matches the prototype's `n/1000` net readout).
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.enums import Brand
from app.models.rates import DisposalMaterial
from app.models.yard_processing import YardProcessing

# The six yard-sort streams (yard_processing.pct keys) → the material whose per-ton `cost`
# represents that sorted stream. Costs are pulled live from the registry at compute time.
STREAM_MATERIAL: dict[str, str] = {
    "junk": "General refuse (sorted)",         # garbage left after sorting → Hartland
    "wood": "Clean wood",                       # sorted wood → Hartland (dirty wood costs more — see decision note)
    "drywall": "Drywall — clean / tested new",  # sorted drywall → DL Disposal
    "concrete": "Clean concrete",               # sorted concrete → McNutts
    "metal": "Metal",                           # income — cost 0
    "recycle": "Cardboard",                     # free to dump — cost 0
}

# The yard-processing picker (WASTE_CLASSES) uses slightly different labels than the
# materials registry (`disposal_material.m`). Whitespace/case are normalised automatically;
# these cover the genuinely different wordings. (data-model.md flags this drift — the
# long-term fix is to drive the picker from the registry.)
WASTE_CLASS_ALIAS: dict[str, str] = {
    "New/post-1990 drywall": "Drywall — clean / tested new",
}


def _norm(s: str | None) -> str:
    """Lowercase + strip all whitespace, so 'Construction/demo' == 'Construction / demo'."""
    return "".join((s or "").split()).lower()


def _fnum(x) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def resolve_material(name: str | None, materials: list[DisposalMaterial]) -> DisposalMaterial | None:
    """Match a waste-class label to a registry material: exact → normalised exact →
    alias → normalised prefix. Returns None if nothing plausibly matches."""
    if not name:
        return None
    by_exact = {m.m: m for m in materials}
    if name in by_exact:
        return by_exact[name]
    by_norm = {_norm(m.m): m for m in materials}
    n = _norm(name)
    if n in by_norm:
        return by_norm[n]
    alias = WASTE_CLASS_ALIAS.get(name)
    if alias and _norm(alias) in by_norm:
        return by_norm[_norm(alias)]
    # picker label is a (normalised) prefix of a material — e.g. "Rubble" / "Yard waste".
    for mn, m in by_norm.items():
        if n and mn.startswith(n):
            return m
    return None


def net_kg(rec: YardProcessing) -> float | None:
    """Net junk kg = gross − tare, using the totals if present else the axle pairs."""
    gross = _fnum(rec.gross)
    if gross is None:
        gf, gr = _fnum(rec.gross_f), _fnum(rec.gross_r)
        gross = (gf or 0) + (gr or 0) if (gf is not None or gr is not None) else None
    tare = _fnum(rec.tare)
    if tare is None:
        tf, tr = _fnum(rec.tare_f), _fnum(rec.tare_r)
        tare = (tf or 0) + (tr or 0) if (tf is not None or tr is not None) else None
    if gross is None or tare is None:
        return None
    return round(gross - tare, 2)


def _per_ton(mat: DisposalMaterial | None, field: str) -> float | None:
    """A material's cost/price when it is a per-ton rate; None for /bag, /crate, free, income."""
    if mat is None:
        return None
    unit = (mat.unit or "").strip().lower()
    if unit and not unit.startswith("/ton"):
        return None
    return _fnum(getattr(mat, field))


def compute_load_margin(rec: YardProcessing, materials: list[DisposalMaterial]) -> dict:
    """Disposal-class margin for one processed load. Pure — no DB access."""
    warnings: list[str] = []
    nkg = net_kg(rec)
    ntons = round(nkg / 1000, 4) if nkg is not None else None
    if ntons is None:
        warnings.append("no net weight (gross/tare) — cannot price by tonnage")

    headline = resolve_material(rec.waste_class, materials)
    if rec.waste_class and headline is None:
        warnings.append(f"waste class {rec.waste_class!r} not in the disposal registry")

    # customer charge (per-ton headline price × tonnage)
    price = _per_ton(headline, "price")
    charge = round(price * ntons, 2) if (price is not None and ntons is not None) else None
    if headline is not None and price is None:
        warnings.append("headline class has no per-ton price — charge not computed here")

    # our cost
    streams: list[dict] = []
    cost: float | None = None
    cost_basis = "unknown"
    if headline is not None and ntons is not None:
        explicit = _per_ton(headline, "cost")
        if explicit is not None:
            cost_basis = "explicit"
            cost = round(explicit * ntons, 2)
        elif headline.cost is None:
            # blank cost → a Yard-sort class: sum the sorted streams.
            cost_basis = "streams"
            pct = rec.pct if isinstance(rec.pct, dict) else {}
            total = 0.0
            for key, mat_name in STREAM_MATERIAL.items():
                p = _fnum(pct.get(key))
                if not p:
                    continue
                sm = resolve_material(mat_name, materials)
                cpt = _fnum(sm.cost) if sm is not None else None
                if cpt is None:
                    cpt = 0.0
                    if sm is None:
                        warnings.append(f"stream material {mat_name!r} missing — costed at $0")
                stons = round(ntons * p / 100, 4)
                sc = round(stons * cpt, 2)
                total += sc
                streams.append({"stream": key, "pct": p, "tons": stons,
                                "material": mat_name, "cost_per_ton": cpt, "cost": sc})
            cost = round(total, 2)
            if not streams:
                warnings.append("yard-sort class with no stream % entered — cost is $0")

    margin = round(charge - cost, 2) if (charge is not None and cost is not None) else None

    return {
        "code": rec.code,
        "processed_date": rec.processed_date.isoformat() if rec.processed_date else None,
        "waste_class": rec.waste_class,
        "matched_material": headline.m if headline else None,
        "net_kg": nkg,
        "net_tons": ntons,
        "charge": charge,
        "cost": cost,
        "cost_basis": cost_basis,
        "streams": streams,
        "margin": margin,
        "recorded_dump_fee": _fnum(rec.dump_fee),
        "warnings": warnings,
    }


def load_margins(db: DbSession, brand: Brand) -> dict:
    """Every processed load's disposal margin for a brand, plus rolled-up totals."""
    materials = list(db.scalars(select(DisposalMaterial).where(DisposalMaterial.brand == brand)).all())
    recs = db.scalars(
        select(YardProcessing).where(
            YardProcessing.brand == brand, YardProcessing.processed.is_(True)
        ).order_by(YardProcessing.processed_date.desc().nullslast())
    ).all()
    loads = [compute_load_margin(r, materials) for r in recs]
    charge = round(sum(l["charge"] or 0 for l in loads), 2)
    cost = round(sum(l["cost"] or 0 for l in loads), 2)
    return {
        "brand": brand.value,
        "count": len(loads),
        "registry_materials": len(materials),
        "totals": {"charge": charge, "cost": cost, "margin": round(charge - cost, 2)},
        "loads": loads,
    }
