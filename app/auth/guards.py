"""Access guards — enforced at the LOGIC layer (CLAUDE.md §3), not just hidden UI.

Mirrors the prototype's `isOwnerRow()` guard: the Manager Hub can manage crew but
must never edit the owner's row, and only the owner may grant owner-only flags.
"""
from __future__ import annotations

import re

from app.models.employee import Employee
from app.models.enums import OWNER_ONLY_GRANTABLE

_OWNER_RE = re.compile(r"owner", re.IGNORECASE)


class AccessDenied(Exception):
    """Raised when an actor attempts an action reserved for the owner."""


def is_owner_role(role: str | None) -> bool:
    return bool(role and _OWNER_RE.search(role))


def is_owner(emp: Employee) -> bool:
    return is_owner_role(emp.role) or ("owner" in (emp.access or []))


def assert_can_manage_employee(actor: Employee, target: Employee) -> None:
    """The owner row is untouchable by anyone but the owner (name/PIN/access/active)."""
    if is_owner(target) and not is_owner(actor):
        raise AccessDenied("Only the owner can edit the owner account.")


def assert_can_grant_access(actor: Employee, flags: list[str]) -> None:
    """owner / estimate / swing may only be granted by the owner."""
    if is_owner(actor):
        return
    blocked = OWNER_ONLY_GRANTABLE & set(flags or [])
    if blocked:
        raise AccessDenied(f"Only the owner can grant: {', '.join(sorted(blocked))}")
