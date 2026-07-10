"""Seed the real Victoria crew roster (from the clock-out board + Paul the manager).
Some are temp workers — the roster is fully editable (add/remove) from the Owner/
Manager hub; this is just the starting set. PINs default to 0000 (owner assigns
real, unique PINs before login). Idempotent.

    python -m scripts.seed_crew
"""
from __future__ import annotations

from sqlalchemy import select

from app.auth.security import hash_pin
from app.db.session import new_session
from app.models.employee import Employee
from app.models.enums import Brand, PayType

# name, role, salaried, time_tracked  (salaried: Paul/Jesse/Brody per CLAUDE.md §1)
CREW = [
    ("Paul", "Truck manager", True, False),
    ("Jesse", "Truck crew", True, True),
    ("Brody", "Truck crew", True, True),
    ("Cody S", "Truck crew", False, True),
    ("Zack", "Truck crew", False, True),
    ("Taryn", "Truck crew", False, True),
    ("Spencer", "Truck crew", False, True),
    ("Tyler", "Truck crew", False, True),
    ("Travis", "Truck crew", False, True),
    ("Troy", "Truck crew", False, True),
    ("Dylan", "Truck crew", False, True),
    ("Chris", "Truck crew", False, True),
    ("Ashton", "Truck crew", False, True),
    ("Roland", "Truck crew", False, True),
    ("Masson", "Truck crew", False, True),
]


def access_for(role: str) -> list[str]:
    if "manager" in role.lower():
        return ["manager", "truck", "yard", "bin", "hours"]
    return ["truck", "hours"]


def main() -> None:
    db = new_session()
    added = 0
    try:
        for name, role, salaried, tracked in CREW:
            if db.scalar(select(Employee).where(Employee.brand == Brand.victoria, Employee.name == name)):
                continue
            db.add(Employee(
                brand=Brand.victoria, name=name, role=role, pin_hash=hash_pin("0000"),
                access=access_for(role), active=True, time_tracked=tracked,
                pay_type=PayType.salaried if salaried else PayType.hourly,
            ))
            added += 1
        db.commit()
        print(f"Crew seeded: +{added} Victoria employees. NOTE: all PIN 0000 placeholder — "
              f"owner must assign real unique PINs before they can log in.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
