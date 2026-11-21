import uuid
from datetime import date, time

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

EVENT_TYPES = ("holiday", "exam", "meeting", "sports", "activity", "other")
EVENT_AUDIENCES = ("all", "teachers", "students", "parents", "class")


class Event(UUIDPk, Timestamps, Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(in_check("event_type", EVENT_TYPES), name="event_type"),
        CheckConstraint(in_check("audience", EVENT_AUDIENCES), name="audience"),
        CheckConstraint("end_date >= start_date", name="dates"),
        CheckConstraint("audience <> 'class' OR section_id IS NOT NULL", name="class_target"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(String(150))
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sections.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
