import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import UPLOADS_DIR
from ..database import get_db

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("", response_model=list[schemas.UploadedFileOut])
def list_files(agent_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.UploadedFile)
    if agent_id is not None:
        query = query.filter(models.UploadedFile.agent_id == agent_id)
    return query.order_by(models.UploadedFile.uploaded_at.desc()).all()


@router.post("", response_model=schemas.UploadedFileOut)
def upload_file(
    agent_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Eigene Dateien hochladen und optional einem Agenten zuordnen.
    Dateien werden lokal auf der Festplatte gespeichert, nicht in der Cloud."""
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest_path: Path = UPLOADS_DIR / safe_name

    with dest_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    record = models.UploadedFile(
        filename=file.filename,
        stored_path=str(dest_path),
        content_type=file.content_type,
        agent_id=agent_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import FileResponse

    record = db.get(models.UploadedFile, file_id)
    if not record:
        raise HTTPException(404, "Datei nicht gefunden")
    return FileResponse(
        record.stored_path,
        media_type=record.content_type or "application/octet-stream",
        filename=record.filename,
    )
