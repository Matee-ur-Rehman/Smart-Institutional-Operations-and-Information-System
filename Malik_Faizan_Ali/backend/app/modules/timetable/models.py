import uuid
from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Time, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk


class PeriodDefinition(UUIDPk, Timestamps, Base):
    __tablename__ = "period_definitions"
    __table_args__ = (CheckConstraint("end_time > start_time", name="times"),)

    period_no: Mapped[int] = mapped_column(SmallInteger, nullable=False, unique=True)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_break: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    label: Mapped[str] = mapped_column(String(30), nullable=False)


class TimetableSlot(UUIDPk, Timestamps, Base):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "section_id", "day_of_week", "period_id"),
        CheckConstraint("day_of_week BETWEEN 1 AND 6", name="day"),
    )

    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    period_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("period_definitions.id"), nullable=False)
    room: Mapped[str | None] = mapped_column(String(30))
