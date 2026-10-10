from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .models import AgentStatus, GoalLevel, GoalStatus, MessageRole, ContactRequestStatus


# ---------- Agents ----------


class AgentCreate(BaseModel):
    name: str
    role_title: str
    core_task: str


class AgentUpdate(BaseModel):
    is_active: Optional[bool] = None
    status: Optional[AgentStatus] = None
    core_task: Optional[str] = None
    role_title: Optional[str] = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role_title: str
    core_task: str
    status: AgentStatus
    is_active: bool
    is_restricted: bool
    is_builtin: bool
    color_accent: str
    created_at: datetime


# ---------- Messages / Chat ----------


class ChatRequest(BaseModel):
    message: str


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    role: MessageRole
    content: str
    category_id: Optional[int] = None
    created_at: datetime


class ChatResponse(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut


# ---------- Agenda ----------


class AgendaItemCreate(BaseModel):
    title: str
    reason: str
    is_blocking: bool = False
    agent_id: Optional[int] = None
    category_id: Optional[int] = None


class AgendaItemUpdate(BaseModel):
    is_done: Optional[bool] = None
    category_id: Optional[int] = None


class AgendaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    reason: str
    is_blocking: bool
    is_done: bool
    agent_id: Optional[int] = None
    category_id: Optional[int] = None
    created_at: datetime


# ---------- Categories ----------


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    is_user_edited: bool


class ClassifyRequest(BaseModel):
    text: str


class ClassifyResponse(BaseModel):
    category: Optional[CategoryOut]


# ---------- Goals ----------


class GoalCreate(BaseModel):
    level: GoalLevel
    title: str
    why_important: str
    target_date: Optional[str] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    why_important: Optional[str] = None
    status: Optional[GoalStatus] = None
    target_date: Optional[str] = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: GoalLevel
    title: str
    why_important: str
    status: GoalStatus
    target_date: Optional[str] = None
    created_at: datetime


# ---------- Achievements ----------


class AchievementCreate(BaseModel):
    title: str
    description: str
    time_saved_minutes: int = 0
    goal_id: Optional[int] = None


class AchievementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    time_saved_minutes: int
    goal_id: Optional[int] = None
    achieved_at: datetime


# ---------- Contact requests ----------


class ContactRequestCreate(BaseModel):
    description: str
    contact_name: Optional[str] = None
    contact_info: Optional[str] = None


class ContactRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str
    contact_name: Optional[str] = None
    contact_info: Optional[str] = None
    status: ContactRequestStatus
    created_at: datetime


# ---------- Files ----------


class UploadedFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: Optional[str] = None
    agent_id: Optional[int] = None
    uploaded_at: datetime
