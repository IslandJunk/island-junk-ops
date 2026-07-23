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

def _town_from_address(address: str | None) -> str:
    """Best-effort town/area pulled from a freeform address, for folder searchability.
    Canadian addresses read 'street, TOWN PROV POSTAL, country' — take the segment after
    the first comma and strip the province + postal noise. Returns '' when nothing clean is
    found (the folder name simply omits it — never guesses)."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) < 2:
        return ""
    seg = parts[1]
    seg = re.sub(r"\b[A-Za-z]\d[A-Za-z]\s*\d[A-Za-z]\d\b", "", seg)          # postal code (V9Z 0P6)
    seg = re.sub(r"\bB\.?\s*C\.?\b|\bBritish Columbia\b", "", seg, flags=re.I)  # province
    return seg.strip(" .")


def job_folder_path(
    brand_value: str, on_date_iso: str, customer: str | None, job_id: str,
    *, phone: str | None = None, address: str | None = None,
) -> str:
    """`<root>/<brand>/<date customer [town] [phone] short-id>` — one findable folder per job.

    Date + name + town + phone are all packed into the name so a later Dropbox search finds
    the folder by ANY of them; the short id keeps it unique AND cross-references the calendar
    event (which carries `[app job <id>]`). Empty parts are dropped — never 'None', never a
    double space."""
    root = settings.dropbox_root.rstrip("/")
    short = (job_id or "").split("-")[0]
    parts = [on_date_iso, (customer or "job"), _town_from_address(address), (phone or ""), short]
    name = _safe(" ".join(p for p in (p.strip() for p in parts) if p))
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
    path = job_folder_path(
        job.brand.value, on_date.isoformat(), job.customer_name, str(job.id),
        phone=job.customer_phone, address=job.address,
    )
    create_folder(token, path)
    link = ensure_shared_link(token, path)
    details = dict(job.details or {})
    details["dropbox"] = {"folder": path, "link": link}
    job.details = details
    return link


# ── Phase 1c: the job's Dropbox folder IS the photo store (upload / list / fetch / delete) ──

DBX_API = "https://api.dropboxapi.com/2"
DBX_CONTENT = "https://content.dropboxapi.com/2"
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif")


def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def job_folder_of(job) -> str | None:
    """The folder Phase 1b stashed on the job at booking, if any."""
    return ((job.details or {}).get("dropbox") or {}).get("folder") or None


def upload_into_folder(token: str, folder: str, filename: str, data: bytes) -> dict:
    """Put one photo in the job's folder. `autorename` so two `photo.jpg` never collide."""
    path = f"{folder.rstrip('/')}/{_safe(filename)}"
    _assert_under_root(path)
    import httpx
    resp = httpx.post(
        f"{DBX_CONTENT}/files/upload",
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": path, "mode": "add", "autorename": True, "mute": True}),
            "Content-Type": "application/octet-stream",
        },
        content=data, timeout=60,
    )
    if resp.status_code >= 400:
        raise DropboxGuardError(f"Dropbox upload {resp.status_code}: {resp.text[:200]}")
    j = resp.json()
    return {"path": j.get("path_lower") or path, "name": j.get("name") or _safe(filename)}


def list_folder_images(token: str, folder: str) -> list[dict]:
    """Every image in the job's folder — INCLUDING ones dropped straight into Dropbox (by the
    manager via the calendar link, or a customer's photos filed there). That is the whole point of
    making the folder the store rather than Postgres. Oldest first. A folder that doesn't exist yet
    is not an error — it simply has no photos."""
    _assert_under_root(folder)
    import httpx
    out: list[dict] = []
    cursor = None
    while True:
        if cursor:
            r = httpx.post(f"{DBX_API}/files/list_folder/continue",
                           headers=_hdr(token), json={"cursor": cursor}, timeout=30)
        else:
            r = httpx.post(f"{DBX_API}/files/list_folder",
                           headers=_hdr(token), json={"path": folder}, timeout=30)
        if r.status_code == 409:
            return []   # path/not_found — nothing filed yet
        if r.status_code >= 400:
            raise DropboxGuardError(f"Dropbox list_folder {r.status_code}: {r.text[:200]}")
        j = r.json()
        for e in j.get("entries", []):
            if e.get(".tag") == "file" and (e.get("name") or "").lower().endswith(_IMAGE_EXT):
                out.append({"path": e.get("path_lower"), "name": e.get("name"),
                            "size": e.get("size"), "modified": e.get("server_modified") or ""})
        if not j.get("has_more"):
            break
        cursor = j.get("cursor")
    out.sort(key=lambda x: x.get("modified") or "")
    return out


def fetch_file(token: str, path: str, *, thumb: bool = False) -> tuple[bytes, str]:
    """Bytes for one file under the root. `thumb` asks Dropbox for a small JPEG — the Day-Board
    strip renders 96px tiles, so there's no reason to move full-size photos for it."""
    _assert_under_root(path)
    import httpx
    if thumb:
        arg = {"resource": {".tag": "path", "path": path}, "format": {".tag": "jpeg"},
               "size": {".tag": "w640h480"}, "mode": {".tag": "strict"}}
        r = httpx.post(f"{DBX_CONTENT}/files/get_thumbnail_v2",
                       headers={"Authorization": f"Bearer {token}", "Dropbox-API-Arg": json.dumps(arg)},
                       timeout=60)
        if r.status_code < 400:
            return r.content, "image/jpeg"
        # not thumbnailable (odd format / too large) -> fall through and serve the original
    r = httpx.post(f"{DBX_CONTENT}/files/download",
                   headers={"Authorization": f"Bearer {token}", "Dropbox-API-Arg": json.dumps({"path": path})},
                   timeout=60)
    if r.status_code >= 400:
        raise DropboxGuardError(f"Dropbox download {r.status_code}: {r.text[:200]}")
    ct = (r.headers.get("content-type") or "").split(";")[0].strip()
    return r.content, (ct if ct.startswith("image/") else "image/jpeg")


def delete_path(token: str, path: str) -> None:
    """Remove one file under the root (a wrong photo got filed). 409 = already gone."""
    _assert_under_root(path)
    import httpx
    r = httpx.post(f"{DBX_API}/files/delete_v2", headers=_hdr(token), json={"path": path}, timeout=30)
    if r.status_code >= 400 and r.status_code != 409:
        raise DropboxGuardError(f"Dropbox delete {r.status_code}: {r.text[:200]}")
