"""Seed the initial owner + owner-security + one demo Victoria manager, so PIN
login can be tested end-to-end. Idempotent. Run AFTER migrations:

    python -m scripts.seed_owner

Demo PINs are placeholders — replace before anything real.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from app.auth.security import hash_password, hash_pin
from app.db.session import new_session
from app.models.employee import Employee
from app.models.enums import Brand, PayType
from app.models.owner_security import OwnerSecurity

# Seed credentials are PLACEHOLDERS — never the real live PINs (this file is public).
# A fresh DB starts every account at "0000"; the owner sets real, unique PINs from the
# Owner Hub immediately after seeding. Override per-deploy with SEED_OWNER_PIN /
# SEED_MANAGER_PIN / SEED_OWNER_PASSWORD env vars if a specific initial value is wanted.
_PLACEHOLDER = "0000"
OWNER_PIN = os.environ.get("SEED_OWNER_PIN", _PLACEHOLDER)
MANAGER_PIN = os.environ.get("SEED_MANAGER_PIN", _PLACEHOLDER)
OWNER_PASSWORD = os.environ.get("SEED_OWNER_PASSWORD", _PLACEHOLDER)


def main() -> None:
    db = new_session()
    try:
        # Owner — shared across brands (brand = NULL).
        owner = db.scalar(select(Employee).where(Employee.role.ilike("%owner%")))
        if owner is None:
            owner = Employee(
                brand=None, name="Wes", role="Owner", pin_hash=hash_pin(OWNER_PIN),
                access=["owner", "manager", "estimate", "swing", "hours"],
                active=True, time_tracked=False, pay_type=PayType.salaried,
                can_clock_others=True, see_all_trucks=True, edit_all_trucks=True,
            )
            db.add(owner)
            print("+ owner 'Wes' (placeholder PIN — set a real one in the Owner Hub)")

        # Owner Hub gate (global, single row).
        if db.scalar(select(OwnerSecurity)) is None:
            db.add(OwnerSecurity(password_hash=hash_password(OWNER_PASSWORD),
                                 phones=[], backup_codes=[], audit_log=[]))
            print("+ owner_security (placeholder password; owner SMS 2FA is the real gate)")

        # Demo Victoria manager — locked to victoria.
        if db.scalar(select(Employee).where(Employee.name == "Manager (demo)")) is None:
            db.add(Employee(
                brand=Brand.victoria, name="Manager (demo)", role="Main manager",
                pin_hash=hash_pin(MANAGER_PIN), access=["manager", "truck", "yard", "bin", "hours"],
                active=True, time_tracked=False, pay_type=PayType.salaried,
            ))
            print("+ Victoria 'Manager (demo)' (placeholder PIN — set a real one in the Owner Hub)")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
