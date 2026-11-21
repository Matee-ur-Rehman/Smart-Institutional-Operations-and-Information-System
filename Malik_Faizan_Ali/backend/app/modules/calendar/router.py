import re
import uuid
from calendar import monthrange
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.audience import audience_user_ids, audience_visibility_clause
from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import section_labels
from app.core.database import get_db
from app.core.errors import NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.calendar.models import Event
from app.modules.calendar.schemas import EventCreate, EventOut, EventUpdate
from app.modules.foundation.models import Section, User
from app.modules.notifications.service import notify_users

router = APIRouter(prefix="/events", tags=["Calendar & Events"])
admin_only = Depends(require_roles("admin"))
LABELS = {"all": "Everyone", "teachers": "Teachers", "students": "Students", "parents": "Parents"}


def _out(db: Session, rows: list[Event]) -> list[EventOut]:
    labels = section_labels(db, {e.section_id for e in rows if e.section_id})
    return [EventOut(id=e.id, title=e.title, description=e.description, event_type=e.event_type,
                     start_date=e.start_date, end_date=e.end_date, start_time=e.start_time, end_time=e.end_time,
                     location=e.location, audience=e.audience, section_id=e.section_id,
                     audience_label=labels.get(e.section_id, "Class") if e.audience == "class" else LABELS[e.audience],
                     created_by=e.created_by, created_at=e.created_at) for e in rows]


def _notify(db: Session, e: Event) -> None:
    when = e.start_date.strftime("%d %b %Y") + (f" – {e.end_date.strftime('%d %b %Y')}" if e.end_date != e.start_date else "")
    notify_users(db, audience_user_ids(db, e.audience, None, e.section_id), f"New event: {e.title}",
                 f"{when}" + (f" at {e.location}" if e.location else ""), "event", "event", e.id)


@router.post("", response_model=EventOut, status_code=201)
def create_event(body: EventCreate, user: User = admin_only, db: Session = Depends(get_db)):
    if body.audience == "class" and db.get(Section, body.section_id) is None:
        raise ValidationFailed(errors=[field_error("section_id", "Section does not exist")])
    e = Event(title=body.title.strip(), description=body.description, event_type=body.event_type,
              start_date=body.start_date, end_date=body.end_date or body.start_date, start_time=body.start_time,
              end_time=body.end_time, location=body.location, audience=body.audience,
              section_id=body.section_id if body.audience == "class" else None, created_by=user.id)
    db.add(e)
    db.flush()
    if body.notify:
        _notify(db, e)
    db.commit()
    return _out(db, [e])[0]


@router.get("", response_model=Page[EventOut])
def list_events(from_date: date | None = None, to_date: date | None = None,
                event_type: Literal["holiday", "exam", "meeting", "sports", "activity", "other"] | None = None,
                month: str | None = Query(None, description="YYYY-MM"), params: PageParams = Depends(page_params),
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if month:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValidationFailed(errors=[field_error("month", "Use the format YYYY-MM")])
        y, m = int(month[:4]), int(month[5:])
        from_date, to_date = date(y, m, 1), date(y, m, monthrange(y, m)[1])
    stmt = select(Event)
    if user.role != "admin":
        stmt = stmt.where(audience_visibility_clause(Event, user, db))
    if from_date:   # events overlapping the window
        stmt = stmt.where(Event.end_date >= from_date)
    if to_date:
        stmt = stmt.where(Event.start_date <= to_date)
    if event_type:
        stmt = stmt.where(Event.event_type == event_type)
    rows, total = paginate(db, stmt.order_by(Event.start_date, Event.start_time, Event.id), params)
    return Page(items=_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


def _get(db: Session, user: User, event_id: uuid.UUID) -> Event:
    stmt = select(Event).where(Event.id == event_id)
    if user.role != "admin":
        stmt = stmt.where(audience_visibility_clause(Event, user, db))
    e = db.scalar(stmt)
    if e is None:
        raise NotFound("Event not found")
    return e


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(db, [_get(db, user, event_id)])[0]


@router.patch("/{event_id}", response_model=EventOut)
def update_event(event_id: uuid.UUID, body: EventUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    e = _get(db, user, event_id)
    data = body.model_dump(exclude_unset=True)
    for k in ("title", "description", "event_type", "start_date", "end_date", "start_time", "end_time", "location"):
        if k in data and (data[k] is not None or k in ("description", "start_time", "end_time", "location")):
            setattr(e, k, data[k].strip() if k == "title" else data[k])
    if "audience" in data and data["audience"] is not None:
        e.audience = data["audience"]
    if "section_id" in data:
        e.section_id = data["section_id"]
    if e.audience != "class":
        e.section_id = None
    elif e.section_id is None or db.get(Section, e.section_id) is None:
        raise ValidationFailed(errors=[field_error("section_id", "A valid section is required for class events")])
    if e.end_date < e.start_date:
        raise ValidationFailed(errors=[field_error("end_date", "end_date cannot be before start_date")])
    if e.start_time and e.end_time and e.end_date == e.start_date and e.end_time <= e.start_time:
        raise ValidationFailed(errors=[field_error("end_time", "end_time must be after start_time")])
    db.commit()
    return _out(db, [e])[0]


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    db.delete(_get(db, user, event_id))
    db.commit()
