import uuid
from datetime import time

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, SmallInteger, String, Time, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, uuid_pk


class PeriodDefinition(Base):
    __tablename__ = "period_definitions"
    __table_args__ = (CheckConstraint("end_time > start_time", name="ck_period_definitions_times"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    period_no: Mapped[int] = mapped_column(SmallInteger, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(30), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_break: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class TimetableSlot(TimestampMixin, Base):
    __tablename__ = "timetable_slots"
    __table_args__ = (
        UniqueConstraint("academic_year_id", "section_id", "day_of_week", "period_id"),
        CheckConstraint("day_of_week >= 1 AND day_of_week <= 6", name="ck_timetable_slots_day"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academic_years.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sections.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False)
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1 = Monday ... 6 = Saturday
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("period_definitions.id"), nullable=False)
    room: Mapped[str | None] = mapped_column(String(30))
