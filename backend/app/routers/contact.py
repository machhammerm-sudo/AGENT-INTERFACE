from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/contact-requests", tags=["contact"])


@router.get("", response_model=list[schemas.ContactRequestOut])
def list_contact_requests(db: Session = Depends(get_db)):
    return db.query(models.ContactRequest).order_by(models.ContactRequest.created_at.desc()).all()


@router.post("", response_model=schemas.ContactRequestOut)
def create_contact_request(payload: schemas.ContactRequestCreate, db: Session = Depends(get_db)):
    """Fuer komplexere, neue Agenten-Wuensche: bewusst KEIN automatisierter
    Self-Service. Die Anfrage wird hier nur gespeichert und angezeigt, damit
    du selbst das Beratungsgespraech (inkl. Kostenabschaetzung) fuehren kannst."""
    request = models.ContactRequest(**payload.model_dump())
    db.add(request)
    db.commit()
    db.refresh(request)
    return request
