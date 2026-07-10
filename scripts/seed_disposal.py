"""Seed the Victoria disposal cost model from the approved rate sheet
(`prototypes/island-junk-rate-sheet-v14.html` -> DEFAULT_RATES.facilities /
DEFAULT_RATES.disposal): 7 facilities + 24 materials, brand-scoped, idempotent.

Each material links to a facility (FK). The prototype seed references facilities by
short name (`"Hartland"`); we resolve those to the full facility name
(`"Hartland (CRD landfill)"`) so the FK is real.

§9 requires effective-dated history (the prototype had none): on first seed — and
whenever a material's cost/price changes on a re-run — we append a
`disposal_rate_history` snapshot.

    python -m scripts.seed_disposal
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import new_session
from app.models.enums import Brand, DisposalRole
from app.models.rates import DisposalFacility, DisposalMaterial, DisposalRateHistory

# where material goes + who pays. role: cost = we pay · income = they pay us · free · sort = yard
FACILITIES: list[tuple[str, DisposalRole, str]] = [
    ("Hartland (CRD landfill)", DisposalRole.cost,
     "general refuse, wood, shingles, asbestos/controlled, paints & chemicals (monthly permit). Does NOT take mixed loads."),
    ("DL Disposal Yard", DisposalRole.cost, "clean / tested NEW drywall only."),
    ("McNutts", DisposalRole.cost, "concrete, rubble, fill / soil, yard waste, rock."),
    ("Waste Connections", DisposalRole.cost, "mixed plastic recycle (comingled). Cardboard is free to dump."),
    ("Williams Scrap Iron", DisposalRole.income,
     "picks metal up from the yard and pays us by weight (untracked income — periodic cheque)."),
    ("The Bottle Depot", DisposalRole.free,
     "picks up TVs, bulbs, electronics & batteries from the yard for recycle — free."),
    ("Yard sort", DisposalRole.sort,
     "mixed loads come back here, wood pulled, each stream goes to its facility. Cost = sum of the sorted streams."),
]

# materials registry — each maps to a facility, with our cost and what we charge.
# (m, fac_shortname, cost, price, unit, note) — cost/price None = blank (computed from streams).
MATERIALS: list[tuple] = [
    ("Mixed general (≤49% wood)", "Yard sort", None, 275, "/ton",
     "Cost = the sorted streams (wood, garbage, etc.) added up from Yard Processing."),
    ("Construction / demo (≥50% wood)", "Yard sort", None, 245, "/ton", "1-ton min; under 1 ton bills at $275/t."),
    ("Clean waste (general garbage)", "Hartland", 160, 175, "/ton", "Commercial hand-load general garbage."),
    ("General refuse (sorted)", "Hartland", 160, None, "/ton",
     "Hartland +$10 bin fee. The garbage portion left after a mixed load is sorted."),
    ("Clean wood", "Hartland", 80, 125, "/ton", ""),
    ("Treated / dirty wood", "Hartland", 110, 135, "/ton", "Includes cedar / wood shingles."),
    ("Drywall — clean / tested new", "DL Disposal Yard", 415, 415, "/ton",
     "Pass-through for now — mark up here whenever you want."),
    ("Mixed drywall (≤30%)", "Yard sort", None, 375, "/ton", ""),
    ("Drywall — small amount", "DL Disposal Yard", None, 25, "/bag", "Per contractor bag."),
    ("Clean concrete", "McNutts", 41, 80, "/ton", "$20 min."),
    ("Concrete w/ rebar", "McNutts", 80, 80, "/ton", ""),
    ("Rubble (brick / tile / mortar)", "McNutts", 60, 165, "/ton", "$20 min."),
    ("Stucco / plaster", "Hartland", None, 175, "/ton", "Charged as general waste; old-material testing may apply."),
    ("Clean soil / fill", "McNutts", 28, 65, "/ton", "$20 min · McNutts load min $31.50."),
    ("Yard waste (over 1 ton)", "McNutts", 53, 75, "/ton", "$20 min · under 1 ton uses the flat per-bin price."),
    ("Stumps", "McNutts", 250, None, "/ton", ""),
    ("Asphalt roofing", "Hartland", 110, 135, "/ton", ""),
    ("Cedar shake roofing", "Hartland", 110, 135, "/ton", "Charged as dirty wood."),
    ("Torch-on roofing", "Hartland", 160, 275, "/ton", "Goes as general waste."),
    ("Mixed plastic recycle (comingled)", "Waste Connections", None, 350, "/ton",
     "Comingled — emptied from Waste Mgmt bins, mostly on custom routes."),
    ("Cardboard", "Waste Connections", 0, 0, "free", "Free for us to dump."),
    ("Metal", "Williams Scrap Iron", 0, 0, "income",
     "Income — they pay us. A $10–15 recycle fee is charged to the customer only when the yard crew pulls metal from their bin."),
    ("Paints / chemicals", "Hartland", None, 25, "/crate", "Monthly permit. Min 1 crate ($25) if any present."),
    ("TVs / bulbs / electronics / batteries", "The Bottle Depot", 0, 0, "free pickup",
     "Customer item fees still apply (TV $5, etc.)."),
]


def _dec(x) -> Decimal | None:
    return None if x is None else Decimal(str(x))


def _resolve_facility(short: str, by_name: dict[str, DisposalFacility]) -> DisposalFacility | None:
    """Map a material's short facility name to the seeded facility (exact, else prefix)."""
    if short in by_name:
        return by_name[short]
    for name, fac in by_name.items():
        if name.startswith(short):
            return fac
    return None


def main() -> None:
    brand = Brand.victoria
    db = new_session()
    try:
        # --- facilities (upsert by name) ---
        by_name: dict[str, DisposalFacility] = {}
        fac_created = fac_updated = 0
        for name, role, note in FACILITIES:
            f = db.scalar(select(DisposalFacility).where(
                DisposalFacility.brand == brand, DisposalFacility.name == name))
            if f is None:
                f = DisposalFacility(brand=brand, name=name, role=role, note=note)
                db.add(f)
                fac_created += 1
            else:
                f.role, f.note = role, note
                fac_updated += 1
            by_name[name] = f
        db.flush()  # assign facility PKs before materials reference them

        # --- materials (upsert by m) + rate history on create/change ---
        mat_created = mat_updated = hist_added = unresolved = 0
        for m, fac_short, cost, price, unit, note in MATERIALS:
            fac = _resolve_facility(fac_short, by_name)
            if fac is None:
                print(f"  !! could not resolve facility '{fac_short}' for material '{m}'")
                unresolved += 1
            cost_d, price_d = _dec(cost), _dec(price)
            mat = db.scalar(select(DisposalMaterial).where(
                DisposalMaterial.brand == brand, DisposalMaterial.m == m))
            changed = False
            if mat is None:
                mat = DisposalMaterial(brand=brand, m=m, facility_id=fac.id if fac else None,
                                       cost=cost_d, price=price_d, unit=unit, note=note)
                db.add(mat)
                db.flush()
                mat_created += 1
                changed = True
            else:
                if mat.cost != cost_d or mat.price != price_d:
                    changed = True
                mat.facility_id = fac.id if fac else None
                mat.cost, mat.price, mat.unit, mat.note = cost_d, price_d, unit, note
                mat_updated += 1
            if changed:
                db.add(DisposalRateHistory(
                    brand=brand, material_id=mat.id, m=m,
                    cost=cost_d, price=price_d, unit=unit, changed_by="seed"))
                hist_added += 1

        db.commit()
        print(f"Victoria disposal seeded — facilities: +{fac_created}/~{fac_updated}, "
              f"materials: +{mat_created}/~{mat_updated}, history rows +{hist_added}"
              + (f", UNRESOLVED facilities: {unresolved}" if unresolved else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
