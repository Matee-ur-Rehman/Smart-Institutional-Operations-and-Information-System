"""School-local time helpers (the school is in Pakistan, UTC+5; the DB stores UTC)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

SCHOOL_TZ = ZoneInfo("Asia/Karachi")


def school_now() -> datetime:
    return datetime.now(SCHOOL_TZ)


def school_today() -> date:
    return school_now().date()
