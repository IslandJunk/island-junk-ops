"""Compute a job's Google colour from (status + assigned truck).

Colour is never stored as the source of truth — it's derived here from the job's
status and truck, then written to the calendar only at booking. Encodes the decided
lifecycle: Flamingo = residential unpaid; a booked job takes its truck's colour.
"""
from __future__ import annotations

from app.models.enums import JobStatus

# Status -> colour key, for statuses whose colour is a fixed status colour.
# `booked` is special: the colour is the assigned truck's colour (via colour_map).
STATUS_COLOUR_KEY: dict[JobStatus, str] = {
    JobStatus.unassigned: "sage",
    JobStatus.done: "basil",
    JobStatus.awaiting_payment: "tomato",   # waiting e-transfer / bin returned
    JobStatus.unpaid: "flamingo",           # residential unpaid (CC or e-transfer)
    JobStatus.invoiced: "grape",
}


def colour_key_for(status: JobStatus, truck_colour_key: str | None = None) -> str | None:
    """The colour key a job should carry. For a `booked` job pass the assigned
    truck's colour key; that's returned as-is."""
    if status == JobStatus.booked:
        return truck_colour_key
    return STATUS_COLOUR_KEY.get(status)
