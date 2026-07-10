"""localStorage -> Postgres sync handlers (reverse of app/web/refs.py builders).

Each handler takes the full localStorage value for a key and **upserts** it into the
DB — never a blind replace, never delete-by-absence (too dangerous for a generic
whole-array sync). Removal is explicit (`active: false` / a status), not by omission.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session as DbSession

from app.auth.guards import is_owner
from app.auth.security import hash_pin
from app.customers.qb_import import company_key, residential_key
from app.models.attendance import Attendance, BreakLog
from app.models.bin_field import BinDriverDay, BinWeigh, ToolDailyLog
from app.models.bins import Bin
from app.models.clock import ClockPunch
from app.models.colour_map import ColourMap
from app.models.dayboard import DayboardOverlay
from app.models.contract import Contract
from app.models.customer import CompanyCustomer, PmBuilding, PmCompany, PmGroup, ResidentialCustomer
from app.models.employee import Employee
from app.models.enums import (
    BinStatus, Brand, ColourKind, ContractPricing, CustomerSource, DisposalRole,
    OWNER_ONLY_GRANTABLE, PayType, ReminderKind,
)
from app.models.field_job import FieldJob
from app.models.incident import Incident
from app.models.maintenance import DefectFlag, MaintenanceDoc
from app.models.ops import FollowupReview, PoChase, PrecheckLog, UsageEvent
from app.models.rates import AreaSurcharge, DisposalFacility, DisposalMaterial, DisposalRateHistory, RateCard
from app.models.reminder import Reminder
from app.models.settings import BrandSetting, DayNote
from app.models.truck import Truck
from app.models.weigh import WeighLog
from app.models.yard_processing import YardProcessing


def _pdate(s) -> date | None:
    try:
        return date.fromisoformat(str(s)[:10]) if s else None
    except ValueError:
        return None


def _pdt(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")) if s else None
    except ValueError:
        return None


def _num(x) -> float | None:
    try:
        return float(x) if x not in (None, "", False) else None
    except (ValueError, TypeError):
        return None


def _int(x) -> int | None:
    try:
        return int(x) if x not in (None, "", False) else None
    except (ValueError, TypeError):
        return None


def _ptime(s) -> time | None:
    """"HH:MM" / "HH:MM:SS" -> time, or None for blank/garbage."""
    try:
        parts = str(s).split(":")
        if not parts[0]:
            return None
        return time(hour=int(parts[0]), minute=int(parts[1]) if len(parts) > 1 else 0)
    except (ValueError, TypeError, IndexError):
        return None


def _ms_dt(ms) -> datetime | None:
    """Prototype Date.now() ms epoch -> aware datetime."""
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc) if ms else None
    except (ValueError, TypeError, OSError):
        return None

# registry `state` -> our BinStatus (reverse of refs._BIN_STATE; lossy but canonical)
_STATE_REV = {
    "idle": BinStatus.idle, "out": BinStatus.dropped, "returned": BinStatus.returned,
    "to_sort": BinStatus.to_sort, "clearing": BinStatus.clearing,
    "ready_dump": BinStatus.ready_dump, "retired": BinStatus.retired,
}
# bin-TRACKER `status` -> our BinStatus (reverse of refs._BIN_TRACKER_STATUS). "stationed"
# is intentionally absent — it rides as the `stationed` boolean, not a status.
_TRACKER_STATUS_REV = {
    "in_yard": BinStatus.idle, "dropped": BinStatus.dropped,
    "returning": BinStatus.returning, "maintenance": BinStatus.maintenance,
}
# rich bin fields written by the tracker -> (Bin attr, coercion). Present-key-only:
# a key absent from the record is never touched, so a lean registry/yard write (which
# omits these) leaves them alone, while the tracker's full write can set/clear them.
_BIN_BOOL = {"lidded": "lidded", "leased": "leased", "stationed": "stationed",
             "customLid": "custom_lid", "roofing": "roofing", "noSort": "no_sort",
             "repairOpen": "repair_open"}
_BIN_STR = {"town": "town", "notes": "notes", "wasteClass": "waste_class",
            "extraTime": "extra_time", "pickupBy": "pickup_by", "dumpBy": "dump_by",
            "sortJunk": "sort_junk", "sortMetal": "sort_metal", "repairNote": "repair_note"}
_BIN_DATE = {"dropDate": "drop_date", "pickDate": "pick_date",
             "scheduledPickup": "scheduled_pickup", "lastDumped": "last_dumped", "repairAt": "repair_at"}
_BIN_TIME = {"dropTime": "drop_time", "hqTime": "hq_time"}
_BIN_DEC = {"base": "base", "surcharge": "surcharge", "gross": "gross", "tare": "tare",
            "grossF": "gross_f", "grossR": "gross_r", "tareF": "tare_f", "tareR": "tare_r",
            "dumpFee": "dump_fee"}


def apply_bins(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert bin state/location/rich fields by `code`. The fleet is fixed — unknown codes
    are ignored. Accepts BOTH shapes on the shared `ij_bins_v1` key: the lean registry/yard
    write (`state` + nested `job`) and the driver bin-tracker's rich write (`status` + drop/
    pick/weigh/repair fields). Every field is **present-key-only** — a lean write never
    blanks the rich fields it omits."""
    if not isinstance(data, list):
        return {"updated": 0, "skipped": "not a list"}
    updated = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("code"):
            continue
        b = db.scalar(select(Bin).where(Bin.brand == brand, Bin.code == rec["code"]))
        if b is None:
            continue

        # status: the tracker's `status` wins over the registry `state` (a record carries one).
        st = None
        if "status" in rec:
            st = _TRACKER_STATUS_REV.get(rec.get("status"))   # None for "stationed"/unknown -> skip
        elif "state" in rec:
            st = _STATE_REV.get(rec.get("state"))
        if st is not None:
            b.status = st

        # customer/address: rich top-level fields, else the lean nested `job`.
        if "customer" in rec:
            b.customer = rec.get("customer") or None
        if "address" in rec:
            b.address = rec.get("address") or None
        job = rec.get("job") if isinstance(rec.get("job"), dict) else None
        if job is not None:
            b.customer = job.get("customer") or None
            b.address = job.get("address") or None
        if "type" in rec:
            b.type = rec.get("type") or None

        for key, attr in _BIN_BOOL.items():
            if key in rec:
                setattr(b, attr, bool(rec[key]))
        for key, attr in _BIN_STR.items():
            if key in rec:
                setattr(b, attr, (str(rec[key]).strip() or None) if rec[key] not in (None, "") else None)
        for key, attr in _BIN_DATE.items():
            if key in rec:
                setattr(b, attr, _pdate(rec[key]))
        for key, attr in _BIN_TIME.items():
            if key in rec:
                setattr(b, attr, _ptime(rec[key]))
        for key, attr in _BIN_DEC.items():
            if key in rec:
                setattr(b, attr, _dec(rec[key]))
        if "sortTime" in rec:
            b.sort_minutes = _int(rec["sortTime"])
        if "photos" in rec and isinstance(rec["photos"], list):
            b.photos = rec["photos"]
        if "contactLog" in rec and isinstance(rec["contactLog"], list):
            b.contact_log = rec["contactLog"]
        if "cleared" in rec and isinstance(rec["cleared"], dict):
            b.cleared = rec["cleared"]
        if "jobId" in rec:
            b.job_id = _as_uuid(rec.get("jobId"))
        updated += 1
    db.commit()
    return {"updated": updated}


def apply_employees(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Add/update crew by `name` (roster editor). Owner/manager only; the owner row is
    untouchable by non-owner; owner-only flags can't be granted by non-owner; PINs are
    never changed here (set via a dedicated owner flow). Removal = explicit active:false
    (no delete-by-absence)."""
    if not (is_owner(actor) or "manager" in (actor.access or [])):
        return {"error": "forbidden — manager/owner only"}
    if not isinstance(data, list):
        return {"updated": 0}
    actor_owner = is_owner(actor)
    added = updated = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        name = (rec.get("name") or "").strip()
        if not name:
            continue
        # Include brand-null (owner) rows so the owner is FOUND + guarded, not duplicated.
        e = db.scalar(select(Employee).where(
            Employee.name == name, or_(Employee.brand == brand, Employee.brand.is_(None))
        ))
        if e is not None and is_owner(e) and not actor_owner:
            continue  # never touch the owner row as a non-owner

        access = rec.get("access") if isinstance(rec.get("access"), list) else None
        if access is not None and not actor_owner:  # keep existing owner-only flags; don't let a manager grant them
            keep = [f for f in (e.access if e else []) if f in OWNER_ONLY_GRANTABLE]
            access = [f for f in access if f not in OWNER_ONLY_GRANTABLE] + keep

        if e is None:
            db.add(Employee(
                brand=brand, name=name, role=rec.get("role") or "Crew",
                pin_hash=hash_pin("0000"), access=access or ["hours"],
                active=bool(rec.get("active", True)), time_tracked=bool(rec.get("tracked", True)),
                pay_type=PayType.salaried if rec.get("salaried") else PayType.hourly,
            ))
            added += 1
        else:
            if rec.get("role") is not None:
                e.role = rec["role"]
            if access is not None:
                e.access = access
            if "active" in rec:
                e.active = bool(rec["active"])
            if "tracked" in rec:
                e.time_tracked = bool(rec["tracked"])
            if "salaried" in rec:
                e.pay_type = PayType.salaried if rec["salaried"] else PayType.hourly
            updated += 1
    db.commit()
    return {"added": added, "updated": updated, "note": "PINs unchanged; removal = active:false"}


def apply_fleet(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_fleet_v1` = {num: {mgr}} — the dispatch-truck roster (manager/owner-editable, §6).
    Upsert Truck by (brand, num) with its lead; a truck removed from a present, non-empty
    object is **soft-removed** (active=False) so its history + past assignments survive (§7)."""
    if not (is_owner(actor) or "manager" in (actor.access or [])):
        return {"error": "forbidden — manager/owner only"}
    if not isinstance(data, dict) or not data:
        return {"upserted": 0}
    seen, n = set(), 0
    for num, rec in data.items():
        num = str(num).strip()
        if not num:
            continue
        seen.add(num)
        lead = (rec.get("mgr") if isinstance(rec, dict) else None) or None
        t = db.scalar(select(Truck).where(Truck.brand == brand, Truck.num == num))
        if t is None:
            t = Truck(brand=brand, num=num, lead=lead, active=True)
            db.add(t)
        else:
            t.lead, t.active = lead, True
        n += 1
    removed = 0
    for t in db.scalars(select(Truck).where(Truck.brand == brand, Truck.active.is_(True))).all():
        if t.num not in seen:
            t.active, removed = False, removed + 1
    db.commit()
    return {"upserted": n, "soft_removed": removed}


def apply_colourmap(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_colourmap_v1` — the colour→truck map (manager/owner-editable, §6). Sets
    `assigned_truck` on **assignable** colours ONLY; STATUS and UNASSIGNED (sage) colours are
    NEVER touched — Make.com keys ad-conversion signals off the status colours (§5/§15), so a
    map edit must never alter them. Unknown keys (owner-added custom colours) are skipped for
    now — creating custom colour rows needs their hex/colorId (a focused follow-up)."""
    if not (is_owner(actor) or "manager" in (actor.access or [])):
        return {"error": "forbidden — manager/owner only"}
    if not isinstance(data, dict):
        return {"updated": 0}
    assign = data.get("assign") if isinstance(data.get("assign"), dict) else {}
    current = data.get("current") if isinstance(data.get("current"), dict) else {}
    merged: dict[str, str] = {}
    for k, v in current.items():
        merged[str(k)] = (v.get("truck") if isinstance(v, dict) else v) or ""
    for k, v in assign.items():   # `assign` wins where both present
        merged[str(k)] = v or ""
    updated = skipped = 0
    for key, truck in merged.items():
        key = key.strip()
        if not key:
            continue
        row = db.scalar(select(ColourMap).where(ColourMap.brand == brand, ColourMap.key == key))
        if row is None or row.kind != ColourKind.assignable:
            skipped += 1   # unknown/custom, or a protected status/sage colour
            continue
        row.assigned_truck = (str(truck).strip() or None)
        updated += 1
    db.commit()
    return {"updated": updated, "skipped_protected_or_custom": skipped}


def apply_incidents(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Append-only: insert new incidents (dedup by the prototype's `id`). Never edit/delete."""
    if not isinstance(data, list):
        return {"added": 0}
    added = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        sid = rec.get("id")
        if sid and db.scalar(select(Incident).where(Incident.brand == brand, Incident.source_id == sid)):
            continue  # already stored
        db.add(Incident(
            brand=brand, source_id=sid, at=_pdt(rec.get("at")), type=rec.get("type"), sev=rec.get("sev"),
            told=rec.get("told"), reported_by=rec.get("by"), who=rec.get("who"),
            incident_date=_pdate(rec.get("date")), incident_time=rec.get("time"),
            location=rec.get("where"), truck=rec.get("truck"), what=rec.get("what"),
            action=rec.get("action"), photos=rec.get("photos"),
        ))
        added += 1
    db.commit()
    return {"added": added}


def apply_clock(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert one punch per (name, work_date); fill in/out/done times as they arrive, then
    mirror the punch to the off-board punch-time calendar (best-effort)."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    touched: list[ClockPunch] = []
    for rec in data:
        if not isinstance(rec, dict):
            continue
        name = (rec.get("name") or "").strip()
        wd = _pdate(rec.get("date") or rec.get("at"))
        if not name or wd is None:
            continue
        p = db.scalar(select(ClockPunch).where(
            ClockPunch.brand == brand, ClockPunch.employee_name == name, ClockPunch.work_date == wd))
        if p is None:
            p = ClockPunch(brand=brand, employee_name=name, work_date=wd)
            db.add(p)
        if rec.get("inTime"):
            p.in_time = rec["inTime"]
        if rec.get("outTime") is not None:
            p.out_time = rec["outTime"] or None
        if rec.get("doneAt") is not None:
            p.done_time = rec["doneAt"] or None
        if rec.get("truck"):
            p.truck = rec["truck"]
        touched.append(p)
        n += 1
    db.commit()
    mirrored = _mirror_punches(db, touched)
    return {"upserted": n, "calendar_mirrored": mirrored}


def _mirror_punches(db: DbSession, punches: list[ClockPunch]) -> int:
    """Create/update one punch-calendar event per touched punch. Best-effort: skips cleanly
    if the calendar isn't shared/configured, and never lets a calendar error fail the sync."""
    if not punches:
        return 0
    try:
        from app.integrations import gcal
        if not gcal.punch_calendar_accessible():
            return 0
    except Exception:
        return 0
    mirrored = 0
    for p in punches:
        try:
            eid = gcal.upsert_punch_event(
                event_id=p.gcal_event_id, name=p.employee_name, on_date=p.work_date,
                in_str=p.in_time, out_str=p.out_time, truck=p.truck)
            if eid and eid != p.gcal_event_id:
                p.gcal_event_id = eid
            mirrored += 1
        except Exception:
            pass
    db.commit()
    return mirrored


def apply_field_jobs(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert crew field jobs by the prototype's `id`; visits replace wholesale."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        fj = db.scalar(select(FieldJob).where(FieldJob.brand == brand, FieldJob.source_id == rec["id"]))
        if fj is None:
            fj = FieldJob(brand=brand, source_id=rec["id"])
            db.add(fj)
        if rec.get("type"):
            fj.type = rec["type"]
        if rec.get("status"):
            fj.status = rec["status"]
        if rec.get("customer") is not None:
            fj.customer = rec["customer"] or None
        if rec.get("address") is not None:
            fj.address = rec["address"] or None
        if isinstance(rec.get("visits"), list):
            fj.visits = rec["visits"]
        n += 1
    db.commit()
    return {"upserted": n}


def apply_weigh(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Append weigh events; dedup by (source_at, bin) so re-syncs don't duplicate.
    The yard/truck-hub write `bin`/`source`; the bin-tracker driver writes the same
    log with `code`/`kind` — accept either so the driver's events keep their bin code."""
    if not isinstance(data, list):
        return {"added": 0}
    added = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        at, binc = rec.get("at"), (rec.get("bin") or rec.get("code"))
        if at is not None and db.scalar(select(WeighLog).where(
                WeighLog.brand == brand, WeighLog.source_at == at, WeighLog.bin == binc)):
            continue
        db.add(WeighLog(
            brand=brand, source_at=at, weigh_date=_pdate(rec.get("date")), weigh_time=rec.get("time"),
            who=rec.get("who"), truck=rec.get("truck"), bin=binc, cls=rec.get("cls"),
            source=(rec.get("source") or rec.get("kind")), front_kg=rec.get("f"), rear_kg=rec.get("r"),
            total_kg=rec.get("total"),
        ))
        added += 1
    db.commit()
    return {"added": added}


def apply_binday(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_binday_v1` — the bin driver's whole day (verbatim). Upsert by (brand, driver,
    work_date). Write-only: a fresh no-driver day is skipped, and the day is never echoed
    back (a shared tablet must not restore another driver's day)."""
    if not isinstance(data, dict):
        return {"saved": False, "reason": "not a day object"}
    driver = (data.get("driver") or "").strip()
    wd = _pdate(data.get("date"))
    if not driver or wd is None:
        return {"saved": False, "reason": "no driver/date yet"}
    row = db.scalar(select(BinDriverDay).where(
        BinDriverDay.brand == brand, BinDriverDay.driver == driver, BinDriverDay.work_date == wd))
    if row is None:
        row = BinDriverDay(brand=brand, driver=driver, work_date=wd)
        db.add(row)
    row.truck = (data.get("truck") or None)
    row.doc = data
    db.commit()
    return {"saved": True, "driver": driver, "date": wd.isoformat()}


def _apply_weigh_state(db: DbSession, brand: Brand, kind: str, data) -> dict:
    """Upsert one field-weight dict (`{k: rec}`) into bin_weigh rows for `kind`. Per-key
    upsert — a key absent from the payload is left alone (never delete-by-absence, so a
    concurrent device's entry is safe)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for k, rec in data.items():
        if not isinstance(rec, dict):
            continue
        row = db.scalar(select(BinWeigh).where(
            BinWeigh.brand == brand, BinWeigh.kind == kind, BinWeigh.k == str(k)))
        if row is None:
            row = BinWeigh(brand=brand, kind=kind, k=str(k))
            db.add(row)
        row.rec = rec
        n += 1
    db.commit()
    return {"upserted": n}


def apply_tares(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_tares_v1` — field tare weights keyed 'truck|code'."""
    return _apply_weigh_state(db, brand, "tare", data)


def apply_weighins(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_weighins_v1` — field gross weigh-ins keyed 'code'."""
    return _apply_weigh_state(db, brand, "weighin", data)


def apply_tooldaily(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_tooldaily_v1` — the morning onboard-gear check log. Upsert by (brand, truck,
    log_date); the tools map replaces wholesale (it's one check per truck per day)."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        truck = str(rec.get("truck") or "").strip()
        ld = _pdate(rec.get("date"))
        tools = rec.get("tools") if isinstance(rec.get("tools"), dict) else None
        if not truck or ld is None or tools is None:
            continue
        row = db.scalar(select(ToolDailyLog).where(
            ToolDailyLog.brand == brand, ToolDailyLog.truck == truck, ToolDailyLog.log_date == ld))
        if row is None:
            row = ToolDailyLog(brand=brand, truck=truck, log_date=ld)
            db.add(row)
        row.who = rec.get("who")
        row.logged_when = rec.get("when")
        row.tools = tools
        n += 1
    db.commit()
    return {"upserted": n}


def apply_yard_processing(db: DbSession, brand: Brand, records, actor: Employee) -> dict:
    """Save the rich yard close-out records (dedicated endpoint, not a sync key).
    Upsert by (code, processed_date); cast the prototype's string numbers."""
    if not isinstance(records, list):
        return {"saved": 0}
    saved = 0
    for rec in records:
        if not isinstance(rec, dict) or not rec.get("code"):
            continue
        pdate = _pdate(rec.get("processedDate"))
        yp = db.scalar(select(YardProcessing).where(
            YardProcessing.brand == brand, YardProcessing.code == rec["code"],
            YardProcessing.processed_date == pdate))
        if yp is None:
            yp = YardProcessing(brand=brand, code=rec["code"], processed_date=pdate)
            db.add(yp)
        yp.ref, yp.type, yp.size, yp.roofing = rec.get("ref"), rec.get("type"), _int(rec.get("size")), bool(rec.get("roofing"))
        yp.customer, yp.address, yp.town = rec.get("customer"), rec.get("address"), rec.get("town")
        yp.pickup_by, yp.truck, yp.hq_time, yp.pick_date = rec.get("pickupBy"), rec.get("truck"), rec.get("hqTime"), rec.get("pickDate")
        yp.crew = rec.get("crew") if isinstance(rec.get("crew"), list) else None
        yp.crew_count = _int(rec.get("crewCount"))
        yp.gross_f, yp.gross_r = _num(rec.get("grossF")), _num(rec.get("grossR"))
        yp.tare_f, yp.tare_r = _num(rec.get("tareF")), _num(rec.get("tareR"))
        yp.gross, yp.tare = _num(rec.get("gross")), _num(rec.get("tare"))
        yp.waste_class, yp.dump_fee = rec.get("wasteClass"), _num(rec.get("dumpFee"))
        yp.pct = rec.get("pct") if isinstance(rec.get("pct"), dict) else None
        yp.extras = rec.get("extras") if isinstance(rec.get("extras"), dict) else None
        yp.custom_extras = rec.get("customExtras") if isinstance(rec.get("customExtras"), list) else None
        yp.process_notes, yp.sort_minutes = rec.get("processNotes"), _int(rec.get("sortMinutes"))
        yp.weighed, yp.processed = bool(rec.get("weighed")), bool(rec.get("processed"))
        yp.processed_clock = rec.get("processedClock")
        yp.photos = rec.get("photos") if isinstance(rec.get("photos"), list) else None
        saved += 1
    db.commit()
    return {"saved": saved}


def _overlay_upsert(db: DbSession, brand: Brand, event_id: str, col: str, value) -> None:
    """Atomically set ONE column of the shared (brand, event_id) overlay row. Uses Postgres
    ON CONFLICT so the three overlay handlers (status/note/sitelog) can create the same row
    concurrently without one insert losing to the other's unique-constraint collision."""
    stmt = pg_insert(DayboardOverlay).values(brand=brand, event_id=event_id, **{col: value})
    stmt = stmt.on_conflict_do_update(
        index_elements=["brand", "event_id"], set_={col: getattr(stmt.excluded, col)})
    db.execute(stmt)


def apply_dayboard_status(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_dayboard_status_v1` = {event_id: status} — crew status override per stop.
    Grow-only (the prototype never clears a status)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for eid, st in data.items():
        if not eid:
            continue
        _overlay_upsert(db, brand, str(eid), "status", st or None)
        n += 1
    db.commit()
    return {"upserted": n}


def apply_dayboard_notes(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_dayboard_notes_v1` = {event_id: note}. The prototype deletes the key when a note
    is emptied, so we reconcile: a note in the DB but absent from the present dict is cleared
    (the injected full set makes the device's dict authoritative)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    seen, n = set(), 0
    for eid, note in data.items():
        if not eid:
            continue
        eid = str(eid)
        seen.add(eid)
        _overlay_upsert(db, brand, eid, "note", (str(note).strip() or None) if note else None)
        n += 1
    cleared = 0
    for row in db.scalars(select(DayboardOverlay).where(
            DayboardOverlay.brand == brand, DayboardOverlay.note.isnot(None))).all():
        if row.event_id not in seen:
            row.note, cleared = None, cleared + 1
    db.commit()
    return {"upserted": n, "cleared": cleared}


def apply_dayboard_sitelog(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_dayboard_sitelog_v1` = {event_id: {start,finish,loc}}. Reconcile-clear absent
    (deleted-on-empty, same as notes)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    seen, n = set(), 0
    for eid, log in data.items():
        if not eid or not isinstance(log, dict):
            continue
        eid = str(eid)
        seen.add(eid)
        _overlay_upsert(db, brand, eid, "sitelog", log or None)
        n += 1
    cleared = 0
    for row in db.scalars(select(DayboardOverlay).where(
            DayboardOverlay.brand == brand, DayboardOverlay.sitelog.isnot(None))).all():
        if row.event_id not in seen:
            row.sitelog, cleared = None, cleared + 1
    db.commit()
    return {"upserted": n, "cleared": cleared}


def apply_attendance(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_attendance_v1` = {date: {name: {status, note, lateTime}}}. Upsert per (date, name);
    permanent HR record (no delete-by-absence)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for d, people in data.items():
        wd = _pdate(d)
        if wd is None or not isinstance(people, dict):
            continue
        for name, rec in people.items():
            name = (name or "").strip()
            if not name or not isinstance(rec, dict):
                continue
            row = db.scalar(select(Attendance).where(
                Attendance.brand == brand, Attendance.work_date == wd, Attendance.employee_name == name))
            if row is None:
                row = Attendance(brand=brand, work_date=wd, employee_name=name)
                db.add(row)
            row.status = rec.get("status") or None
            row.note = rec.get("note") or None
            row.late_time = rec.get("lateTime") or None
            n += 1
    db.commit()
    return {"upserted": n}


def apply_breaks(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_breaks_v1` = {name: {iso: rec}}. Upsert per (name, date), record kept verbatim,
    `total` minutes lifted out for the owner's hours math."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for name, days in data.items():
        name = (name or "").strip()
        if not name or not isinstance(days, dict):
            continue
        for iso, rec in days.items():
            wd = _pdate(iso)
            if wd is None or not isinstance(rec, dict):
                continue
            row = db.scalar(select(BreakLog).where(
                BreakLog.brand == brand, BreakLog.employee_name == name, BreakLog.work_date == wd))
            if row is None:
                row = BreakLog(brand=brand, employee_name=name, work_date=wd, doc=rec)
                db.add(row)
            else:
                row.doc = rec
            row.total_minutes = _int(rec.get("total"))
            n += 1
    db.commit()
    return {"upserted": n}


def apply_daynotes(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_daynotes_v1` = {date: {bin, yard, handson}}. Upsert per date; per-shift present-key
    only (a hub that sets one shift never blanks the others)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for d, rec in data.items():
        wd = _pdate(d)
        if wd is None or not isinstance(rec, dict):
            continue
        row = db.scalar(select(DayNote).where(DayNote.brand == brand, DayNote.note_date == wd))
        if row is None:
            row = DayNote(brand=brand, note_date=wd)
            db.add(row)
        for shift in ("bin", "yard", "handson"):
            if shift in rec:
                setattr(row, shift, (str(rec[shift]).strip() or None) if rec[shift] else None)
        n += 1
    db.commit()
    return {"upserted": n}


def _apply_setting(db: DbSession, brand: Brand, key: str, data) -> dict:
    """Upsert a small brand setting (`brand_setting`) verbatim."""
    if data is None:
        return {"saved": False}
    row = db.scalar(select(BrandSetting).where(BrandSetting.brand == brand, BrandSetting.key == key))
    if row is None:
        db.add(BrandSetting(brand=brand, key=key, value=data))
    else:
        row.value = data
    db.commit()
    return {"saved": True, "key": key}


def apply_binsout_cfg(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_binsout_cfg_v1` = {days: n} — the long-out-rental threshold. -> brand_setting."""
    return _apply_setting(db, brand, "ij_binsout_cfg_v1", data)


def apply_checklists(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_checklists_v1` — the owner/manager-configurable crew checklist TEMPLATES
    (walk-around + clock-out, per crew type). `{walk:{hand,bin}, clockout:{hand,bin,yard}}`,
    each a list of `{id,t,d}`. Owner/manager only (crew tools read but must not overwrite the
    template). Stored verbatim so the truck-hub / day-board / yard read the owner's edits."""
    if not (is_owner(actor) or "manager" in (actor.access or [])):
        return {"error": "forbidden — manager/owner only"}
    if not isinstance(data, dict) or not data:
        return {"saved": False}
    return _apply_setting(db, brand, "ij_checklists_v1", data)


def apply_reviews(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_reviews_v1` — the §11 follow-up-reviews list. Upsert by `id`; upsert-only (a
    review record is a permanent 'who to ask' log, never delete-by-absence)."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        sid = str(rec["id"])
        row = db.scalar(select(FollowupReview).where(
            FollowupReview.brand == brand, FollowupReview.source_id == sid))
        if row is None:
            row = FollowupReview(brand=brand, source_id=sid)
            db.add(row)
        row.name = rec.get("name")
        row.review_sent = bool(rec.get("reviewSent"))
        row.skipped = bool(rec.get("skipped"))
        row.doc = rec
        n += 1
    db.commit()
    return {"upserted": n}


def apply_usage(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_usage_v1` — the consumables used/restock ledger. Append-only; dedup by
    (item_id, at, type) against the DB **and within this payload** (the ledger can carry
    two identical events, which would otherwise collide on the unique key)."""
    if not isinstance(data, list):
        return {"added": 0}
    added = 0
    seen: set[tuple] = set()
    for rec in data:
        if not isinstance(rec, dict):
            continue
        at = rec.get("at")
        if not at:
            continue
        item_id, typ = rec.get("id"), rec.get("type")
        key = (item_id, str(at), typ)
        if key in seen:
            continue
        seen.add(key)
        if db.scalar(select(UsageEvent).where(
                UsageEvent.brand == brand, UsageEvent.item_id == item_id,
                UsageEvent.at_iso == str(at), UsageEvent.type == typ)):
            continue
        db.add(UsageEvent(brand=brand, item_id=item_id, item_name=rec.get("name"),
                          qty=_int(rec.get("qty")), type=typ, at_iso=str(at)))
        added += 1
    db.commit()
    return {"added": added}


def apply_precheck(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_precheck_v1` — the hands-on crew's morning truck walk-around. Upsert by
    (brand, truck, date); the items list replaces wholesale (one check per truck per day)."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        truck = str(rec.get("truck") or "").strip()
        cd = _pdate(rec.get("date"))
        items = rec.get("items") if isinstance(rec.get("items"), list) else None
        if not truck or cd is None or items is None:
            continue
        row = db.scalar(select(PrecheckLog).where(
            PrecheckLog.brand == brand, PrecheckLog.truck == truck, PrecheckLog.check_date == cd))
        if row is None:
            row = PrecheckLog(brand=brand, truck=truck, check_date=cd, items=items)
            db.add(row)
        else:
            row.items = items
        row.who = rec.get("who")
        row.logged_when = rec.get("when")
        row.flagged = _int(rec.get("flagged"))
        n += 1
    db.commit()
    return {"upserted": n}


def apply_po_needed(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """`ij_po_needed_v1` — property-management PO#s to chase. Upsert by `id`; upsert-only.
    Owner/manager only (created by the booking, chased in the hubs). The demo sample is
    suppressed client-side via the injected `ij_po_seeded_v1` flag, but we also skip any
    record still tagged '— SAMPLE' as a belt-and-braces guard against seeding the demo."""
    if not (is_owner(actor) or "manager" in (actor.access or [])):
        return {"error": "forbidden — manager/owner only"}
    if not isinstance(data, list):
        return {"upserted": 0}
    n = skipped = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        if "SAMPLE" in (rec.get("company") or "").upper():
            skipped += 1
            continue
        sid = str(rec["id"])
        row = db.scalar(select(PoChase).where(PoChase.brand == brand, PoChase.source_id == sid))
        if row is None:
            row = PoChase(brand=brand, source_id=sid)
            db.add(row)
        row.status = rec.get("status")
        row.total = _dec(rec.get("total"))
        row.doc = rec
        n += 1
    db.commit()
    return {"upserted": n, "skipped_samples": skipped}


def apply_maint(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert the whole maintenance document (`ij_maint_v2` = {order, m, _v}) — one row
    per brand. Stored verbatim as JSONB so the prototype's structure + client-side
    migrations are preserved."""
    if not isinstance(data, dict) or "m" not in data:
        return {"saved": False, "reason": "not a maintenance doc"}
    doc = db.scalar(select(MaintenanceDoc).where(MaintenanceDoc.brand == brand))
    if doc is None:
        db.add(MaintenanceDoc(brand=brand, doc=data))
    else:
        doc.doc = data
    db.commit()
    return {"saved": True, "assets": len(data.get("m") or {})}


def apply_fixes(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert crew walk-around defect flags (`ij_fixes_v1`) by source id. Never
    delete-by-absence — closing is explicit via `ij_fixes_resolved_v1`."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        sid = rec.get("id")
        f = db.scalar(select(DefectFlag).where(
            DefectFlag.brand == brand, DefectFlag.source_id == sid)) if sid else None
        if f is None:
            f = DefectFlag(brand=brand, source_id=sid)
            db.add(f)
        f.truck, f.item, f.note, f.who = rec.get("truck"), rec.get("item"), rec.get("note"), rec.get("who")
        f.flag_date, f.source = rec.get("date"), rec.get("source")
        if rec.get("open") is not None:
            f.is_open = bool(rec.get("open"))
        n += 1
    db.commit()
    return {"upserted": n}


def apply_fixes_resolved(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Close defect flags the maintenance/yard hub marked fixed (`ij_fixes_resolved_v1`
    = {source_id: ms-ts})."""
    if not isinstance(data, dict):
        return {"resolved": 0}
    n = 0
    for sid, ts in data.items():
        f = db.scalar(select(DefectFlag).where(DefectFlag.brand == brand, DefectFlag.source_id == sid))
        if f is None:
            f = DefectFlag(brand=brand, source_id=sid, is_open=False)
            db.add(f)
        f.is_open = False
        if f.resolved_at is None:
            f.resolved_at = _ms_dt(ts)
        n += 1
    db.commit()
    return {"resolved": n}


def apply_reminders(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert the app reminder list (`ij_reminders_v1`) by id. The prototype removes a
    reminder from the list when it's done, so we reconcile: any app-managed reminder
    (general/booking_draft) no longer in the list is marked done. cc_charge reminders are
    owner-managed via their own endpoint and are never touched by an absent list entry."""
    if not isinstance(data, list):
        return {"upserted": 0}
    seen: set[str] = set()
    n = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("id"):
            continue
        sid = rec["id"]
        seen.add(sid)
        r = db.scalar(select(Reminder).where(Reminder.brand == brand, Reminder.source_id == sid))
        if r is None:
            r = Reminder(brand=brand, source_id=sid,
                         kind=ReminderKind.booking_draft if rec.get("booking") else ReminderKind.general)
            db.add(r)
        elif r.kind == ReminderKind.cc_charge:
            continue  # never let the app list overwrite an owner CC-charge reminder
        r.text, r.by, r.ts = rec.get("text"), rec.get("by"), _int(rec.get("ts"))
        r.due = _pdate(rec.get("due"))
        r.booking = bool(rec.get("booking"))
        r.name, r.addr = rec.get("name"), rec.get("addr")
        r.draft = rec.get("draft") if isinstance(rec.get("draft"), dict) else None
        r.done = bool(rec.get("done", False))
        n += 1
    closed = 0
    for r in db.scalars(select(Reminder).where(
            Reminder.brand == brand, Reminder.done.is_(False), Reminder.kind != ReminderKind.cc_charge)).all():
        if r.source_id not in seen:
            r.done, closed = True, closed + 1
    db.commit()
    return {"upserted": n, "closed": closed}


def _dec(x) -> Decimal | None:
    """Rate-sheet money cell -> Decimal, or None for a blank ('' / None)."""
    if x in (None, ""):
        return None
    try:
        return Decimal(str(x))
    except (InvalidOperation, ValueError, TypeError):
        return None


# ij_rates_v1 scalar key -> RateCard money column
_RATE_SCALARS = {
    "labourRate": "labour_rate", "demoRate": "demo_rate", "crewExtraRate": "crew_extra_rate",
    "recycleCharge": "recycle_charge", "diversionSurcharge": "diversion_surcharge",
    "diversionReport": "diversion_report", "gstPct": "gst_pct", "cardFeePct": "card_fee_pct",
}
# ij_rates_v1 JSONB key -> RateCard column
_RATE_JSONB = {
    "parking": "parking", "travel": "travel", "residentialLoads": "residential_loads",
    "commercialLoads": "commercial_loads", "residentialMin": "residential_min",
    "commercialIncludedMin": "commercial_included_min", "items": "specials", "ppe": "ppe",
    "bin": "bin_rates", "yardWaste": "yard_waste",
}
_ROLE = {r.value: r for r in DisposalRole}


def _apply_facilities(db: DbSession, brand: Brand, facs) -> dict:
    """Upsert disposal facilities by name; remove any not in a present, non-empty list."""
    if not isinstance(facs, list) or not facs:
        return {"skipped": "no facilities in payload"}
    seen, added, updated = set(), 0, 0
    for f in facs:
        if not isinstance(f, dict) or not (f.get("name") or "").strip():
            continue
        name = f["name"].strip()
        seen.add(name)
        row = db.scalar(select(DisposalFacility).where(DisposalFacility.brand == brand, DisposalFacility.name == name))
        role = _ROLE.get(f.get("role") or "cost", DisposalRole.cost)
        if row is None:
            db.add(DisposalFacility(brand=brand, name=name, role=role, note=(f.get("note") or None)))
            added += 1
        else:
            row.role, row.note = role, (f.get("note") or None)
            updated += 1
    removed = 0
    for row in db.scalars(select(DisposalFacility).where(DisposalFacility.brand == brand)).all():
        if row.name not in seen:
            db.delete(row)
            removed += 1
    return {"added": added, "updated": updated, "removed": removed}


def _apply_materials(db: DbSession, brand: Brand, mats, actor: Employee) -> dict:
    """Upsert disposal materials by `m` (resolve facility name -> id, log rate history on a
    cost/price change); remove any not in a present, non-empty list."""
    if not isinstance(mats, list) or not mats:
        return {"skipped": "no materials in payload"}
    fac_by_name = {f.name: f for f in db.scalars(select(DisposalFacility).where(DisposalFacility.brand == brand))}
    seen, added, updated, hist = set(), 0, 0, 0
    for m in mats:
        if not isinstance(m, dict) or not (m.get("m") or "").strip():
            continue
        mm = m["m"].strip()
        seen.add(mm)
        fac = fac_by_name.get((m.get("fac") or "").strip())
        cost, price = _dec(m.get("cost")), _dec(m.get("price"))
        row = db.scalar(select(DisposalMaterial).where(DisposalMaterial.brand == brand, DisposalMaterial.m == mm))
        changed = row is None or row.cost != cost or row.price != price
        if row is None:
            row = DisposalMaterial(brand=brand, m=mm)
            db.add(row)
            added += 1
        else:
            updated += 1
        row.facility_id = fac.id if fac else None
        row.cost, row.price, row.unit, row.note = cost, price, (m.get("unit") or None), (m.get("note") or None)
        db.flush()
        if changed:
            db.add(DisposalRateHistory(brand=brand, material_id=row.id, m=mm, cost=cost, price=price,
                                       unit=row.unit, changed_by=(actor.name if actor else None)))
            hist += 1
    removed = 0
    for row in db.scalars(select(DisposalMaterial).where(DisposalMaterial.brand == brand)).all():
        if row.m not in seen:
            db.delete(row)
            removed += 1
    return {"added": added, "updated": updated, "removed": removed, "history": hist}


def _slug(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").lower()).strip("_")


def _infer_pricing(cust: dict) -> ContractPricing:
    """Guess a custom customer's pricing mode from its rate units / kind text."""
    units = " ".join(str(r.get("unit", "")) for r in (cust.get("rates") or [])).lower()
    kind = (cust.get("kind") or "").lower()
    if "/hr" in units or "hour" in kind:
        return ContractPricing.hourly
    if "month" in kind:
        return ContractPricing.flatmonthly
    return ContractPricing.commercial


def _apply_surcharges(db: DbSession, brand: Brand, reg, roof) -> dict:
    """Persist the rate sheet's area surcharges — `surcharges` (regular bin) + `roofingSurcharges`
    keyed by area name -> area_surcharge rows. Reconcile within a present, non-empty regular map
    (never touches an `is_base` row)."""
    if not isinstance(reg, dict) or not reg:
        return {"skipped": "no surcharges in payload"}
    roof = roof if isinstance(roof, dict) else {}
    seen, added, updated = set(), 0, 0
    for area, amt in reg.items():
        area = (area or "").strip()
        if not area:
            continue
        seen.add(area)
        row = db.scalar(select(AreaSurcharge).where(AreaSurcharge.brand == brand, AreaSurcharge.area_name == area))
        if row is None:
            row = AreaSurcharge(brand=brand, area_name=area, aliases=[])
            db.add(row)
            added += 1
        else:
            updated += 1
        row.bin_amount = _dec(amt)
        row.roofing_bin_amount = _dec(roof.get(area))
    removed = 0
    for row in db.scalars(select(AreaSurcharge).where(AreaSurcharge.brand == brand)).all():
        if row.area_name not in seen and not row.is_base:
            db.delete(row)
            removed += 1
    return {"added": added, "updated": updated, "removed": removed}


def _apply_custom_customers(db: DbSession, brand: Brand, custs, actor: Employee) -> dict:
    """Persist the rate sheet's custom customers (Saanich/Oak Bay + owner-built) -> contract.
    Upsert by key `rc_<slug>`; rate-sheet-only extras (kind/disposal/bins/dumpRates/jobs) are
    preserved in `properties`."""
    if not isinstance(custs, list) or not custs:
        return {"skipped": "no custom customers"}
    added = updated = 0
    for c in custs:
        if not isinstance(c, dict) or not (c.get("name") or "").strip():
            continue
        name = c["name"].strip()
        key = "rc_" + _slug(name)
        row = db.scalar(select(Contract).where(Contract.brand == brand, Contract.key == key))
        if row is None:
            row = Contract(brand=brand, key=key, name=name, pricing=_infer_pricing(c))
            db.add(row)
            added += 1
        else:
            row.name, row.pricing = name, _infer_pricing(c)
            updated += 1
        row.short = name.replace("District of ", "")
        row.divisions = c.get("departments") or []
        row.shots = c.get("reqShots") or []
        row.extra = c.get("extra") or None
        row.po_req = bool(c.get("poReq"))
        row.terms = c.get("terms") or None
        row.rates = c.get("rates") or None
        extras = {k: c.get(k) for k in ("kind", "disposal", "bins", "dumpRates", "jobs") if c.get(k) is not None}
        row.properties = extras or None
    return {"added": added, "updated": updated}


def apply_rates(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Persist the rate sheet (`ij_rates_v1`) — the single source of truth for pricing.
    Owner-only. Writes rate_card scalars + JSONB, disposal facilities + materials, area
    surcharges (regular + roofing), and custom-customer contracts. Owner-authoritative
    reconcile-deletes happen only within a *present, non-empty* list; an absent/empty list
    is skipped (never 'delete all')."""
    if not is_owner(actor):
        return {"error": "forbidden — owner only"}
    if not isinstance(data, dict):
        return {"saved": False}
    rc = db.scalar(select(RateCard).where(RateCard.brand == brand))
    if rc is None:
        rc = RateCard(brand=brand)
        db.add(rc)
    for k, col in _RATE_SCALARS.items():
        if k in data:
            v = _dec(data[k])
            if v is not None:
                setattr(rc, col, v)
    for k, col in _RATE_JSONB.items():
        if k in data and data[k] is not None:
            setattr(rc, col, data[k])
    facs = _apply_facilities(db, brand, data.get("facilities"))
    mats = _apply_materials(db, brand, data.get("disposal"), actor)
    surs = _apply_surcharges(db, brand, data.get("surcharges"), data.get("roofingSurcharges"))
    custs = _apply_custom_customers(db, brand, data.get("customers"), actor)
    db.commit()
    return {"saved": True, "facilities": facs, "materials": mats, "surcharges": surs, "custom_customers": custs}


_PRICING = {p.value: p for p in ContractPricing}


def apply_contracts(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert user-added contracts (`ij_contracts_v1`, an object keyed by slug) -> contract.
    A near-1:1 model match. Upsert-only (built-in contracts stay runtime constants)."""
    if not isinstance(data, dict):
        return {"upserted": 0}
    n = 0
    for key, c in data.items():
        if not isinstance(c, dict) or not (c.get("name") or "").strip():
            continue
        row = db.scalar(select(Contract).where(Contract.brand == brand, Contract.key == key))
        if row is None:
            row = Contract(brand=brand, key=key, name=c["name"].strip(),
                           pricing=_PRICING.get(c.get("pricing"), ContractPricing.commercial))
            db.add(row)
        else:
            row.name = c["name"].strip()
            row.pricing = _PRICING.get(c.get("pricing"), row.pricing)
        row.short = c.get("short") or None
        row.rate_key = c.get("rateKey") or None
        row.divisions = c.get("divisions") or []
        row.route_divs = c.get("routeDivs") or []
        row.div_addable = bool(c.get("divAddable"))
        row.extra = c.get("extra") or None
        row.bin = bool(c.get("bin"))
        row.po_req = bool(c.get("poReq"))
        row.site_log = bool(c.get("siteLog"))
        row.shots = c.get("shots") or []
        row.terms = c.get("terms") or None
        row.rates = c.get("rates") if isinstance(c.get("rates"), list) else None
        row.flat = _dec(c.get("flat"))
        row.flat_unit = c.get("flatUnit") or None
        row.properties = c.get("properties") if isinstance(c.get("properties"), (list, dict)) else None
        row.note = c.get("note") or None
        n += 1
    db.commit()
    return {"upserted": n}


def apply_customers(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert residential customers (`ij_customers_v1`) — e.g. new customers saved during a
    booking. Dedupe on digits phone / email / first|last; **upsert-only, never delete**
    (the injected list can be thousands of rows; absence must not mean deletion)."""
    if not isinstance(data, list):
        return {"added": 0}
    existing = {
        residential_key({"phone": c.phone, "email": c.email, "first": c.first, "last": c.last}): c
        for c in db.scalars(select(ResidentialCustomer).where(ResidentialCustomer.brand == brand))
    }
    added = updated = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        first, last = (rec.get("first") or "").strip(), (rec.get("last") or "").strip()
        phone, email = (rec.get("phone") or "").strip()[:40], (rec.get("email") or "").strip()[:180]
        addr = (rec.get("addr") or "").strip()[:255]
        if not (first or last or phone or email):
            continue
        key = residential_key({"phone": phone, "email": email, "first": first, "last": last})
        c = existing.get(key)
        if c is None:
            c = ResidentialCustomer(brand=brand, first=first[:120] or None, last=last[:120] or None,
                                    phone=phone or None, email=email or None, addr=addr or None)
            db.add(c)
            existing[key] = c
            added += 1
        else:   # fill blanks only — never wipe an existing value with an empty one
            if phone and not c.phone:
                c.phone = phone
            if email and not c.email:
                c.email = email
            if addr and not c.addr:
                c.addr = addr
            updated += 1
    db.commit()
    return {"added": added, "matched": updated, "note": "upsert-only (no deletes)"}


def apply_company_customers(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert commercial customers (`ij_company_customers_v1`) incl. their department/location
    `accounts[]`. Dedupe on lowercased company name; upsert-only (no deletes)."""
    if not isinstance(data, list):
        return {"added": 0}
    existing = {company_key({"co": c.co}): c
                for c in db.scalars(select(CompanyCustomer).where(CompanyCustomer.brand == brand))}
    added = updated = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        co = (rec.get("co") or rec.get("name") or "").strip()
        if not co:
            continue
        accounts = rec.get("accounts") if isinstance(rec.get("accounts"), list) else None
        c = existing.get(company_key({"co": co}))
        if c is None:
            db.add(CompanyCustomer(
                brand=brand, co=co[:180], name=(rec.get("name") or co)[:180],
                contact=(rec.get("contact") or None), phone=(rec.get("phone") or None),
                email=(rec.get("email") or None), addr=(rec.get("addr") or None),
                accounts=accounts or [], src=CustomerSource.app))
            added += 1
        else:
            if rec.get("contact"):
                c.contact = rec["contact"]
            if rec.get("phone"):
                c.phone = rec["phone"]
            if rec.get("email"):
                c.email = rec["email"]
            if rec.get("addr"):
                c.addr = rec["addr"]
            if accounts is not None:
                c.accounts = accounts
            updated += 1
    db.commit()
    return {"added": added, "matched": updated, "note": "upsert-only (no deletes)"}


def _as_uuid(x) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(x))
    except (ValueError, TypeError, AttributeError):
        return None


def apply_pm(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert the property-management tree (`ij_pm_db_v2`): companies → groups → buildings.
    Matches an existing row by its DB-uuid id (emitted by `build_pm_db_v2`) else by name, so
    a re-sync before reload never duplicates. Upsert-only (no deletes)."""
    if not isinstance(data, list):
        return {"companies_added": 0}
    nc = ng = nb = 0
    for co in data:
        if not isinstance(co, dict) or not (co.get("nm") or "").strip():
            continue
        nm = co["nm"].strip()
        cid = _as_uuid(co.get("id"))
        company = db.scalar(select(PmCompany).where(PmCompany.brand == brand, PmCompany.id == cid)) if cid else None
        if company is None:
            company = db.scalar(select(PmCompany).where(PmCompany.brand == brand, PmCompany.nm == nm))
        if company is None:
            company = PmCompany(brand=brand, nm=nm)
            db.add(company)
            nc += 1
        company.addr = co.get("addr") or None
        company.email = co.get("email") or None
        company.contact = co.get("contact") or None
        company.phone = co.get("phone") or None
        db.flush()
        for g in (co.get("groups") or []):
            if not isinstance(g, dict):
                continue
            gnm = (g.get("nm") or "").strip()
            gid = _as_uuid(g.get("id"))
            group = db.scalar(select(PmGroup).where(PmGroup.brand == brand, PmGroup.id == gid)) if gid else None
            if group is None:
                group = db.scalar(select(PmGroup).where(
                    PmGroup.brand == brand, PmGroup.company_id == company.id, PmGroup.nm == gnm))
            if group is None:
                group = PmGroup(brand=brand, company_id=company.id, nm=gnm)
                db.add(group)
                ng += 1
            else:
                group.nm = gnm
            db.flush()
            for b in (g.get("bldgs") or []):
                if not isinstance(b, dict):
                    continue
                bname, baddr = (b.get("n") or "").strip(), (b.get("a") or "").strip()
                if not (bname or baddr):
                    continue
                bid = _as_uuid(b.get("id"))
                bldg = db.scalar(select(PmBuilding).where(PmBuilding.brand == brand, PmBuilding.id == bid)) if bid else None
                if bldg is None:
                    bldg = db.scalar(select(PmBuilding).where(
                        PmBuilding.brand == brand, PmBuilding.group_id == group.id,
                        PmBuilding.name == (bname or None), PmBuilding.address == (baddr or None)))
                if bldg is None:
                    bldg = PmBuilding(brand=brand, group_id=group.id)
                    db.add(bldg)
                    nb += 1
                bldg.name, bldg.address = bname or None, baddr or None
                bldg.email = b.get("email") or None
                bldg.contact = b.get("contact") or None
                bldg.phone = b.get("phone") or None
    db.commit()
    return {"companies_added": nc, "groups_added": ng, "buildings_added": nb}


HANDLERS = {
    "ij_bins_v1": apply_bins,
    "ij_fleet_v1": apply_fleet,
    "ij_colourmap_v1": apply_colourmap,
    "ij_employees_v1": apply_employees,
    "ij_incidents_v1": apply_incidents,
    "ij_clock_log": apply_clock,
    "ij_jobs_v1": apply_field_jobs,
    "ij_weighlog_v1": apply_weigh,
    "ij_binday_v1": apply_binday,
    "ij_tares_v1": apply_tares,
    "ij_weighins_v1": apply_weighins,
    "ij_tooldaily_v1": apply_tooldaily,
    "ij_dayboard_status_v1": apply_dayboard_status,
    "ij_dayboard_notes_v1": apply_dayboard_notes,
    "ij_dayboard_sitelog_v1": apply_dayboard_sitelog,
    "ij_attendance_v1": apply_attendance,
    "ij_breaks_v1": apply_breaks,
    "ij_daynotes_v1": apply_daynotes,
    "ij_binsout_cfg_v1": apply_binsout_cfg,
    "ij_checklists_v1": apply_checklists,
    "ij_reviews_v1": apply_reviews,
    "ij_usage_v1": apply_usage,
    "ij_precheck_v1": apply_precheck,
    "ij_po_needed_v1": apply_po_needed,
    "ij_maint_v2": apply_maint,
    "ij_fixes_v1": apply_fixes,
    "ij_fixes_resolved_v1": apply_fixes_resolved,
    "ij_reminders_v1": apply_reminders,
    "ij_rates_v1": apply_rates,
    "ij_customers_v1": apply_customers,
    "ij_company_customers_v1": apply_company_customers,
    "ij_pm_db_v2": apply_pm,
    "ij_contracts_v1": apply_contracts,
}
