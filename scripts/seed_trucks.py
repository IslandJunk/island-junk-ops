"""Seed Victoria dispatch trucks #3-7 (Isuzu NPRs, hands-on, per CLAUDE.md §7),
each with a default notification-prefs row. Crew leads are left blank (manager
sets them — never hardcoded). Idempotent.

The BIN TRUCK (Hino) is intentionally NOT seeded: its real dispatch number/label
needs confirming (the prototype's "12" is demo data). Add it once confirmed.

    python -m scripts.seed_trucks
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.session import new_session
from app.models.enums import Brand, TruckKind
from app.models.truck import Truck, TruckAlertPref

VICTORIA_HANDS_ON = ["3", "4", "5", "6", "7"]


def main() -> None:
    db = new_session()
    added = 0
    try:
        for num in VICTORIA_HANDS_ON:
            truck = db.scalar(
                select(Truck).where(Truck.brand == Brand.victoria, Truck.num == num)
            )
            if truck is None:
                truck = Truck(brand=Brand.victoria, num=num, kind=TruckKind.hands_on, active=True)
                db.add(truck)
                db.flush()  # get truck.id
                db.add(TruckAlertPref(truck_id=truck.id))  # defaults: all alerts on
                added += 1
        db.commit()
        print(f"Trucks seeded: +{added} Victoria hands-on trucks (#{', #'.join(VICTORIA_HANDS_ON)}).")
        print("NOTE: bin truck not seeded — confirm its real dispatch number/label with Wes.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
