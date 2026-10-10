from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..anthropic_client import classify_category
from ..database import get_db

router = APIRouter(prefix="/api/agenda", tags=["agenda"])


@router.get("", response_model=list[schemas.AgendaItemOut])
def list_agenda(db: Session = Depends(get_db)):
    """Weekly-Agenda: offene Punkte zuerst, blockierende ganz oben - als
    Priorisierungs-Empfehlung, nicht als Zwang."""
    items = (
        db.query(models.AgendaItem)
        .filter(models.AgendaItem.is_done == False)  # noqa: E712
        .order_by(models.AgendaItem.is_blocking.desc(), models.AgendaItem.created_at.desc())
        .all()
    )
    return items


@router.post("", response_model=schemas.AgendaItemOut)
def create_agenda_item(payload: schemas.AgendaItemCreate, db: Session = Depends(get_db)):
    category_id = payload.category_id
    if category_id is None:
        categories = db.query(models.Category).all()
        category_id = classify_category(f"{payload.title}\n{payload.reason}", categories)

    item = models.AgendaItem(
        title=payload.title,
        reason=payload.reason,
        is_blocking=payload.is_blocking,
        agent_id=payload.agent_id,
        category_id=category_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=schemas.AgendaItemOut)
def update_agenda_item(
    item_id: int, payload: schemas.AgendaItemUpdate, db: Session = Depends(get_db)
):
    item = db.get(models.AgendaItem, item_id)
    if not item:
        raise HTTPException(404, "Eintrag nicht gefunden")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item
