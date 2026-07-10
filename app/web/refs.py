"""Reference-data bootstrap for the served prototypes.

The approved prototypes read reference data (fleet, colour map, ...) from
`localStorage`. Instead of their demo fallbacks, we inject the real DB data as an
inline `<script>` placed EARLY in the page (before the prototype's own scripts), so
`localStorage` is populated synchronously before anything reads it — no async races.

Each builder emits the exact shape a given `ij_*` key expects.
"""
from __future__ import annotations

import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.bins import Bin
from app.models.clock import ClockPunch
from app.models.colour_map import ColourMap
from app.models.customer import CompanyCustomer, PmBuilding, PmCompany, PmGroup, ResidentialCustomer
from app.models.employee import Employee
from app.models.enums import BinStatus, Brand, ColourKind, PayType
from app.models.field_job import FieldJob
from app.models.incident import Incident
from app.models.rates import DisposalFacility, DisposalMaterial, RateCard
from app.models.truck import Truck
from app.models.weigh import WeighLog


def _f(x) -> float | None:
    return float(x) if x is not None else None


def _money(x):
    """Rate-sheet money cell: a number, or "" for a blank (the prototype's convention)."""
    return float(x) if x is not None else ""

# §6: bin-truck colours vs hand-load colours (the prototype categorises trucks by this).
_BIN_COLOUR_KEYS = {"graphite", "blueberry"}


def build_fleet_v1(db: DbSession, brand: Brand) -> dict:
    """`ij_fleet_v1` -> { "<num>": {mgr: "<lead>"} }"""
    trucks = db.scalars(
        select(Truck).where(Truck.brand == brand, Truck.active.is_(True))
    ).all()
    return {t.num: {"mgr": t.lead or ""} for t in trucks}


def build_colourmap_v1(db: DbSession, brand: Brand) -> dict:
    """`ij_colourmap_v1` (v3) -> { current: { <key>: {cat, truck} } } for mapped colours."""
    rows = db.scalars(select(ColourMap).where(ColourMap.brand == brand)).all()
    current: dict[str, dict] = {}
    for r in rows:
        if r.kind == ColourKind.assignable and r.assigned_truck:
            cat = "Bin trucks" if r.key in _BIN_COLOUR_KEYS else "Hand-load trucks"
            current[r.key] = {"cat": cat, "truck": r.assigned_truck}
    return {"v": 3, "current": current}


# our BinStatus -> the bin-registry prototype's `state` values.
_BIN_STATE = {
    BinStatus.idle: "idle", BinStatus.reserved: "idle", BinStatus.dropped: "out",
    BinStatus.full: "out", BinStatus.returning: "returned", BinStatus.returned: "returned",
    BinStatus.to_sort: "to_sort", BinStatus.clearing: "clearing", BinStatus.ready_dump: "ready_dump",
    BinStatus.weighing: "ready_dump", BinStatus.maintenance: "idle", BinStatus.retired: "retired",
}


def build_bins_v1(db: DbSession, brand: Brand) -> list[dict]:
    """`ij_bins_v1` -> [{code, size, lidded, leased, state, type, job:{customer,address}}]."""
    bins = db.scalars(select(Bin).where(Bin.brand == brand)).all()
    out: list[dict] = []
    for b in bins:
        rec: dict = {"code": b.code, "size": b.size, "state": _BIN_STATE.get(b.status, "idle")}
        if b.lidded:
            rec["lidded"] = True
        if b.leased:
            rec["leased"] = True
        if b.type:
            rec["type"] = b.type
        if b.customer or b.address:
            rec["job"] = {"customer": b.customer or "", "address": b.address or ""}
        out.append(rec)
    return out


def build_employees_v1(db: DbSession, brand: Brand) -> list[dict]:
    """`ij_employees_v1` -> roster for the person-picker + access-gated tiles.
    NO PINs: login goes through the API (hashed verification), not client-side."""
    emps = db.scalars(
        select(Employee).where(
            Employee.active.is_(True), or_(Employee.brand == brand, Employee.brand.is_(None))
        )
    ).all()
    return [
        {"name": e.name, "role": e.role, "access": list(e.access or []), "active": e.active,
         "tracked": e.time_tracked, "salaried": e.pay_type == PayType.salaried}
        for e in emps
    ]


def build_rates_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_rates_v1` from the rate card. Returns None (skip injection -> prototype keeps
    its own defaults) if the brand has no rate card. Disposal facilities/materials +
    custom-customer rate profiles are emitted empty until seeded from real data."""
    rc = db.scalar(select(RateCard).where(RateCard.brand == brand))
    if rc is None:
        return None
    facs = db.scalars(select(DisposalFacility).where(DisposalFacility.brand == brand)).all()
    fac_name = {f.id: f.name for f in facs}
    mats = db.scalars(select(DisposalMaterial).where(DisposalMaterial.brand == brand)).all()
    return {
        "labourRate": _f(rc.labour_rate), "demoRate": _f(rc.demo_rate), "crewExtraRate": _f(rc.crew_extra_rate),
        "recycleCharge": _f(rc.recycle_charge), "diversionSurcharge": _f(rc.diversion_surcharge),
        "diversionReport": _f(rc.diversion_report), "gstPct": _f(rc.gst_pct), "cardFeePct": _f(rc.card_fee_pct),
        "parking": rc.parking or {}, "travel": rc.travel or {},
        "residentialLoads": rc.residential_loads or {}, "commercialLoads": rc.commercial_loads or {},
        "residentialMin": rc.residential_min or {}, "commercialIncludedMin": rc.commercial_included_min or {},
        "items": rc.specials or [], "ppe": rc.ppe or [],
        "bin": rc.bin_rates or {}, "yardWaste": rc.yard_waste or {},
        "facilities": [{"name": f.name, "role": f.role.value, "note": f.note or ""} for f in facs],
        "disposal": [{"m": m.m, "fac": fac_name.get(m.facility_id, ""), "cost": _money(m.cost),
                      "price": _money(m.price), "unit": m.unit or "", "note": m.note or ""} for m in mats],
        "customers": [],
    }


def build_incidents_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_incidents_v1`, newest first. None (keep demo) until real incidents exist."""
    rows = db.scalars(
        select(Incident).where(Incident.brand == brand).order_by(Incident.at.desc().nullslast())
    ).all()
    if not rows:
        return None
    return [{
        "id": r.source_id, "at": r.at.isoformat() if r.at else None, "type": r.type, "sev": r.sev,
        "told": r.told, "by": r.reported_by, "who": r.who,
        "date": r.incident_date.isoformat() if r.incident_date else None, "time": r.incident_time,
        "where": r.location, "truck": r.truck, "what": r.what, "action": r.action, "photos": r.photos or [],
    } for r in rows]


def build_clock_log_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_clock_log`. None (keep demo) until real punches exist."""
    rows = db.scalars(select(ClockPunch).where(ClockPunch.brand == brand)).all()
    if not rows:
        return None
    return [{
        "name": r.employee_name, "date": r.work_date.isoformat(),
        "at": r.work_date.isoformat() + "T00:00:00", "inTime": r.in_time,
        "outTime": r.out_time, "doneAt": r.done_time, "truck": r.truck,
    } for r in rows]


def build_field_jobs_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_jobs_v1` (crew multi-visit field jobs). None until real rows exist."""
    rows = db.scalars(select(FieldJob).where(FieldJob.brand == brand)).all()
    if not rows:
        return None
    return [{
        "id": r.source_id, "type": r.type, "status": r.status,
        "customer": r.customer, "address": r.address, "visits": r.visits or [],
    } for r in rows]


def build_weighlog_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_weighlog_v1` (yard weigh events). None until real rows exist."""
    rows = db.scalars(select(WeighLog).where(WeighLog.brand == brand)).all()
    if not rows:
        return None
    return [{
        "at": r.source_at, "date": r.weigh_date.isoformat() if r.weigh_date else None,
        "time": r.weigh_time, "who": r.who, "truck": r.truck, "bin": r.bin, "cls": r.cls,
        "source": r.source, "f": _f(r.front_kg), "r": _f(r.rear_kg), "total": _f(r.total_kg),
    } for r in rows]


def build_customers_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_customers_v1` (residential autofill). None until real customers exist.
    NOTE: coexists with the booking screen's small hardcoded `QB_CUST` demo const —
    fully retiring that demo needs a booking-screen edit (see PROGRESS)."""
    rows = db.scalars(select(ResidentialCustomer).where(ResidentialCustomer.brand == brand)).all()
    if not rows:
        return None
    return [{"first": r.first or "", "last": r.last or "", "phone": r.phone or "",
             "email": r.email or "", "addr": r.addr or ""} for r in rows]


def build_company_customers_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_company_customers_v1` (commercial accounts). None until real rows exist."""
    rows = db.scalars(select(CompanyCustomer).where(CompanyCustomer.brand == brand)).all()
    if not rows:
        return None
    return [{"id": str(r.id), "co": r.co, "name": r.name or r.co, "addr": r.addr or "",
             "contact": r.contact or "", "phone": r.phone or "", "email": r.email or "",
             "accounts": list(r.accounts or []), "src": r.src.value} for r in rows]


def build_pm_db_v2(db: DbSession, brand: Brand) -> list | None:
    """`ij_pm_db_v2` — the 3-level PM tree (company -> group -> building). None until data."""
    companies = db.scalars(select(PmCompany).where(PmCompany.brand == brand)).all()
    if not companies:
        return None
    groups = db.scalars(select(PmGroup).where(PmGroup.brand == brand)).all()
    buildings = db.scalars(select(PmBuilding).where(PmBuilding.brand == brand)).all()
    b_by_group: dict = {}
    for b in buildings:
        b_by_group.setdefault(b.group_id, []).append(
            {"id": str(b.id), "n": b.name or "", "a": b.address or "",
             "email": b.email or "", "contact": b.contact or "", "phone": b.phone or ""})
    g_by_co: dict = {}
    for g in groups:
        g_by_co.setdefault(g.company_id, []).append(
            {"id": str(g.id), "nm": g.nm or "", "bldgs": b_by_group.get(g.id, [])})
    out = []
    for c in companies:
        grps = g_by_co.get(c.id) or [{"id": str(c.id) + "-g", "nm": "", "bldgs": []}]
        out.append({"id": str(c.id), "nm": c.nm, "addr": c.addr or "", "email": c.email or "",
                    "contact": c.contact or "", "phone": c.phone or "", "src": c.src.value, "groups": grps})
    return out


_BUILDERS = {
    "ij_fleet_v1": build_fleet_v1,
    "ij_colourmap_v1": build_colourmap_v1,
    "ij_bins_v1": build_bins_v1,
    "ij_employees_v1": build_employees_v1,
    "ij_rates_v1": build_rates_v1,
    "ij_incidents_v1": build_incidents_v1,
    "ij_clock_log": build_clock_log_v1,
    "ij_jobs_v1": build_field_jobs_v1,
    "ij_weighlog_v1": build_weighlog_v1,
    "ij_customers_v1": build_customers_v1,
    "ij_company_customers_v1": build_company_customers_v1,
    "ij_pm_db_v2": build_pm_db_v2,
}


def reference_bootstrap_script(db: DbSession, brand: Brand, keys: list[str]) -> str:
    """An inline <script> that seeds the requested localStorage keys with real DB data.
    A builder returning None is skipped (the prototype keeps its own defaults)."""
    payload = {}
    for k in keys:
        if k not in _BUILDERS:
            continue
        v = _BUILDERS[k](db, brand)
        if v is not None:
            payload[k] = v
    sets = "\n".join(
        f"  localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v))});"
        for k, v in payload.items()
    )
    return "<script>/* Island Junk — reference data from DB */\ntry{\n" + sets + "\n}catch(e){}\n</script>"
