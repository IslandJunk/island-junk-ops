"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DbSession

import app.models.all  # noqa: F401  (register every model so cross-table FKs resolve at runtime)
from app.api.auth import router as auth_router
from app.api.booking import router as booking_router
from app.api.customers import router as customers_router
from app.api.day_board import router as day_board_router
from app.api.disposal import router as disposal_router
from app.api.dropbox import router as dropbox_router
from app.api.integrations import router as integrations_router
from app.api.invoicing import router as invoicing_router
from app.api.job_photos import router as job_photos_router
from app.api.quickbooks import router as quickbooks_router
from app.api.reminders import router as reminders_router
from app.api.reviews import router as reviews_router
from app.api.sms import router as sms_router
from app.api.sync import router as sync_router
from app.api.yard import router as yard_router
from app.api.deps import optional_brand
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import Brand
from app.web.refs import reference_bootstrap_script


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    """Start the QBO auto-sync background loop. Best-effort: a scheduler hiccup never blocks the
    web app from serving, and the loop sleeps before its first run + swallows its own errors."""
    import asyncio
    task = None
    try:
        from app.quickbooks.scheduler import qbo_poll_loop
        task = asyncio.create_task(qbo_poll_loop())
    except Exception:
        task = None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()


app = FastAPI(title=settings.app_name, lifespan=_lifespan)
app.include_router(auth_router)
app.include_router(booking_router)
app.include_router(customers_router)
app.include_router(day_board_router)
app.include_router(disposal_router)
app.include_router(dropbox_router)
app.include_router(integrations_router)
app.include_router(invoicing_router)
app.include_router(job_photos_router)
app.include_router(quickbooks_router)
app.include_router(reminders_router)
app.include_router(reviews_router)
app.include_router(sms_router)
app.include_router(sync_router)
app.include_router(yard_router)


# ── Public legal pages (required by Intuit to unlock QuickBooks production keys) ──────────────
# The app is an INTERNAL tool, but Intuit's app profile needs public EULA + privacy URLs. These
# live on the app's own domain so they're always reachable. Plain static HTML, no data access.
_LEGAL_WRAP = ('<!doctype html><meta charset="utf-8">'
               '<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>'
               '<div style="font-family:Inter,system-ui,sans-serif;max-width:760px;margin:6vh auto;'
               'padding:0 22px;color:#222;line-height:1.6">{body}'
               '<p style="margin-top:32px;color:#888;font-size:13px">Island Junk Solutions · '
               'contact: wes@islandjunk.com</p></div>')

_PRIVACY_HTML = _LEGAL_WRAP.format(title="Privacy Policy — Island Junk Operations App", body=(
    "<h1>Privacy Policy</h1><p><em>Island Junk Operations App — last updated July 2026</em></p>"
    "<p>The Island Junk Operations App (the “App”) is a private, internal tool used by Island "
    "Junk Solutions (“we”, “us”) to run our junk-removal and bin-rental operations. It "
    "is not a public consumer product; access is limited to our authorized staff.</p>"
    "<h3>Information we handle</h3><p>The App stores operational data our staff enter — bookings, job "
    "details, crew assignments, bin tracking, customer contact details, and job photos. It connects to "
    "third-party services we use to run the business: QuickBooks Online, Square, Twilio, Google Calendar, "
    "and Dropbox.</p>"
    "<h3>QuickBooks Online</h3><p>With your authorization, the App connects to QuickBooks Online in "
    "<strong>read-only</strong> mode. It reads invoice and payment status to track which jobs have been "
    "invoiced and paid. The App never creates, edits, sends, or deletes anything in QuickBooks, and never "
    "accesses data beyond what is needed for this purpose.</p>"
    "<h3>How we use information</h3><p>Solely to operate our business — scheduling, dispatch, invoicing "
    "follow-up, and customer communication. We do not sell your information, and we share it only with the "
    "service providers above as needed to run the App.</p>"
    "<h3>Security &amp; retention</h3><p>Access is restricted to authorized staff via per-user login; "
    "sensitive credentials and access tokens are stored encrypted. Operational records are retained as long "
    "as needed for business and legal purposes.</p>"
    "<h3>Contact</h3><p>Questions about this policy: wes@islandjunk.com.</p>"))

_EULA_HTML = _LEGAL_WRAP.format(title="End User License Agreement — Island Junk Operations App", body=(
    "<h1>End User License Agreement</h1><p><em>Island Junk Operations App — last updated July 2026</em></p>"
    "<p>This agreement governs use of the Island Junk Operations App (the “App”), provided by "
    "Island Junk Solutions.</p>"
    "<h3>1. License</h3><p>The App is licensed for use solely by Island Junk Solutions’ authorized "
    "staff to operate the business. No other use is licensed.</p>"
    "<h3>2. Acceptable use</h3><p>Users will access the App only as authorized and only for legitimate "
    "business purposes.</p>"
    "<h3>3. Third-party services</h3><p>The App integrates with third-party services (including QuickBooks "
    "Online, used in read-only mode). Use of those services is subject to their own terms.</p>"
    "<h3>4. No warranty</h3><p>The App is provided “as is,” without warranties of any kind, to the "
    "extent permitted by law.</p>"
    "<h3>5. Limitation of liability</h3><p>To the extent permitted by law, Island Junk Solutions is not "
    "liable for indirect or consequential damages arising from use of the App.</p>"
    "<h3>6. Governing law</h3><p>This agreement is governed by the laws of British Columbia, Canada.</p>"
    "<h3>7. Contact</h3><p>wes@islandjunk.com.</p>"))


@app.get("/legal/privacy", response_class=HTMLResponse)
def legal_privacy() -> HTMLResponse:
    return HTMLResponse(_PRIVACY_HTML)


@app.get("/legal/eula", response_class=HTMLResponse)
def legal_eula() -> HTMLResponse:
    return HTMLResponse(_EULA_HTML)


_PROTOTYPES = Path(__file__).resolve().parent.parent / "prototypes"
_STATIC = Path(__file__).resolve().parent / "static"
_MAIN_HUB_HTML = _PROTOTYPES / "island-junk-main-hub.html"


def _serve_prototype(html_path: Path, db: DbSession, keys: list[str],
                     bridge: str | None = None, brand: Brand = Brand.victoria) -> HTMLResponse:
    """Serve an approved prototype (file untouched) with the requested real DB
    reference data injected early + (optionally) the screen's bridge appended."""
    html = html_path.read_text(encoding="utf-8")
    # Tell the page (and its sync bridge) which brand it was served with, so every write is
    # tagged with the brand the user was actually looking at (never-mix, §15).
    brand_marker = f"<script>window.__IJ_BRAND={json.dumps(brand.value)};</script>\n"
    boot = brand_marker + reference_bootstrap_script(db, brand, keys)
    html = html.replace("</head>", boot + "\n</head>", 1) if "</head>" in html else boot + html
    # sync bridge on every page (persists synced-key writes); then the screen's own bridge.
    tail = '<script src="/static/sync-bridge.js"></script>\n'
    if bridge:
        tail += f'<script src="/static/{bridge}"></script>\n'
    # Inject before the LAST </body> only. Some prototypes embed "</body>" inside JS
    # export-template strings (e.g. the owner hub's print/PDF docs); a replace-all would
    # inject a <script> mid-string and break that whole script block.
    idx = html.rfind("</body>")
    html = (html[:idx] + tail + html[idx:]) if idx != -1 else (html + tail)
    return HTMLResponse(html)

# Bridge scripts etc.
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
# The raw approved screens as-is (the UI spec).
if _PROTOTYPES.is_dir():
    app.mount("/prototypes", StaticFiles(directory=str(_PROTOTYPES), html=True), name="prototypes")


_DISPATCH_REFS = ["ij_fleet_v1", "ij_colourmap_v1"]
_CUSTOMER_REFS = ["ij_customers_v1", "ij_company_customers_v1", "ij_pm_db_v2", "ij_contracts_v1"]
_HUB_REFS = ["ij_employees_v1", "ij_fleet_v1", "ij_colourmap_v1", "ij_bins_v1"]
_DAYBOARD_REFS = ["ij_dayboard_status_v1", "ij_dayboard_notes_v1", "ij_dayboard_sitelog_v1"]
# HR + office overlays the manager/owner hubs read (attendance grid, break totals, office notes).
_HR_REFS = ["ij_attendance_v1", "ij_breaks_v1", "ij_daynotes_v1", "ij_binsout_cfg_v1"]

# slug -> {file, refs keys injected from DB, optional bridge}. The Main Hub launcher
# navigates here (its go() is remapped by main-hub-bridge.js).
SCREENS: dict[str, dict] = {
    "new-booking":     {"file": "island-junk-new-booking-v67.html", "keys": _DISPATCH_REFS + _CUSTOMER_REFS + ["ij_rates_v1", "ij_po_needed_v1"], "bridge": "booking-bridge.js"},
    "day-board":       {"file": "island-junk-day-board-v28.html",   "keys": _DISPATCH_REFS + _DAYBOARD_REFS + ["ij_checklists_v1"], "bridge": "day-board-bridge.js"},
    "bin-registry":    {"file": "island-junk-bin-registry-v6.html", "keys": ["ij_bins_v1", "ij_binsout_cfg_v1"], "bridge": None},
    "residential-calculator": {"file": "CREW-residential-calculator-v25.html", "keys": ["ij_rates_v1", "ij_employees_v1", "ij_jobs_v1", "ij_reviews_v1", "ij_usage_v1", "ij_owner_cfg_v1"], "bridge": "residential-calculator-bridge.js"},
    "commercial-form": {"file": "CREW-commercial-form-v22.html", "keys": ["ij_rates_v1", "ij_employees_v1", "ij_jobs_v1", "ij_usage_v1", "ij_owner_cfg_v1"], "bridge": None},
    "owner-hub":       {"file": "island-junk-owner-hub-v54.html",   "keys": _HUB_REFS + _HR_REFS + ["ij_usage_v1", "ij_checklists_v1", "ij_po_needed_v1", "ij_po_seeded_v1", "ij_owner_cfg_v1"], "bridge": "owner-hub-bridge.js"},
    "manager-hub":     {"file": "island-junk-management-hub-v83.html", "keys": _HUB_REFS + _HR_REFS + ["ij_reviews_v1", "ij_usage_v1", "ij_po_needed_v1", "ij_owner_cfg_v1"], "bridge": "manager-hub-bridge.js"},
    "truck-hub":       {"file": "island-junk-truck-hub-v54.html",   "keys": ["ij_employees_v1", "ij_fleet_v1", "ij_fixes_v1", "ij_daynotes_v1", "ij_usage_v1", "ij_checklists_v1"], "bridge": None},
    "bin-tracker":     {"file": "island-junk-bin-tracker-v34.html", "keys": ["ij_bins_full_v1", "ij_fleet_v1", "ij_tares_v1", "ij_weighins_v1", "ij_daynotes_v1", "ij_binsout_cfg_v1"], "bridge": "bin-tracker-bridge.js"},
    "yard-hub":        {"file": "island-junk-yard-hub-v19.html",    "keys": ["ij_employees_v1", "ij_bins_v1", "ij_weighlog_v1", "ij_tares_v1", "ij_weighins_v1", "ij_breaks_v1", "ij_daynotes_v1"], "bridge": None},
    "yard-processing": {"file": "island-junk-yard-processing-v28.html", "keys": ["ij_bins_v1", "ij_weighlog_v1", "ij_tares_v1", "ij_weighins_v1", "ij_checklists_v1"], "bridge": "yard-processing-bridge.js"},
    "maintenance-hub": {"file": "island-junk-maintenance-hub-v12.html", "keys": ["ij_fleet_v1", "ij_maint_v2", "ij_fixes_v1"], "bridge": None},
    "clock-out":       {"file": "island-junk-clock-out-v9.html",    "keys": ["ij_employees_v1", "ij_clock_log"], "bridge": None},
    "employee-hours":  {"file": "island-junk-employee-hours-v6.html", "keys": ["ij_employees_v1", "ij_clock_log", "ij_breaks_v1"], "bridge": None},
    "incident-report": {"file": "island-junk-incident-report-v2.html", "keys": ["ij_employees_v1", "ij_incidents_v1"], "bridge": None},
    "reminders":       {"file": "island-junk-reminders-v1.html",   "keys": ["ij_reminders_v1"], "bridge": None},
    "save-card":       {"file": "island-junk-save-card.html",      "keys": [], "bridge": "save-card-bridge.js"},
    "swing-board":     {"file": "island-junk-swing-board-v5.html",  "keys": _DISPATCH_REFS, "bridge": None},
    "estimate-builder": {"file": "island-junk-estimate-builder-v4.html", "keys": [], "bridge": None},
    "rate-sheet":      {"file": "island-junk-rate-sheet-v14.html", "keys": ["ij_rates_v1"], "bridge": None},
}


@app.get("/app", response_class=HTMLResponse)
@app.get("/app/", response_class=HTMLResponse)
def main_hub(request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse:
    """Main Hub — launcher + real PIN login (via main-hub-bridge.js)."""
    brand = optional_brand(request, db)
    return _serve_prototype(_MAIN_HUB_HTML, db, ["ij_employees_v1", "ij_clock_log"],
                            bridge="main-hub-bridge.js", brand=brand)


@app.get("/app/{slug}", response_class=HTMLResponse)
def app_screen(slug: str, request: Request, db: DbSession = Depends(get_db)) -> HTMLResponse:
    """Serve any registered approved screen with its real DB refs + bridge, scoped to the
    signed-in user's active brand (owner-switchable; crew locked; default Victoria)."""
    scr = SCREENS.get(slug)
    if scr is None:
        raise HTTPException(status_code=404, detail=f"Unknown screen '{slug}'")
    path = _PROTOTYPES / scr["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prototype missing: {scr['file']}")
    brand = optional_brand(request, db)
    return _serve_prototype(path, db, scr["keys"], bridge=scr["bridge"], brand=brand)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "db_configured": settings.is_db_configured,
    }
