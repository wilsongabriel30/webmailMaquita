"""Pydantic schemas for Calendar module."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Calendar ──────────────────────────────────────────────
class CalendarCreate(BaseModel):
    name: str = "Calendario"
    color: str = "#0078d4"
    description: str = ""
    timezone: str = "America/Guayaquil"


class CalendarUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    description: Optional[str] = None
    timezone: Optional[str] = None


class CalendarOut(BaseModel):
    id: uuid.UUID
    name: str
    color: str
    description: str
    timezone: str
    is_default: bool


# ── Event ─────────────────────────────────────────────────
class EventCreate(BaseModel):
    calendar_id: uuid.UUID
    summary: str
    description: str = ""
    location: str = ""
    dtstart: datetime
    dtend: datetime
    all_day: bool = False
    rrule: str = ""
    timezone: str = "America/Guayaquil"
    reminders: list = Field(default_factory=list)
    attendees: list = Field(default_factory=list)


class EventUpdate(BaseModel):
    calendar_id: Optional[uuid.UUID] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    dtstart: Optional[datetime] = None
    dtend: Optional[datetime] = None
    all_day: Optional[bool] = None
    rrule: Optional[str] = None
    timezone: Optional[str] = None
    reminders: Optional[list] = None
    attendees: Optional[list] = None


class EventMove(BaseModel):
    dtstart: datetime
    dtend: datetime


class EventOut(BaseModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    uid: str
    summary: str
    description: str
    location: str
    dtstart: datetime
    dtend: datetime
    all_day: bool
    rrule: str
    status: str
    color: str
    calendar_name: str
    timezone: str
    reminders: list
    attendees: list


# ── Calendar Sharing ──────────────────────────────────────
class CalendarShareCreate(BaseModel):
    shared_with: str
    permission: str = "read"


class CalendarShareOut(BaseModel):
    id: uuid.UUID
    calendar_id: uuid.UUID
    calendar_name: str
    calendar_color: str
    owner_email: str
    shared_with: str
    permission: str
    created_at: datetime


# ── Event Invitation Response ─────────────────────────────
class EventInvitationResponse(BaseModel):
    status: str  # "accepted" | "declined" | "tentative"


# ── Free/Busy ─────────────────────────────────────────────
class FreeBusySlot(BaseModel):
    start: str
    end: str


class FreeBusyResponse(BaseModel):
    user: str
    slots: list[FreeBusySlot]
