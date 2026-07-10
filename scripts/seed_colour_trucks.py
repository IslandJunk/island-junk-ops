"""Starter colour -> truck assignments for Victoria (manager edits in the hub).

Classic palette has only 3 hand-load colours (Tangerine/Peacock/Banana), so at most
3 hand-load trucks can run distinctly until the June-2026 expanded palette is loaded.
Bin colours (Graphite/Blueberry) are left unmapped until the bin truck's real number
is confirmed. Idempotent.

    python -m scripts.seed_colour_trucks
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import new_session
from app.models.colour_map import ColourMap
from app.models.enums import Brand

# colour key -> truck number ("" clears the assignment)
MAPPING = {
    "tangerine": "3",
    "peacock": "4",
    "banana": "5",
    "graphite": "",   # bin truck TBD
    "blueberry": "",
    "lavender": "",
}


def main() -> None:
    db = new_session()
    try:
        changed = 0
        for key, truck in MAPPING.items():
            r = db.scalar(select(ColourMap).where(ColourMap.brand == Brand.victoria, ColourMap.key == key))
            if r is None:
                continue
            new = truck or None
            if r.assigned_truck != new:
                r.assigned_truck = new
                changed += 1
        db.commit()
        print(f"Colour->truck starter map set (Victoria): Tangerine->3, Peacock->4, Banana->5. ({changed} changed)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
