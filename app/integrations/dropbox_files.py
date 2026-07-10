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
