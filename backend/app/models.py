import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


class AgentStatus(str, enum.Enum):
    WORKING = "working"
    WAITING_FOR_USER = "waiting_for_user"
    DONE = "done"
    PAUSED = "paused"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    role_title = Column(String, nullable=False)  # z.B. "Organisation & Kommunikation"
    core_task = Column(Text, nullable=False)  # freier Text, was der Agent tun soll
    status = Column(Enum(AgentStatus), default=AgentStatus.DONE, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_restricted = Column(Boolean, default=False, nullable=False)
    # restricted = darf keine kritischen Aktionen autonom auslösen (z.B. Sicherheits-Agentin)
    is_builtin = Column(Boolean, default=False, nullable=False)
    color_accent = Column(String, default="blue", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    messages = relationship(
        "Message", back_populates="agent", cascade="all, delete-orphan"
    )


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    role = Column(Enum(MessageRole), nullable=False)
    content = Column(Text, nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent", back_populates="messages")
    category = relationship("Category")


class AgendaItem(Base):
    __tablename__ = "agenda_items"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    reason = Column(Text, nullable=False)  # kurze Begruendung, warum wichtig
    is_blocking = Column(Boolean, default=False, nullable=False)
    is_done = Column(Boolean, default=False, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent")
    category = relationship("Category")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_user_edited = Column(Boolean, default=False, nullable=False)


class GoalLevel(str, enum.Enum):
    MONTH = "month"
    YEAR = "year"
    LONG_TERM = "long_term"  # 3-5-10 Jahre, eher Richtung als Zahl


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    MISSED = "missed"


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    level = Column(Enum(GoalLevel), nullable=False)
    title = Column(String, nullable=False)
    why_important = Column(Text, nullable=False)
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE, nullable=False)
    target_date = Column(String, nullable=True)  # freitext z.B. "2026-12" oder "in 5 Jahren"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Achievement(Base):
    """Rueckschau: was wurde mit dem Team erreicht, wie viel Zeit gespart."""

    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    time_saved_minutes = Column(Integer, default=0, nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    achieved_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    goal = relationship("Goal")


class ContactRequestStatus(str, enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class ContactRequest(Base):
    """Kontaktanfrage fuer komplexe, neue Agenten-Wuensche -> kein Self-Service,
    sondern eine Anfrage, die ein Beratungsgespraech mit dem Nutzer anstoesst."""

    __tablename__ = "contact_requests"

    id = Column(Integer, primary_key=True)
    description = Column(Text, nullable=False)
    contact_name = Column(String, nullable=True)
    contact_info = Column(String, nullable=True)
    status = Column(
        Enum(ContactRequestStatus), default=ContactRequestStatus.OPEN, nullable=False
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True)
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    content_type = Column(String, nullable=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    agent = relationship("Agent")
