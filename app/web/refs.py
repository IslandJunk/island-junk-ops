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

from app.auth.guards import is_owner
from app.models.attendance import Attendance, BreakLog
from app.models.bin_field import BinWeigh
from app.models.bins import Bin
from app.models.clock import ClockPunch
from app.models.dayboard import DayboardOverlay
from app.models.colour_map import ColourMap
from app.models.contract import Contract
from app.models.customer import CompanyCustomer, PmBuilding, PmCompany, PmGroup, ResidentialCustomer
from app.models.employee import Employee
from app.models.enums import ACCESS_FLAGS, BinStatus, Brand, ColourKind, PayType, ReminderKind
from app.models.field_job import FieldJob
from app.models.incident import Incident
from app.models.maintenance import DefectFlag, MaintenanceDoc
from app.models.ops import FollowupReview, UsageEvent
from app.models.rates import AreaSurcharge, DisposalFacility, DisposalMaterial, RateCard
from app.models.reminder import Reminder
from app.models.settings import BrandSetting, DayNote
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


# our BinStatus -> the bin-TRACKER prototype's `status` values (driver tool). Distinct
# from the registry `state` map above; `stationed`/`leased` ride as booleans, not statuses.
_BIN_TRACKER_STATUS = {
    BinStatus.idle: "in_yard", BinStatus.reserved: "in_yard", BinStatus.dropped: "dropped",
    BinStatus.full: "dropped", BinStatus.returning: "returning", BinStatus.returned: "returning",
    BinStatus.to_sort: "returning", BinStatus.clearing: "returning", BinStatus.ready_dump: "returning",
    BinStatus.weighing: "returning", BinStatus.maintenance: "maintenance", BinStatus.retired: "maintenance",
}


def _iso(d) -> str:
    return d.isoformat() if d else ""


def _hm(t) -> str:
    return t.strftime("%H:%M") if t else ""


def _nums(x):
    """A weight/fee cell: the number, or "" for empty (the tracker's blank convention)."""
    return float(x) if x is not None else ""


def build_bins_full_v1(db: DbSession, brand: Brand) -> list[dict] | None:
    """`ij_bins_full_v1` — the RICH bin shape the driver's bin-tracker uses (its in-memory
    `seed()` replacement). Every field the tool reads/derives, so a drop/pick/weigh/repair
    round-trips through `apply_bins`. Distinct key from the lean `ij_bins_v1` that the
    registry + yard read, so those screens are untouched. None until the fleet is seeded."""
    bins = db.scalars(select(Bin).where(Bin.brand == brand)).all()
    if not bins:
        return None
    out: list[dict] = []
    for b in bins:
        status = "stationed" if b.stationed else _BIN_TRACKER_STATUS.get(b.status, "in_yard")
        rec = {
            "code": b.code, "size": b.size, "lidded": bool(b.lidded), "leased": bool(b.leased),
            "stationed": bool(b.stationed), "customLid": bool(b.custom_lid), "status": status,
            "customer": b.customer or "", "address": b.address or "", "town": b.town or "",
            "roofing": bool(b.roofing), "base": (float(b.base) if b.base is not None else 0),
            "surcharge": (float(b.surcharge) if b.surcharge is not None else None),
            "dropDate": _iso(b.drop_date), "dropTime": _hm(b.drop_time), "pickDate": _iso(b.pick_date),
            "scheduledPickup": _iso(b.scheduled_pickup), "hqTime": _hm(b.hq_time), "lastDumped": _iso(b.last_dumped),
            "gross": _nums(b.gross), "grossF": _nums(b.gross_f), "grossR": _nums(b.gross_r),
            "tare": _nums(b.tare), "tareF": _nums(b.tare_f), "tareR": _nums(b.tare_r),
            "wasteClass": b.waste_class or "", "dumpFee": _nums(b.dump_fee), "extraTime": b.extra_time or "",
            "pickupBy": b.pickup_by or "", "dumpBy": b.dump_by or "", "sortJunk": b.sort_junk or "",
            "sortMetal": b.sort_metal or "", "sortTime": (str(b.sort_minutes) if b.sort_minutes is not None else ""),
            "noSort": bool(b.no_sort), "notes": b.notes or "",
            "photos": b.photos or [], "contactLog": b.contact_log or [],
        }
        if b.job_id:
            rec["jobId"] = str(b.job_id)
        if b.repair_note:
            rec["repairNote"] = b.repair_note
            rec["repairOpen"] = bool(b.repair_open)
            rec["repairAt"] = _iso(b.repair_at)
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
    # The owner sees every hub — grant the full flag set (owner = all-access, Wes 2026-07).
    # Feature visibility only; owner-only *mutations* stay guarded server-side (is_owner).
    return [
        {"name": e.name, "role": e.role,
         "access": sorted(ACCESS_FLAGS) if is_owner(e) else list(e.access or []),
         "active": e.active, "tracked": e.time_tracked, "salaried": e.pay_type == PayType.salaried}
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
    surs = db.scalars(select(AreaSurcharge).where(AreaSurcharge.brand == brand)).all()
    surcharges = {s.area_name: _f(s.bin_amount) for s in surs if s.bin_amount is not None}
    roofing_surcharges = {s.area_name: _f(s.roofing_bin_amount) for s in surs if s.roofing_bin_amount is not None}
    # custom customers persisted from the rate sheet (key rc_*), rebuilt to the sheet's shape
    customers = []
    for c in db.scalars(select(Contract).where(Contract.brand == brand, Contract.key.like("rc_%"))):
        ex = c.properties if isinstance(c.properties, dict) else {}
        customers.append({
            "name": c.name, "kind": ex.get("kind", ""), "rates": c.rates or [],
            "departments": list(c.divisions or []), "reqShots": list(c.shots or []),
            "poReq": c.po_req, "extra": c.extra, "terms": c.terms or "",
            "disposal": ex.get("disposal"), "bins": ex.get("bins"),
            "dumpRates": ex.get("dumpRates"), "jobs": ex.get("jobs"),
        })
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
        "surcharges": surcharges, "roofingSurcharges": roofing_surcharges,
        "customers": customers,
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


def _build_weigh_state(db: DbSession, brand: Brand, kind: str) -> dict | None:
    """`{k: rec}` of the field weights for `kind`, or None until any exist."""
    rows = db.scalars(select(BinWeigh).where(BinWeigh.brand == brand, BinWeigh.kind == kind)).all()
    if not rows:
        return None
    return {r.k: r.rec for r in rows}


def build_tares_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_tares_v1` — field tare weights keyed 'truck|code'."""
    return _build_weigh_state(db, brand, "tare")


def build_weighins_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_weighins_v1` — field gross weigh-ins keyed 'code'."""
    return _build_weigh_state(db, brand, "weighin")


def build_maint_v2(db: DbSession, brand: Brand) -> dict | None:
    """`ij_maint_v2` — the whole maintenance document. None (keep the prototype's own
    seed) until the hub has been edited + synced for this brand."""
    doc = db.scalar(select(MaintenanceDoc).where(MaintenanceDoc.brand == brand))
    return doc.doc if (doc and doc.doc) else None


def build_fixes_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_fixes_v1` — OPEN crew defect flags only (resolved ones are simply omitted).
    None until real flags exist."""
    rows = db.scalars(select(DefectFlag).where(
        DefectFlag.brand == brand, DefectFlag.is_open.is_(True))).all()
    if not rows:
        return None
    return [{"id": r.source_id, "truck": r.truck, "item": r.item, "note": r.note,
             "who": r.who, "date": r.flag_date, "open": True, "source": r.source} for r in rows]


def build_reminders_v1(db: DbSession, brand: Brand) -> list | None:
    """`ij_reminders_v1` — OPEN app reminders (general + booking drafts). CC-charge
    reminders live on the owner's separate queue (`GET /reminders`), not this screen.
    None until real reminders exist."""
    rows = db.scalars(select(Reminder).where(
        Reminder.brand == brand, Reminder.done.is_(False), Reminder.kind != ReminderKind.cc_charge)).all()
    if not rows:
        return None
    return [{"id": r.source_id, "text": r.text, "by": r.by, "ts": r.ts,
             "due": r.due.isoformat() if r.due else "", "booking": r.booking,
             "name": r.name, "addr": r.addr, "draft": r.draft} for r in rows]


def build_contracts_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_contracts_v1` — user-added contracts (an object keyed by slug). Excludes the
    rate-sheet custom customers (key `rc_*`, which live in `ij_rates_v1.customers`). None
    until real ones exist (the prototype keeps its built-in constants)."""
    rows = [c for c in db.scalars(select(Contract).where(Contract.brand == brand))
            if not (c.key or "").startswith("rc_")]
    if not rows:
        return None
    return {c.key: {
        "name": c.name, "short": c.short or "", "pricing": c.pricing.value, "rateKey": c.rate_key,
        "divisions": list(c.divisions or []), "routeDivs": list(c.route_divs or []),
        "divAddable": c.div_addable, "extra": c.extra, "bin": c.bin, "poReq": c.po_req,
        "siteLog": c.site_log, "shots": list(c.shots or []), "terms": c.terms or "",
        "rates": c.rates, "flat": _f(c.flat), "flatUnit": c.flat_unit,
        "properties": c.properties, "note": c.note or "",
    } for c in rows}


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


def build_dayboard_status_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_dayboard_status_v1` = {event_id: status}. None until any exist."""
    rows = db.scalars(select(DayboardOverlay).where(
        DayboardOverlay.brand == brand, DayboardOverlay.status.isnot(None))).all()
    return {r.event_id: r.status for r in rows} or None


def build_dayboard_notes_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_dayboard_notes_v1` = {event_id: note}. None until any exist."""
    rows = db.scalars(select(DayboardOverlay).where(
        DayboardOverlay.brand == brand, DayboardOverlay.note.isnot(None))).all()
    return {r.event_id: r.note for r in rows} or None


def build_dayboard_sitelog_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_dayboard_sitelog_v1` = {event_id: {start,finish,loc}}. None until any exist."""
    rows = db.scalars(select(DayboardOverlay).where(
        DayboardOverlay.brand == brand, DayboardOverlay.sitelog.isnot(None))).all()
    return {r.event_id: r.sitelog for r in rows} or None


def build_attendance_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_attendance_v1` = {date: {name: {status, note, lateTime}}}. None until any exist."""
    rows = db.scalars(select(Attendance).where(Attendance.brand == brand)).all()
    if not rows:
        return None
    out: dict[str, dict] = {}
    for r in rows:
        rec: dict = {}
        if r.status is not None:
            rec["status"] = r.status
        if r.note is not None:
            rec["note"] = r.note
        if r.late_time is not None:
            rec["lateTime"] = r.late_time
        out.setdefault(r.work_date.isoformat(), {})[r.employee_name] = rec
    return out


def build_breaks_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_breaks_v1` = {name: {iso: rec}}. None until any exist."""
    rows = db.scalars(select(BreakLog).where(BreakLog.brand == brand)).all()
    if not rows:
        return None
    out: dict[str, dict] = {}
    for r in rows:
        out.setdefault(r.employee_name, {})[r.work_date.isoformat()] = r.doc
    return out


def build_daynotes_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_daynotes_v1` = {date: {bin, yard, handson}}. None until any exist."""
    rows = db.scalars(select(DayNote).where(DayNote.brand == brand)).all()
    if not rows:
        return None
    out: dict[str, dict] = {}
    for r in rows:
        rec = {k: v for k, v in (("bin", r.bin), ("yard", r.yard), ("handson", r.handson)) if v is not None}
        if rec:
            out[r.note_date.isoformat()] = rec
    return out or None


def build_binsout_cfg_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_binsout_cfg_v1` = {days: n}. None until set (prototype defaults to 14)."""
    row = db.scalar(select(BrandSetting).where(
        BrandSetting.brand == brand, BrandSetting.key == "ij_binsout_cfg_v1"))
    return row.value if (row and isinstance(row.value, dict)) else None


def build_checklists_v1(db: DbSession, brand: Brand) -> dict | None:
    """`ij_checklists_v1` — the owner's crew checklist templates. None until the owner has
    saved them (the crew tools keep their own built-in defaults meanwhile)."""
    row = db.scalar(select(BrandSetting).where(
        BrandSetting.brand == brand, BrandSetting.key == "ij_checklists_v1"))
    return row.value if (row and isinstance(row.value, dict)) else None


def build_reviews_v1(db: DbSession, brand: Brand) -> list:
    """`ij_reviews_v1` — the follow-up-reviews list (verbatim records). Returns [] (NOT None)
    even when empty, so the injected empty array suppresses the prototype's demo-seed write
    (`revList()` seeds + persists rv1/rv2/rv3 to localStorage on render otherwise)."""
    rows = db.scalars(select(FollowupReview).where(FollowupReview.brand == brand)).all()
    return [r.doc for r in rows]


def build_usage_v1(db: DbSession, brand: Brand) -> list:
    """`ij_usage_v1` — the consumables used/restock ledger. Returns [] (NOT None) even when
    empty, so the injected empty array suppresses the prototype's `seedUsage()` demo."""
    rows = db.scalars(select(UsageEvent).where(UsageEvent.brand == brand)).all()
    return [{"id": r.item_id, "name": r.item_name, "qty": r.qty, "type": r.type, "at": r.at_iso}
            for r in rows]


_BUILDERS = {
    "ij_fleet_v1": build_fleet_v1,
    "ij_colourmap_v1": build_colourmap_v1,
    "ij_bins_v1": build_bins_v1,
    "ij_bins_full_v1": build_bins_full_v1,
    "ij_employees_v1": build_employees_v1,
    "ij_rates_v1": build_rates_v1,
    "ij_incidents_v1": build_incidents_v1,
    "ij_clock_log": build_clock_log_v1,
    "ij_jobs_v1": build_field_jobs_v1,
    "ij_weighlog_v1": build_weighlog_v1,
    "ij_tares_v1": build_tares_v1,
    "ij_weighins_v1": build_weighins_v1,
    "ij_customers_v1": build_customers_v1,
    "ij_company_customers_v1": build_company_customers_v1,
    "ij_pm_db_v2": build_pm_db_v2,
    "ij_dayboard_status_v1": build_dayboard_status_v1,
    "ij_dayboard_notes_v1": build_dayboard_notes_v1,
    "ij_dayboard_sitelog_v1": build_dayboard_sitelog_v1,
    "ij_attendance_v1": build_attendance_v1,
    "ij_breaks_v1": build_breaks_v1,
    "ij_daynotes_v1": build_daynotes_v1,
    "ij_binsout_cfg_v1": build_binsout_cfg_v1,
    "ij_checklists_v1": build_checklists_v1,
    "ij_reviews_v1": build_reviews_v1,
    "ij_usage_v1": build_usage_v1,
    "ij_maint_v2": build_maint_v2,
    "ij_fixes_v1": build_fixes_v1,
    "ij_reminders_v1": build_reminders_v1,
    "ij_contracts_v1": build_contracts_v1,
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
