"""Imports every model so the ORM registry + Base.metadata are complete.

Import THIS (not individual model modules) wherever a full registry is needed —
app startup, Alembic, and scripts — so cross-table foreign keys always resolve.

Kept out of app/models/__init__.py on purpose: __init__ must stay empty to avoid
an import cycle (app.db.base -> app.db.types -> app.models.enums would trigger a
package __init__ that re-imports models while app.db.base is half-initialized).
"""
from app.models import (  # noqa: F401
    attendance,
    bin_field,
    bins,
    clock,
    colour_map,
    contract,
    customer,
    dayboard,
    employee,
    field_job,
    incident,
    job,
    maintenance,
    ops,
    owner_security,
    rates,
    reminder,
    session,
    settings,
    truck,
    weigh,
    yard_processing,
)
