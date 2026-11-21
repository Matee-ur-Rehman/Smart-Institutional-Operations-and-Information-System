import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

AStatus = Literal["present", "absent", "late", "leave"]


class AttendanceEntry(BaseModel):
    student_id: uuid.UUID
    status: AStatus
    remarks: str | None = Field(None, max_length=200)


class AttendanceBulk(BaseModel):
    entries: list[AttendanceEntry] = Field(min_length=1, max_length=300)


class SheetRow(BaseModel):
    student_id: uuid.UUID
    roll_no: str
    full_name: str
    status: str | None = None          # None = not marked yet
    remarks: str | None = None
    on_approved_leave: bool = False    # an approved leave request covers this date


class SheetOut(BaseModel):
    section_id: uuid.UUID
    section_label: str | None = None
    date: date
    editable: bool
    marked: int
    total: int
    counts: dict[str, int]
    rows: list[SheetRow]


class Summary(BaseModel):
    total_days: int
    present: int
    absent: int
    late: int
    leave: int
    percentage: Decimal | None = None  # (present+late) / (present+late+absent) * 100; leave days excluded


class RecordOut(BaseModel):
    date: date
    status: str
    remarks: str | None = None


class StudentAttendanceOut(BaseModel):
    student_id: uuid.UUID
    student_name: str
    roll_no: str
    section_label: str | None = None
    from_date: date
    to_date: date
    summary: Summary
    records: list[RecordOut]
