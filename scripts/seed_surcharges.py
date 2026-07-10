"""Seed Victoria's bin area surcharges (CLAUDE.md §9 — Victoria = bin surcharges only,
hand-load flat). Values from the approved rate sheet (`surcharges` + `roofingSurcharges`)
and the booking screen's town→alias map. Regular and roofing match except Sooke ($60 vs
$35). Idempotent (upsert by area name).

    python -m scripts.seed_surcharges
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.db.session import new_session
from app.models.enums import Brand
from app.models.rates import AreaSurcharge

# area_name -> (regular bin surcharge, roofing bin surcharge, aliases, is_base)
AREAS: list[tuple] = [
    ("Victoria / Saanich / Sidney / Westshore", 0, 0,
     ["victoria", "saanich", "sidney", "langford", "colwood", "westshore", "view royal", "esquimalt", "brentwood"], True),
    ("Oak Bay", 10, 10, ["oak bay"], False),
    ("Metchosin", 30, 30, ["metchosin"], False),
    ("Sooke / E. Sooke", 60, 35, ["sooke", "east sooke", "e. sooke"], False),
    ("Shawnigan", 75, 75, ["shawnigan"], False),
    ("Shirley", 90, 90, ["shirley"], False),
    ("Millbay", 100, 100, ["mill bay", "millbay"], False),
    ("Renfrew", 170, 170, ["renfrew"], False),
]


def main() -> None:
    brand = Brand.victoria
    db = new_session()
    try:
        created = updated = 0
        for name, reg, roof, aliases, is_base in AREAS:
            row = db.scalar(select(AreaSurcharge).where(
                AreaSurcharge.brand == brand, AreaSurcharge.area_name == name))
            if row is None:
                row = AreaSurcharge(brand=brand, area_name=name)
                db.add(row)
                created += 1
            else:
                updated += 1
            row.aliases = aliases
            row.hand_amount = None                       # Victoria hand-load is flat (no surcharge)
            row.bin_amount = Decimal(str(reg))
            row.roofing_bin_amount = Decimal(str(roof))
            row.is_base = is_base
        db.commit()
        print(f"Victoria area surcharges seeded — created {created}, updated {updated} "
              f"(base + {len(AREAS) - 1} surcharge areas; Sooke roofing $35 vs regular $60).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
