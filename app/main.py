"""FastAPI entrypoint. Run: uvicorn app.main:app --reload"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session as DbSession

import app.models.all  # noqa: F401  (register every model so cross-table FKs resolve at runtime)
from app.api.auth import router as auth_router
from app.api.booking import router as booking_router
from app.api.customers import router as customers_router
from app.api.day_board import router as day_board_router
from app.api.disposal import router as disposal_router
from app.api.reminders import router as reminders_router
from app.api.sync import router as sync_router
from app.api.yard import router as yard_router
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import Brand
from app.web.refs import reference_bootstrap_script

app = FastAPI(title=settings.app_name)
app.include_router(auth_router)
app.include_router(booking_router)
app.include_router(customers_router)
app.include_router(day_board_router)
app.include_router(disposal_router)
app.include_router(reminders_router)
app.include_router(sync_router)
app.include_router(yard_router)

_PROTOTYPES = Path(__file__).resolve().parent.parent / "prototypes"
_STATIC = Path(__file__).resolve().parent / "static"
_MAIN_HUB_HTML = _PROTOTYPES / "island-junk-main-hub.html"


def _serve_prototype(html_path: Path, db: DbSession, keys: list[str],
                     bridge: str | None = None, brand: Brand = Brand.victoria) -> HTMLResponse:
    """Serve an approved prototype (file untouched) with the requested real DB
    reference data injected early + (optionally) the screen's bridge appended."""
    html = html_path.read_text(encoding="utf-8")
    boot = reference_bootstrap_script(db, brand, keys)
    html = html.replace("</head>", boot + "\n</head>", 1) if "</head>" in html else boot + html
    # sync bridge on every page (persists synced-key writes); then the screen's own bridge.
    tail = '<script src="/static/sync-bridge.js"></script>\n'
    if bridge:
        tail += f'<script src="/static/{bridge}"></script>\n'
    html = html.replace("</body>", tail + "</body>")
    return HTMLResponse(html)

# Bridge scripts etc.
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")
# The raw approved screens as-is (the UI spec).
if _PROTOTYPES.is_dir():
    app.mount("/prototypes", StaticFiles(directory=str(_PROTOTYPES), html=True), name="prototypes")


_DISPATCH_REFS = ["ij_fleet_v1", "ij_colourmap_v1"]
_CUSTOMER_REFS = ["ij_customers_v1", "ij_company_customers_v1", "ij_pm_db_v2"]
_HUB_REFS = ["ij_employees_v1", "ij_fleet_v1", "ij_colourmap_v1", "ij_bins_v1"]

# slug -> {file, refs keys injected from DB, optional bridge}. The Main Hub launcher
# navigates here (its go() is remapped by main-hub-bridge.js).
SCREENS: dict[str, dict] = {
    "new-booking":     {"file": "island-junk-new-booking-v67.html", "keys": _DISPATCH_REFS + _CUSTOMER_REFS, "bridge": "booking-bridge.js"},
    "day-board":       {"file": "island-junk-day-board-v28.html",   "keys": _DISPATCH_REFS, "bridge": "day-board-bridge.js"},
    "bin-registry":    {"file": "island-junk-bin-registry-v6.html", "keys": ["ij_bins_v1"], "bridge": None},
    "residential-calculator": {"file": "CREW-residential-calculator-v25.html", "keys": ["ij_rates_v1", "ij_employees_v1", "ij_jobs_v1"], "bridge": None},
    "commercial-form": {"file": "CREW-commercial-form-v22.html", "keys": ["ij_rates_v1", "ij_employees_v1", "ij_jobs_v1"], "bridge": None},
    "owner-hub":       {"file": "island-junk-owner-hub-v54.html",   "keys": _HUB_REFS, "bridge": None},
    "manager-hub":     {"file": "island-junk-management-hub-v83.html", "keys": _HUB_REFS, "bridge": None},
    "truck-hub":       {"file": "island-junk-truck-hub-v54.html",   "keys": ["ij_employees_v1", "ij_fleet_v1", "ij_fixes_v1"], "bridge": None},
    "bin-tracker":     {"file": "island-junk-bin-tracker-v34.html", "keys": ["ij_bins_v1", "ij_fleet_v1"], "bridge": None},
    "yard-hub":        {"file": "island-junk-yard-hub-v19.html",    "keys": ["ij_employees_v1", "ij_bins_v1", "ij_weighlog_v1"], "bridge": None},
    "yard-processing": {"file": "island-junk-yard-processing-v28.html", "keys": ["ij_bins_v1", "ij_weighlog_v1"], "bridge": "yard-processing-bridge.js"},
    "maintenance-hub": {"file": "island-junk-maintenance-hub-v12.html", "keys": ["ij_fleet_v1", "ij_maint_v2", "ij_fixes_v1"], "bridge": None},
    "clock-out":       {"file": "island-junk-clock-out-v9.html",    "keys": ["ij_employees_v1", "ij_clock_log"], "bridge": None},
    "employee-hours":  {"file": "island-junk-employee-hours-v6.html", "keys": ["ij_employees_v1", "ij_clock_log"], "bridge": None},
    "incident-report": {"file": "island-junk-incident-report-v2.html", "keys": ["ij_employees_v1", "ij_incidents_v1"], "bridge": None},
    "reminders":       {"file": "island-junk-reminders-v1.html",   "keys": ["ij_reminders_v1"], "bridge": None},
    "swing-board":     {"file": "island-junk-swing-board-v5.html",  "keys": _DISPATCH_REFS, "bridge": None},
    "estimate-builder": {"file": "island-junk-estimate-builder-v4.html", "keys": [], "bridge": None},
    "rate-sheet":      {"file": "island-junk-rate-sheet-v14.html", "keys": ["ij_rates_v1"], "bridge": None},
}


@app.get("/app", response_class=HTMLResponse)
@app.get("/app/", response_class=HTMLResponse)
def main_hub(db: DbSession = Depends(get_db)) -> HTMLResponse:
    """Main Hub — launcher + real PIN login (via main-hub-bridge.js)."""
    return _serve_prototype(_MAIN_HUB_HTML, db, ["ij_employees_v1", "ij_clock_log"], bridge="main-hub-bridge.js")


@app.get("/app/{slug}", response_class=HTMLResponse)
def app_screen(slug: str, db: DbSession = Depends(get_db)) -> HTMLResponse:
    """Serve any registered approved screen with its real DB refs + bridge."""
    scr = SCREENS.get(slug)
    if scr is None:
        raise HTTPException(status_code=404, detail=f"Unknown screen '{slug}'")
    path = _PROTOTYPES / scr["file"]
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prototype missing: {scr['file']}")
    return _serve_prototype(path, db, scr["keys"], bridge=scr["bridge"])


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "db_configured": settings.is_db_configured,
    }
