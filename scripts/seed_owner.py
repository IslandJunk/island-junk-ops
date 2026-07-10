"""Seed the initial owner + owner-security + one demo Victoria manager, so PIN
login can be tested end-to-end. Idempotent. Run AFTER migrations:

    python -m scripts.seed_owner

Demo PINs are placeholders — replace before anything real.
"""
from __future__ import annotations

from sqlalchemy import select

from app.auth.security import hash_password, hash_pin
from app.db.session import new_session
from app.models.employee import Employee
from app.models.enums import Brand, PayType
from app.models.owner_security import OwnerSecurity


def main() -> None:
    db = new_session()
    try:
        # Owner — shared across brands (brand = NULL).
        owner = db.scalar(select(Employee).where(Employee.role.ilike("%owner%")))
        if owner is None:
            owner = Employee(
                brand=None, name="Wes", role="Owner", pin_hash=hash_pin("4321"),
                access=["owner", "manager", "estimate", "swing", "hours"],
                active=True, time_tracked=False, pay_type=PayType.salaried,
                can_clock_others=True, see_all_trucks=True, edit_all_trucks=True,
            )
            db.add(owner)
            print("+ owner 'Wes' (PIN 4321)")

        # Owner Hub gate (global, single row).
        if db.scalar(select(OwnerSecurity)) is None:
            db.add(OwnerSecurity(password_hash=hash_password("owner"),
                                 phones=[], backup_codes=[], audit_log=[]))
            print("+ owner_security (password 'owner')")

        # Demo Victoria manager — locked to victoria.
        if db.scalar(select(Employee).where(Employee.name == "Manager (demo)")) is None:
            db.add(Employee(
                brand=Brand.victoria, name="Manager (demo)", role="Main manager",
                pin_hash=hash_pin("1111"), access=["manager", "truck", "yard", "bin", "hours"],
                active=True, time_tracked=False, pay_type=PayType.salaried,
            ))
            print("+ Victoria 'Manager (demo)' (PIN 1111)")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
