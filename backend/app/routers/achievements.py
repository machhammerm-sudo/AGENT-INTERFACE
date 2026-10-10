from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/achievements", tags=["achievements"])


@router.get("", response_model=list[schemas.AchievementOut])
def list_achievements(db: Session = Depends(get_db)):
    """Rueckschau: was wurde mit dem Team bereits erreicht."""
    return db.query(models.Achievement).order_by(models.Achievement.achieved_at.desc()).all()


@router.get("/summary")
def achievements_summary(db: Session = Depends(get_db)):
    total_minutes = (
        db.query(func.coalesce(func.sum(models.Achievement.time_saved_minutes), 0)).scalar()
    )
    count = db.query(models.Achievement).count()
    return {
        "total_achievements": count,
        "total_time_saved_minutes": int(total_minutes),
        "total_time_saved_hours": round(int(total_minutes) / 60, 1),
    }


@router.post("", response_model=schemas.AchievementOut)
def create_achievement(payload: schemas.AchievementCreate, db: Session = Depends(get_db)):
    achievement = models.Achievement(**payload.model_dump())
    db.add(achievement)
    db.commit()
    db.refresh(achievement)
    return achievement
