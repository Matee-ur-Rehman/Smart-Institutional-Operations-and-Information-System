import uuid
from datetime import date, datetime
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

LeaveType = Literal["sick", "family", "other"]
LStatus = Literal["pending", "approved", "rejected", "cancelled"]


class LeaveCreate(BaseModel):
    student_id: uuid.UUID
    from_date: date
    to_date: date
    leave_type: LeaveType = "other"
    reason: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.to_date < self.from_date:
            raise ValueError("to_date cannot be before from_date")
        return self


class DecisionBody(BaseModel):
    note: str | None = Field(None, max_length=500)


class LeaveOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID
    student_name: str | None = None
    roll_no: str | None = None
    section_id: uuid.UUID | None = None
    section_label: str | None = None
    applied_by_name: str | None = None
    from_date: date
    to_date: date
    days: int
    leave_type: str
    reason: str
    status: str
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    decision_note: str | None = None
    created_at: datetime
