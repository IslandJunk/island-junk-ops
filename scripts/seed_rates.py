"""Seed the Victoria rate card from CLAUDE.md §9 (residential + commercial loads,
special items, PPE, bin rates, yard waste, parking, travel). Scalar rates (labour
125, GST 5%, card fee 2.4%, ...) use the model defaults. Idempotent (one per brand).

    python -m scripts.seed_rates
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import new_session
from app.models.enums import Brand
from app.models.rates import RateCard

RESIDENTIAL_LOADS = {"1/8": 150, "1/4": 225, "1/3": 275, "1/2": 350, "2/3": 425, "3/4": 550, "7/8": 600, "full": 650}
RESIDENTIAL_MIN = {"low": 75, "mid": 85, "high": 95}
COMMERCIAL_LOADS = {"min": 75, "1/8": 135, "1/4": 200, "1/3": 250, "1/2": 300, "2/3": 385, "3/4": 450, "7/8": 500, "full": 550}
COMMERCIAL_INCLUDED_MIN = {"min": 0, "1/8": 15, "1/4": 15, "1/3": 20, "1/2": 30, "2/3": 45, "3/4": 45, "7/8": 50, "full": 60}
SPECIALS = [
    {"n": "TV", "price": 5, "unit": "each"},
    {"n": "Tire", "price": 7, "unit": "each"},
    {"n": "Mattress", "price": 15, "unit": "each"},
    {"n": "Freon", "price": 20, "unit": "each"},
    {"n": "Paint/chem/propane", "price": 25, "unit": "crate"},
    {"n": "Drywall (small)", "price": 25, "unit": "bag"},
    {"n": "Concrete/soil", "price": 20, "unit": "wheelbarrow"},
    {"n": "Battery", "price": 0, "unit": "ask"},
]
PPE = [
    {"n": "Hazmat suit", "price": 22}, {"n": "Gloves", "price": 5}, {"n": "Masks", "price": 5},
    {"n": "Heavy bags", "price": 1.15}, {"n": "Sawzall blades", "price": 11},
]
BIN_RATES = {"base": 225, "roofingBase": 250, "extraDay": 10, "maxTonnes": 4}
YARD_WASTE = {"12 yd": 40, "16 yd": 75, "20 yd": 100}
PARKING = {"costHr": 3.25, "chargeHr": 5}
TRAVEL = {"rate": 95, "roundTrip": True, "minMin": 0}


def main() -> None:
    db = new_session()
    try:
        rc = db.scalar(select(RateCard).where(RateCard.brand == Brand.victoria))
        created = rc is None
        if created:
            rc = RateCard(brand=Brand.victoria)
            db.add(rc)
        rc.residential_loads = RESIDENTIAL_LOADS
        rc.residential_min = RESIDENTIAL_MIN
        rc.commercial_loads = COMMERCIAL_LOADS
        rc.commercial_included_min = COMMERCIAL_INCLUDED_MIN
        rc.specials = SPECIALS
        rc.ppe = PPE
        rc.bin_rates = BIN_RATES
        rc.yard_waste = YARD_WASTE
        rc.parking = PARKING
        rc.travel = TRAVEL
        db.commit()
        print(f"Victoria rate_card {'created' if created else 'updated'} "
              f"(GST {rc.gst_pct}%, card fee {rc.card_fee_pct}%, full load ${RESIDENTIAL_LOADS['full']}).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
