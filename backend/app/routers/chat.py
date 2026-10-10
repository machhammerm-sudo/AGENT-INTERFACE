from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..anthropic_client import send_chat_message
from ..config import RECENT_MESSAGES_WINDOW
from ..database import get_db

router = APIRouter(prefix="/api", tags=["chat"])


@router.get("/agents/{agent_id}/history", response_model=list[schemas.MessageOut])
def get_history(
    agent_id: int,
    q: str | None = Query(default=None, description="Freitext-Suche in der Historie"),
    limit: int = Query(default=50, le=500),
    db: Session = Depends(get_db),
):
    """Durchsuchbare Historie. Wird NUR bei gezieltem Aufruf (z.B. Suche)
    geladen - nie automatisch komplett bei jeder Chat-Anfrage mitgeschickt."""
    query = db.query(models.Message).filter(models.Message.agent_id == agent_id)
    if q:
        query = query.filter(models.Message.content.ilike(f"%{q}%"))
    return query.order_by(models.Message.created_at.desc()).limit(limit).all()[::-1]


@router.post("/agents/{agent_id}/chat", response_model=schemas.ChatResponse)
def chat_with_agent(
    agent_id: int, payload: schemas.ChatRequest, db: Session = Depends(get_db)
):
    agent = db.get(models.Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent nicht gefunden")
    if not agent.is_active:
        raise HTTPException(400, f"{agent.name} ist aktuell pausiert.")

    # Nur ein kurzes, aktuelles Gedaechtnis mitschicken - kein kompletter Verlauf.
    recent = (
        db.query(models.Message)
        .filter(models.Message.agent_id == agent_id)
        .order_by(models.Message.created_at.desc())
        .limit(RECENT_MESSAGES_WINDOW)
        .all()
    )
    recent.reverse()
    history = [{"role": m.role.value, "content": m.content} for m in recent]

    agent.status = models.AgentStatus.WORKING
    db.commit()

    user_msg = models.Message(
        agent_id=agent_id, role=models.MessageRole.USER, content=payload.message
    )
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    try:
        reply_text = send_chat_message(agent, history, payload.message)
    except Exception as exc:
        agent.status = models.AgentStatus.DONE
        db.commit()
        raise HTTPException(502, f"Anfrage an die KI ist fehlgeschlagen: {exc}")

    assistant_msg = models.Message(
        agent_id=agent_id,
        role=models.MessageRole.ASSISTANT,
        content=reply_text,
    )
    db.add(assistant_msg)

    # Einfache Heuristik fuer den Kurzstatus: endet die Antwort mit einer Frage
    # an den Nutzer, wartet der Agent auf eine Rueckmeldung - sonst gilt die
    # Anfrage als erledigt.
    agent.status = (
        models.AgentStatus.WAITING_FOR_USER
        if reply_text.strip().endswith("?")
        else models.AgentStatus.DONE
    )

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return schemas.ChatResponse(user_message=user_msg, assistant_message=assistant_msg)
