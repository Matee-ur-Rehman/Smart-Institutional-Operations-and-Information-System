"""Attendance calculations shared by routers (and later by the reports module)."""
from collections import Counter
from collections.abc import Iterable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.attendance.schemas import Summary
from app.modules.calendar.models import Event

LOW_ATTENDANCE_THRESHOLD = Decimal("75.00")


def summarize(statuses: Iterable[str]) -> Summary:
    c = Counter(statuses)
    present, absent, late, leave = c["present"], c["absent"], c["late"], c["leave"]
    counted = present + late + absent                  # approved-leave days do not count against the student
    pct = (Decimal(present + late) * 100 / counted).quantize(Decimal("0.01"), ROUND_HALF_UP) if counted else None
    return Summary(total_days=sum(c.values()), present=present, absent=absent, late=late, leave=leave, percentage=pct)


def is_holiday(db: Session, d: date, section_id) -> bool:
    """A holiday event for the whole school (or for this section's class target) covers the date."""
    stmt = select(Event.id).where(Event.event_type == "holiday", Event.start_date <= d, Event.end_date >= d,
                                  (Event.audience == "all") | ((Event.audience == "class") & (Event.section_id == section_id)))
    return db.scalar(stmt.limit(1)) is not None


def is_school_day(d: date) -> bool:
    return d.weekday() != 6                            # Monday-Saturday, Sunday is off
