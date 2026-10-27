import calendar as pycalendar
import uuid
from datetime import date, datetime, time
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.notifications.service import notify_users, users_for_audience
from app.modules.ops_common.core_refs import Section, User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import audience_condition, get_or_404, not_found
from app.modules.school_calendar.models import Event

router = APIRouter(prefix="/events", tags=["School Calendar & Events"])
EventType = Literal["holiday", "exam", "meeting", "sports", "activity", "other"]
Audience = Literal["all", "teachers", "students", "parents", "class"]


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    event_type: EventType
    start_date: date
    end_date: date | None = None  # defaults to start_date
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=150)
    audience: Audience = "all"
    section_id: uuid.UUID | None = None
    notify: bool = True

    @model_validator(mode="after")
    def _check(self):
        self.end_date = self.end_date or self.start_date
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.start_time and self.end_time and self.end_time <= self.start_time and self.end_date == self.start_date:
            raise ValueError("end_time must be after start_time")
        if self.audience == "class" and self.section_id is None:
            raise ValueError("section_id is required when audience is 'class'")
        if self.audience != "class" and self.section_id is not None:
            raise ValueError("section_id is only allowed when audience is 'class'")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    event_type: EventType | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(default=None, max_length=150)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    description: str | None
    event_type: str
    start_date: date
    end_date: date
    start_time: time | None
    end_time: time | None
    location: str | None
    audience: str
    section_id: uuid.UUID | None
    created_at: datetime


def _visible(db: Session, user: User, event_id: uuid.UUID) -> Event:
    stmt = select(Event).where(Event.id == event_id)
    condition = audience_condition(Event, user, db)
    if condition is not None:
        stmt = stmt.where(condition)
    event = db.scalar(stmt)
    if event is None:
        raise not_found("Event")
    return event


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    payload: EventCreate, background: BackgroundTasks, db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    if payload.section_id is not None:
        get_or_404(db, Section, payload.section_id, "Section")
    event = Event(**payload.model_dump(exclude={"notify"}), created_by=user.id)
    db.add(event)
    db.flush()
    if payload.notify:
        when = event.start_date.isoformat() if event.start_date == event.end_date else f"{event.start_date} to {event.end_date}"
        notify_users(
            db, users_for_audience(db, event.audience, section_id=event.section_id),
            title=f"New event: {event.title}", body=f"{event.event_type.title()} on {when}.",
            type="event", reference_type="event", reference_id=event.id,
        )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return event


@router.get("", response_model=Page[EventOut])
def list_events(
    from_date: date | None = None,
    to_date: date | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="YYYY-MM"),
    event_type: EventType | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if month:
        year, mon = int(month[:4]), int(month[5:])
        from_date = date(year, mon, 1)
        to_date = date(year, mon, pycalendar.monthrange(year, mon)[1])
    stmt = select(Event)
    condition = audience_condition(Event, user, db)
    if condition is not None:
        stmt = stmt.where(condition)
    if from_date:
        stmt = stmt.where(Event.end_date >= from_date)  # events overlapping the range
    if to_date:
        stmt = stmt.where(Event.start_date <= to_date)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    rows, total = paginate(db, stmt.order_by(Event.start_date, Event.start_time), params)
    return page_of(rows, total, params)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _visible(db, user, event_id)


@router.patch("/{event_id}", response_model=EventOut)
def update_event(
    event_id: uuid.UUID, payload: EventUpdate, db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    event = get_or_404(db, Event, event_id, "Event")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None and field in ("title", "event_type", "start_date", "end_date"):
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(event, field, value)
    if event.end_date < event.start_date:
        raise AppError(422, "validation_error", "end_date cannot be before start_date")
    if event.start_time and event.end_time and event.start_date == event.end_date and event.end_time <= event.start_time:
        raise AppError(422, "validation_error", "end_time must be after start_time")
    db.commit()
    return event


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    db.delete(get_or_404(db, Event, event_id, "Event"))
    db.commit()
