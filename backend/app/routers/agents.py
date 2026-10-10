from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(models.Agent).order_by(models.Agent.id).all()


@router.post("", response_model=schemas.AgentOut)
def create_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    """Neuen Agenten per freier Texteingabe anlegen - bewusst ohne Vorlagen,
    damit Name, Rolle und Kernaufgabe in normaler Sprache formuliert werden."""
    agent = models.Agent(
        name=payload.name,
        role_title=payload.role_title,
        core_task=payload.core_task,
        status=models.AgentStatus.DONE,
        is_active=True,
        is_builtin=False,
        color_accent="blue",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.patch("/{agent_id}", response_model=schemas.AgentOut)
def update_agent(
    agent_id: int, payload: schemas.AgentUpdate, db: Session = Depends(get_db)
):
    agent = db.get(models.Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent nicht gefunden")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = db.get(models.Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent nicht gefunden")
    if agent.is_builtin:
        raise HTTPException(400, "Fest eingerichtete Team-Agenten koennen nur pausiert, nicht geloescht werden")
    db.delete(agent)
    db.commit()
    return {"ok": True}
