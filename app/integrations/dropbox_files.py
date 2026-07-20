"""Dropbox — auto-file each job's photos into a per-job folder. Writes ONLY under the
configured root (the TEST folder until go-live, §2/§4/§10) — every upload asserts the
target path is inside that root before doing anything, mirroring the calendar guard.

Creds in `.env`; absent → dry-run (returns a placeholder path, uploads nothing). Uses
httpx directly (already a dep).
"""
from __future__ import annotations

import base64
import json
import re

from app.core.config import settings


class DropboxGuardError(RuntimeError):
    pass


def is_configured() -> bool:
    return settings.is_dropbox_configured


def _safe(part: str) -> str:
    """A path segment safe for Dropbox (no slashes / control chars)."""
    return re.sub(r"[^A-Za-z0-9._ #-]+", "_", (part or "").strip()) or "untitled"


def _assert_under_root(path: str) -> str:
    root = settings.dropbox_root.rstrip("/")
    if not path.startswith(root + "/"):
        raise DropboxGuardError(f"REFUSING: '{path}' is outside the configured Dropbox root '{root}'.")
    return path


def decode_data_url(data_url: str) -> tuple[bytes, str]:
    """`data:image/jpeg;base64,...` -> (bytes, extension). Falls back to ('', 'bin')."""
    m = re.match(r"data:([^;,]+)?(;base64)?,(.*)$", data_url or "", re.DOTALL)
    if not m:
        return b"", "bin"
    mime, is_b64, payload = m.group(1) or "", m.group(2), m.group(3)
    raw = base64.b64decode(payload) if is_b64 else payload.encode("utf-8", "ignore")
    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(mime, "jpg")
    return raw, ext


def job_photo_path(job_ref: str, filename: str) -> str:
    """`<root>/<job>/<filename>` — the per-job folder (§10 'auto-file per job')."""
    root = settings.dropbox_root.rstrip("/")
    return f"{root}/{_safe(job_ref)}/{_safe(filename)}"


def upload_bytes(*, path: str, data: bytes) -> dict:
    """Upload raw bytes to a path UNDER the root. Returns {uploaded, path, dry_run}. The
    root guard runs in both modes; dry-run uploads nothing."""
    _assert_under_root(path)
    if not is_configured():
        return {"uploaded": False, "path": path, "dry_run": True, "bytes": len(data)}
    import httpx
    resp = httpx.post(
        "https://content.dropboxapi.com/2/files/upload",
        headers={
            "Authorization": f"Bearer {settings.dropbox_access_token}",
            "Dropbox-API-Arg": json.dumps({"path": path, "mode": "add", "autorename": True, "mute": True}),
            "Content-Type": "application/octet-stream",
        },
        content=data, timeout=60,
    )
    resp.raise_for_status()
    return {"uploaded": True, "path": resp.json().get("path_lower", path), "dry_run": False}


def upload_job_photo(*, job_ref: str, filename: str, data_url: str) -> dict:
    """File one job photo (a data-URL from the crew form) into the job's folder."""
    raw, ext = decode_data_url(data_url)
    if not filename.lower().endswith(("." + ext, ".jpg", ".png", ".webp")):
        filename = f"{filename}.{ext}"
    return upload_bytes(path=job_photo_path(job_ref, filename), data=raw)


# ── Per-job folder + shared link (Phase 1: created at booking, link rides into the calendar) ──

def job_folder_path(brand_value: str, on_date_iso: str, customer: str | None, job_id: str) -> str:
    """`<root>/<brand>/<date customer short-id>` — one findable folder per job."""
    root = settings.dropbox_root.rstrip("/")
    short = (job_id or "").split("-")[0]
    name = _safe(f"{on_date_iso} {customer or 'job'} {short}".strip())
    return f"{root}/{_safe(brand_value)}/{name}"


def create_folder(access_token: str, path: str) -> None:
    """Create a folder under the root (idempotent — an existing folder / 409 is fine). Dropbox
    create_folder_v2 creates any missing parent folders."""
    _assert_under_root(path)
    import httpx
    resp = httpx.post(
        "https://api.dropboxapi.com/2/files/create_folder_v2",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={"path": path, "autorename": False}, timeout=30,
    )
    if resp.status_code == 409:
        return   # already exists — idempotent
    if resp.status_code >= 400:
        raise DropboxGuardError(f"Dropbox create_folder {resp.status_code}: {resp.text[:200]}")


def ensure_shared_link(access_token: str, path: str) -> str | None:
    """Return a stable shared link for the folder, creating one if needed. This is the URL that
    rides into the calendar event so searching the job opens all its photos."""
    import httpx
    hdr = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = httpx.post(
        "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings",
        headers=hdr, json={"path": path}, timeout=30,
    )
    if resp.status_code < 400:
        return resp.json().get("url")
    if resp.status_code == 409:   # a link already exists — fetch it
        r2 = httpx.post(
            "https://api.dropboxapi.com/2/sharing/list_shared_links",
            headers=hdr, json={"path": path, "direct_only": True}, timeout=30,
        )
        if r2.status_code < 400:
            links = r2.json().get("links", [])
            if links:
                return links[0].get("url")
    return None


def ensure_job_folder(db, job, on_date) -> str | None:
    """At booking: create the job's Dropbox folder + a stable shared link, stash {folder, link} on
    job.details['dropbox'], and return the link. Dry-run (None) when Dropbox isn't connected — the
    booking proceeds either way (the caller wraps this best-effort)."""
    from app.integrations import dropbox_oauth
    token = dropbox_oauth.get_valid_access_token(db)
    if not token:
        return None
    path = job_folder_path(job.brand.value, on_date.isoformat(), job.customer_name, str(job.id))
    create_folder(token, path)
    link = ensure_shared_link(token, path)
    details = dict(job.details or {})
    details["dropbox"] = {"folder": path, "link": link}
    job.details = details
    return link
