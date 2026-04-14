"""Pydantic schemas for Tasks module (Microsoft To Do style)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# Board (kept for backward compat)
class BoardCreate(BaseModel):
    name: str
    color: str = "#0078d4"

class BoardUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None

class BoardOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    position: int
    created_at: datetime
    updated_at: datetime

# Board Members
class MemberAdd(BaseModel):
    user_email: str
    role: str = "member"

class MemberOut(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    user_email: str
    role: str
    invited_by: str
    joined_at: datetime

# List (legacy)
class ListCreate(BaseModel):
    name: str
    color: str = "#e0e0e0"

class ListUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    position: Optional[int] = None

class ListOut(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    position: int
    color: str
    list_type: str = "custom"
    icon: str = ""
    task_count: int = 0

# New: TaskList for To Do style
class TaskListCreate(BaseModel):
    name: str
    icon: str = ""

class TaskListUpdate(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None

# Card
class CardCreate(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[datetime] = None
    priority: str = "medium"
    labels: list[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    important: bool = False
    my_day: bool = False
    reminder: Optional[datetime] = None
    note: str = ""
    recurrence: Optional[str] = None  # daily, weekdays, weekly, monthly, yearly

class CardUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    labels: Optional[list[str]] = None
    completed: Optional[bool] = None
    position: Optional[int] = None
    assigned_to: Optional[str] = None
    important: Optional[bool] = None
    my_day: Optional[bool] = None
    reminder: Optional[datetime] = None
    note: Optional[str] = None
    recurrence: Optional[str] = None

class CardMove(BaseModel):
    list_id: uuid.UUID
    position: int

class CardOut(BaseModel):
    id: uuid.UUID
    list_id: uuid.UUID
    title: str
    description: str
    due_date: Optional[datetime]
    priority: str
    labels: list[str]
    completed: bool
    position: int
    assigned_to: Optional[str]
    created_by: str
    completed_by: Optional[str]
    completed_at: Optional[datetime]
    important: bool = False
    my_day: bool = False
    reminder: Optional[datetime] = None
    note: str = ""
    recurrence: Optional[str] = None  # daily, weekdays, weekly, monthly, yearly
    created_at: datetime
    updated_at: datetime

# Label
class LabelCreate(BaseModel):
    name: str
    color: str = "#0078d4"

class LabelOut(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    name: str
    color: str

# Activity
class ActivityOut(BaseModel):
    id: uuid.UUID
    board_id: uuid.UUID
    card_id: Optional[uuid.UUID]
    user_email: str
    action: str
    details: str
    created_at: datetime

# Full board (kanban view - kept for backward compat)
class ListFull(ListOut):
    cards: list[CardOut] = Field(default_factory=list)

class BoardFull(BoardOut):
    lists: list[ListFull] = Field(default_factory=list)
    labels: list[LabelOut] = Field(default_factory=list)
    members: list[MemberOut] = Field(default_factory=list)
