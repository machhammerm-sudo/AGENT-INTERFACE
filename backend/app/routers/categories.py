from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..anthropic_client import classify_category
from ..database import get_db

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).order_by(models.Category.id).all()


@router.patch("/{category_id}", response_model=schemas.CategoryOut)
def update_category(
    category_id: int, payload: schemas.CategoryUpdate, db: Session = Depends(get_db)
):
    category = db.get(models.Category, category_id)
    if not category:
        raise HTTPException(404, "Kategorie nicht gefunden")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(category, field, value)
    if data:
        category.is_user_edited = True
    db.commit()
    db.refresh(category)
    return category


@router.post("/classify", response_model=schemas.ClassifyResponse)
def classify(payload: schemas.ClassifyRequest, db: Session = Depends(get_db)):
    """Guenstiger Hintergrund-Call, der einen Text einer der neun Kategorien
    zuordnet. Das Ergebnis ist ein Vorschlag und kann in der Oberflaeche
    jederzeit manuell korrigiert werden."""
    categories = db.query(models.Category).all()
    category_id = classify_category(payload.text, categories)
    category = db.get(models.Category, category_id) if category_id else None
    return schemas.ClassifyResponse(category=category)
