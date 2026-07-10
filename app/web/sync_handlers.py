"""localStorage -> Postgres sync handlers (reverse of app/web/refs.py builders).

Each handler takes the full localStorage value for a key and **upserts** it into the
DB — never a blind replace, never delete-by-absence (too dangerous for a generic
whole-array sync). Removal is explicit (`active: false` / a status), not by omission.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.auth.guards import is_owner
from app.auth.security import hash_pin
from app.models.bins import Bin
from app.models.clock import ClockPunch
from app.models.employee import Employee
from app.models.enums import BinStatus, Brand, DisposalRole, OWNER_ONLY_GRANTABLE, PayType, ReminderKind
from app.models.field_job import FieldJob
from app.models.incident import Incident
from app.models.maintenance import DefectFlag, MaintenanceDoc
from app.models.rates import DisposalFacility, DisposalMaterial, DisposalRateHistory, RateCard
from app.models.reminder import Reminder
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


def apply_bins(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Upsert bin state/location by `code`. The fleet is fixed — unknown codes are ignored."""
    if not isinstance(data, list):
        return {"updated": 0, "skipped": "not a list"}
    updated = 0
    for rec in data:
        if not isinstance(rec, dict) or not rec.get("code"):
            continue
        b = db.scalar(select(Bin).where(Bin.brand == brand, Bin.code == rec["code"]))
        if b is None:
            continue
        changed = False
        st = _STATE_REV.get(rec.get("state"))
        if st is not None and b.status != st:
            b.status, changed = st, True
        job = rec.get("job") if isinstance(rec.get("job"), dict) else None
        if job is not None:
            cust, addr = (job.get("customer") or None), (job.get("address") or None)
            if b.customer != cust:
                b.customer, changed = cust, True
            if b.address != addr:
                b.address, changed = addr, True
        if "type" in rec and b.type != (rec.get("type") or None):
            b.type, changed = (rec.get("type") or None), True
        updated += 1 if changed else 0
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
    """Upsert one punch per (name, work_date); fill in/out/done times as they arrive."""
    if not isinstance(data, list):
        return {"upserted": 0}
    n = 0
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
        n += 1
    db.commit()
    return {"upserted": n}


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
    """Append weigh events; dedup by (source_at, bin) so re-syncs don't duplicate."""
    if not isinstance(data, list):
        return {"added": 0}
    added = 0
    for rec in data:
        if not isinstance(rec, dict):
            continue
        at, binc = rec.get("at"), rec.get("bin")
        if at is not None and db.scalar(select(WeighLog).where(
                WeighLog.brand == brand, WeighLog.source_at == at, WeighLog.bin == binc)):
            continue
        db.add(WeighLog(
            brand=brand, source_at=at, weigh_date=_pdate(rec.get("date")), weigh_time=rec.get("time"),
            who=rec.get("who"), truck=rec.get("truck"), bin=binc, cls=rec.get("cls"),
            source=rec.get("source"), front_kg=rec.get("f"), rear_kg=rec.get("r"), total_kg=rec.get("total"),
        ))
        added += 1
    db.commit()
    return {"added": added}


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


def apply_rates(db: DbSession, brand: Brand, data, actor: Employee) -> dict:
    """Persist the rate sheet (`ij_rates_v1`) — the single source of truth for pricing.
    Owner-only. Writes rate_card scalars + JSONB substructures and upserts disposal
    facilities + materials. The owner is authoritative for facilities/materials: within a
    *present, non-empty* list, items no longer in it are removed; an absent/empty list is
    skipped (never 'delete all'). Custom-customer rate profiles (`data['customers']`) are
    handled by the contracts write-back, not here."""
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
    db.commit()
    return {"saved": True, "facilities": facs, "materials": mats}


HANDLERS = {
    "ij_bins_v1": apply_bins,
    "ij_employees_v1": apply_employees,
    "ij_incidents_v1": apply_incidents,
    "ij_clock_log": apply_clock,
    "ij_jobs_v1": apply_field_jobs,
    "ij_weighlog_v1": apply_weigh,
    "ij_maint_v2": apply_maint,
    "ij_fixes_v1": apply_fixes,
    "ij_fixes_resolved_v1": apply_fixes_resolved,
    "ij_reminders_v1": apply_reminders,
    "ij_rates_v1": apply_rates,
}
