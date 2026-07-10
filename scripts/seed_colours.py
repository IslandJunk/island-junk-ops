"""Seed the dispatch colour map for both brands, per the decided scheme:
Flamingo = STATUS only; bin truck = Graphite/Blueberry; Sage = locked Unassigned.
Truck assignments are left blank (the manager sets colour->truck). Idempotent.

    python -m scripts.seed_colours
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import new_session
from app.models.colour_map import ColourMap
from app.models.enums import Brand, ColourKind

# key, google_color_id, display name, hex (Google classic), kind, status_meaning
PALETTE = [
    ("lavender",  1, "Lavender",  "#7986CB", ColourKind.assignable, None),
    ("sage",      2, "Sage",      "#33B679", ColourKind.unassigned, "Unassigned — no truck yet"),
    ("grape",     3, "Grape",     "#8E24AA", ColourKind.status,     "Invoiced / charged"),
    ("flamingo",  4, "Flamingo",  "#E67C73", ColourKind.status,     "Residential unpaid (bin CC or e-transfer)"),
    ("banana",    5, "Banana",    "#F6BF26", ColourKind.assignable, None),
    ("tangerine", 6, "Tangerine", "#F4511E", ColourKind.assignable, None),
    ("peacock",   7, "Peacock",   "#039BE5", ColourKind.assignable, None),
    ("graphite",  8, "Graphite",  "#616161", ColourKind.assignable, None),
    ("blueberry", 9, "Blueberry", "#3F51B5", ColourKind.assignable, None),
    ("basil",    10, "Basil",     "#0B8043", ColourKind.status,     "Done / on route"),
    ("tomato",   11, "Tomato",    "#D50000", ColourKind.status,     "Waiting on e-transfer / bin returned"),
]


def main() -> None:
    db = new_session()
    added = updated = 0
    try:
        for brand in (Brand.victoria, Brand.nanaimo):
            for key, gid, name, hexv, kind, meaning in PALETTE:
                row = db.scalar(
                    select(ColourMap).where(ColourMap.brand == brand, ColourMap.key == key)
                )
                if row is None:
                    row = ColourMap(brand=brand, key=key)
                    db.add(row)
                    added += 1
                else:
                    updated += 1
                # Refresh the palette definition; DON'T touch manager-set assigned_truck.
                row.name = name
                row.google_color_id = gid
                row.hex = hexv
                row.kind = kind
                row.status_meaning = meaning
                row.is_locked = kind is not ColourKind.assignable  # sage + status locked from truck assign
        db.commit()
        print(f"Colour map upserted: +{added} new, {updated} updated ({len(PALETTE)} colours x 2 brands).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
