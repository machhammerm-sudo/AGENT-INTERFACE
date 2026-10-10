from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/goals", tags=["goals"])


@router.get("", response_model=list[schemas.GoalOut])
def list_goals(db: Session = Depends(get_db)):
    return db.query(models.Goal).order_by(models.Goal.level, models.Goal.created_at).all()


@router.post("", response_model=schemas.GoalOut)
def create_goal(payload: schemas.GoalCreate, db: Session = Depends(get_db)):
    goal = models.Goal(
        level=payload.level,
        title=payload.title,
        why_important=payload.why_important,
        target_date=payload.target_date,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.patch("/{goal_id}", response_model=schemas.GoalOut)
def update_goal(goal_id: int, payload: schemas.GoalUpdate, db: Session = Depends(get_db)):
    goal = db.get(models.Goal, goal_id)
    if not goal:
        raise HTTPException(404, "Ziel nicht gefunden")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    goal = db.get(models.Goal, goal_id)
    if not goal:
        raise HTTPException(404, "Ziel nicht gefunden")
    db.delete(goal)
    db.commit()
    return {"ok": True}
