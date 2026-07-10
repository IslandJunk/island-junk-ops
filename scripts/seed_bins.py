"""Seed the real 75-bin Victoria fleet (numbers per Wes, 2026-07):
  8yd  : 8-01..8-04            (4)
  12yd : 12-01..12-16          (16, all lidded)
  16yd : 16-01..16-11          (11)
  20yd : 20-01..20-44          (44)
Leased to Nanaimo (ROSS, 11): 20-10,20-11,20-14,20-22,20-29,20-41,20-44,16-05,16-06,12-03,12-04.
Lidded 20yd + stationed at a customer: 20-20 (Cool-Aid), 20-39 (PHS).

All seeded brand=victoria (the fleet); `leased` flags the Nanaimo ones. When the
Nanaimo workspace is built, decide whether leased bins move to brand=nanaimo.
Idempotent.

    python -m scripts.seed_bins
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.db.session import new_session
from app.models.bins import Bin
from app.models.enums import Brand, BinStatus

SIZES = {8: 4, 12: 16, 16: 11, 20: 44}
NANAIMO_LEASED = {"20-10", "20-11", "20-14", "20-22", "20-29", "20-41", "20-44",
                  "16-05", "16-06", "12-03", "12-04"}
STATIONED = {"20-20": "Cool-Aid", "20-39": "PHS"}   # lidded 20yd, long-term at customer


def code(size: int, n: int) -> str:
    return f"{size}-{n:02d}"


def main() -> None:
    db = new_session()
    added = 0
    try:
        for size, count in SIZES.items():
            for n in range(1, count + 1):
                c = code(size, n)
                if db.scalar(select(Bin).where(Bin.brand == Brand.victoria, Bin.code == c)):
                    continue
                stationed = c in STATIONED
                db.add(Bin(
                    brand=Brand.victoria, code=c, size=size,
                    lidded=(size == 12 or c in STATIONED),
                    leased=(c in NANAIMO_LEASED),
                    stationed=stationed,
                    customer=STATIONED.get(c),
                    status=BinStatus.dropped if stationed else BinStatus.idle,
                ))
                added += 1
        db.commit()
        total = db.scalar(select(func.count()).select_from(Bin).where(Bin.brand == Brand.victoria))
        lidded = db.scalar(select(func.count()).select_from(Bin).where(Bin.brand == Brand.victoria, Bin.lidded.is_(True)))
        leased = db.scalar(select(func.count()).select_from(Bin).where(Bin.brand == Brand.victoria, Bin.leased.is_(True)))
        print(f"Bins seeded: +{added}. Victoria total {total} (lidded {lidded}, leased->Nanaimo {leased}, "
              f"stationed {len(STATIONED)}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
