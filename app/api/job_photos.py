"""Job photos — attach reference photos to a Job and serve them back (the crew see them
on the Day Board stop detail, §8). In-app storage; the client downscales before upload.

Any signed-in employee may attach/view (the manager attaches at booking, the crew view on
the job). Brand-isolated: a crew member can only reach photos for jobs in their own brand
(never-mix §15); the owner (brand=None) can reach any.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.integrations.dropbox_files import decode_data_url
from app.models.employee import Employee
from app.models.job import Job
from app.models.job_photo import JobPhoto

router = APIRouter(tags=["job-photos"])

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


@router.post("/jobs/{job_id}/photos")
def add_job_photo(job_id: str, body: PhotoIn, db: DbSession = Depends(get_db),
                  emp: Employee = Depends(get_current_employee)) -> dict:
    job = _job_or_404(db, job_id, emp)
    raw, ext = decode_data_url(body.data_url)
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No image data")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Photo too large - compress it first")
    count = db.scalar(select(func.count()).select_from(JobPhoto).where(JobPhoto.job_id == job.id)) or 0
    if count >= MAX_PER_JOB:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Photo limit ({MAX_PER_JOB}) reached for this job")
    fn = (body.filename or f"photo.{ext}").strip()[:255] or f"photo.{ext}"
    photo = JobPhoto(job_id=job.id, filename=fn, content_type=_CT.get(ext, "image/jpeg"),
                     data=raw, uploaded_by=emp.name)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return {"id": str(photo.id), "filename": photo.filename, "url": f"/job-photos/{photo.id}"}


@router.get("/jobs/{job_id}/photos")
def list_job_photos(job_id: str, db: DbSession = Depends(get_db),
                    emp: Employee = Depends(get_current_employee)) -> dict:
    job = _job_or_404(db, job_id, emp)
    rows = db.scalars(
        select(JobPhoto).where(JobPhoto.job_id == job.id).order_by(JobPhoto.created_at)
    ).all()
    return {"photos": [{"id": str(p.id), "filename": p.filename, "content_type": p.content_type,
                        "uploaded_by": p.uploaded_by, "url": f"/job-photos/{p.id}"} for p in rows]}


@router.get("/job-photos/{photo_id}")
def serve_job_photo(photo_id: str, db: DbSession = Depends(get_db),
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
def delete_job_photo(photo_id: str, db: DbSession = Depends(get_db),
                     emp: Employee = Depends(get_current_employee)) -> dict:
    """Remove a photo (manager or owner) — e.g. a wrong one got attached."""
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
