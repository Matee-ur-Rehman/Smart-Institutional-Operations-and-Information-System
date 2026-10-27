import uuid
from datetime import date, time

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, Time, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk

EVENT_TYPES = ["holiday", "exam", "meeting", "sports", "activity", "other"]
AUDIENCES = ["all", "teachers", "students", "parents", "class"]


class Event(TimestampMixin, Base):
    __tablename__ = "events"
    __table_args__ = (
        check_in("events", "event_type", EVENT_TYPES),
        check_in("events", "audience", AUDIENCES),
        CheckConstraint("end_date >= start_date", name="ck_events_dates"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(String(150))
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sections.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
