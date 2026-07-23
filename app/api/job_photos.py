"""Job photos — attach reference photos to a Job and serve them back (the crew see them
on the Day Board stop detail, §8).

**Phase 1c: the job's DROPBOX FOLDER is the store.** New photos are filed into the folder Phase 1b
created at booking (the same folder the calendar event links to), and the listing reads that folder —
so photos the manager or a customer drops straight into Dropbox show up in-app as thumbnails too,
without any upload through the app.

Postgres `job_photo` rows are still served (and still written when a job has no Dropbox folder, or
Dropbox isn't connected), so nothing that already works breaks. Photos are addressed by an opaque
ref: a UUID = a legacy Postgres row, anything else = a base64url Dropbox path which is verified to sit
inside THIS job's folder before it is fetched.

Any signed-in employee may attach/view (the manager attaches at booking, the crew view on the job).
Brand-isolated: a crew member can only reach photos for jobs in their own brand (never-mix §15); the
owner (brand=None) can reach any.
"""
from __future__ import annotations

import base64
import binascii
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.integrations import dropbox_files, dropbox_oauth
from app.integrations.dropbox_files import decode_data_url
from app.models.employee import Employee
from app.models.job import Job
from app.models.job_photo import JobPhoto

router = APIRouter(tags=["job-photos"])
_log = logging.getLogger("job_photos")

MAX_BYTES = 6 * 1024 * 1024   # per photo AFTER the client compresses; guards against raw uploads
MAX_PER_JOB = 30
_CT = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


class PhotoIn(BaseModel):
    filename: str
    data_url: str      # data:image/...;base64,...  (client-compressed)


def _job_or_404(db: DbSession, job_id: str, emp: Employee) -> Job:
    try:
        jid = uuid.UUID(str(job_id))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    job = db.get(Job, jid)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    # never-mix: don't confirm or serve a cross-brand job to a brand-locked crew member.
    if not is_owner(emp) and job.brand != emp.brand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


def _ref(path: str) -> str:
    """Dropbox path -> opaque URL-safe ref (padding stripped so it stays clean in a URL)."""
    return base64.urlsafe_b64encode(path.encode("utf-8")).decode("ascii").rstrip("=")


def _unref(ref: str) -> str | None:
    try:
        return base64.urlsafe_b64decode(ref + "=" * (-len(ref) % 4)).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _token(db: DbSession) -> str | None:
    """A valid Dropbox access token, or None. NEVER raises: `get_valid_access_token` throws when a
    refresh fails (revoked link, bad app creds), and a Dropbox problem must degrade to the Postgres
    store / a clean 503 — it must never 500 the crew's photo strip on a live job."""
    try:
        return dropbox_oauth.get_valid_access_token(db)
    except Exception:
        return None


def _dbx(db: DbSession, job: Job) -> tuple[str | None, str | None]:
    """(access token, this job's folder) — either may be None, in which case Postgres is used."""
    folder = dropbox_files.job_folder_of(job)
    if not folder:
        return None, None
    return _token(db), folder


def _path_for_job(job: Job, ref: str) -> str:
    """Decode a ref and PROVE it lives inside this job's own folder — otherwise a valid session
    could read any file in the Dropbox root by crafting a ref."""
    folder = dropbox_files.job_folder_of(job)
    path = _unref(ref)
    if not folder or not path or not path.lower().startswith(folder.rstrip("/").lower() + "/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return path


def _db_row(p: JobPhoto, job_id: str) -> dict:
    url = f"/jobs/{job_id}/photos/{p.id}"
    return {"id": str(p.id), "filename": p.filename, "content_type": p.content_type,
            "uploaded_by": p.uploaded_by, "url": url, "thumb_url": url, "source": "app"}


@router.post("/jobs/{job_id}/photos")
def add_job_photo(job_id: str, body: PhotoIn, db: DbSession = Depends(get_db),
                  emp: Employee = Depends(get_current_employee)) -> dict:
    job = _job_or_404(db, job_id, emp)
    raw, ext = decode_data_url(body.data_url)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No image data")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo too large - compress it first")
    fn = (body.filename or f"photo.{ext}").strip()[:255] or f"photo.{ext}"

    token, folder = _dbx(db, job)
    if token and folder:
        try:
            if len(dropbox_files.list_folder_images(token, folder)) >= MAX_PER_JOB:
                raise HTTPException(status.HTTP_409_CONFLICT,
                                    f"Photo limit ({MAX_PER_JOB}) reached for this job")
            up = dropbox_files.upload_into_folder(token, folder, fn, raw)
            return {"id": _ref(up["path"]), "filename": up["name"], "source": "dropbox",
                    "url": f"/jobs/{job.id}/photos/{_ref(up['path'])}"}
        except HTTPException:
            raise
        except Exception:
            # Dropbox hiccup -> keep the photo in Postgres rather than lose it. LOG it: the fallback
            # is silent to the user, so without this a wrong API call just looks like "nothing changed".
            _log.warning("dropbox upload failed for job %s, storing in Postgres instead", job.id,
                         exc_info=True)

    count = db.scalar(select(func.count()).select_from(JobPhoto).where(JobPhoto.job_id == job.id)) or 0
    if count >= MAX_PER_JOB:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Photo limit ({MAX_PER_JOB}) reached for this job")
    photo = JobPhoto(job_id=job.id, filename=fn, content_type=_CT.get(ext, "image/jpeg"),
                     data=raw, uploaded_by=emp.name)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return _db_row(photo, str(job.id))


@router.get("/jobs/{job_id}/photos")
def list_job_photos(job_id: str, db: DbSession = Depends(get_db),
                    emp: Employee = Depends(get_current_employee)) -> dict:
    job = _job_or_404(db, job_id, emp)
    photos: list[dict] = []

    token, folder = _dbx(db, job)
    if token and folder:
        try:
            for f in dropbox_files.list_folder_images(token, folder):
                r = _ref(f["path"])
                photos.append({"id": r, "filename": f["name"], "content_type": "image/jpeg",
                               "uploaded_by": None, "source": "dropbox",
                               "url": f"/jobs/{job.id}/photos/{r}",
                               "thumb_url": f"/jobs/{job.id}/photos/{r}?thumb=1"})
        except Exception:
            # never let a Dropbox outage hide the legacy photos below — but say so in the log
            _log.warning("dropbox list failed for job %s, showing app-stored photos only", job.id,
                         exc_info=True)

    rows = db.scalars(
        select(JobPhoto).where(JobPhoto.job_id == job.id).order_by(JobPhoto.created_at)
    ).all()
    photos.extend(_db_row(p, str(job.id)) for p in rows)
    return {"photos": photos}


@router.get("/jobs/{job_id}/photos/{ref}")
def serve_job_photo(job_id: str, ref: str, thumb: int = 0, db: DbSession = Depends(get_db),
                    emp: Employee = Depends(get_current_employee)) -> Response:
    """Serve one photo. Brand-gated on the job in the path; a Dropbox ref must resolve inside that
    job's own folder. `?thumb=1` serves Dropbox's small JPEG (used by the Day-Board strip)."""
    job = _job_or_404(db, job_id, emp)
    try:                                   # a UUID ref = a legacy Postgres row
        pid = uuid.UUID(str(ref))
    except ValueError:
        pid = None
    if pid is not None:
        p = db.get(JobPhoto, pid)
        if p is None or p.job_id != job.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        return Response(content=p.data, media_type=p.content_type,
                        headers={"Cache-Control": "private, max-age=86400"})

    path = _path_for_job(job, ref)
    token = _token(db)
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dropbox is not connected")
    try:
        data, ct = dropbox_files.fetch_file(token, path, thumb=bool(thumb))
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return Response(content=data, media_type=ct, headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/jobs/{job_id}/photos/{ref}")
def delete_job_photo_ref(job_id: str, ref: str, db: DbSession = Depends(get_db),
                         emp: Employee = Depends(get_current_employee)) -> dict:
    """Remove a photo (manager or owner) — e.g. a wrong one got attached."""
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager or owner only")
    job = _job_or_404(db, job_id, emp)
    try:
        pid = uuid.UUID(str(ref))
    except ValueError:
        pid = None
    if pid is not None:
        p = db.get(JobPhoto, pid)
        if p is None or p.job_id != job.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        db.delete(p)
        db.commit()
        return {"deleted": True, "source": "app"}

    path = _path_for_job(job, ref)
    token = _token(db)
    if not token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Dropbox is not connected")
    dropbox_files.delete_path(token, path)
    return {"deleted": True, "source": "dropbox"}


# ── legacy routes: photos filed before Phase 1c still have /job-photos/<uuid> URLs in the wild ──

@router.get("/job-photos/{photo_id}")
def serve_job_photo_legacy(photo_id: str, db: DbSession = Depends(get_db),
                           emp: Employee = Depends(get_current_employee)) -> Response:
    try:
        pid = uuid.UUID(str(photo_id))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    p = db.get(JobPhoto, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    _job_or_404(db, str(p.job_id), emp)   # brand gate on the linked job
    return Response(content=p.data, media_type=p.content_type,
                    headers={"Cache-Control": "private, max-age=86400"})


@router.delete("/job-photos/{photo_id}")
def delete_job_photo_legacy(photo_id: str, db: DbSession = Depends(get_db),
                            emp: Employee = Depends(get_current_employee)) -> dict:
    if not (is_owner(emp) or "manager" in (emp.access or [])):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Manager or owner only")
    try:
        pid = uuid.UUID(str(photo_id))
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    p = db.get(JobPhoto, pid)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    _job_or_404(db, str(p.job_id), emp)   # brand gate on the linked job
    db.delete(p)
    db.commit()
    return {"deleted": True}
