import uuid
from datetime import time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PeriodCreate(BaseModel):
    period_no: int = Field(ge=1, le=20)
    start_time: time
    end_time: time
    is_break: bool = False
    label: str = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def _t(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class PeriodUpdate(BaseModel):
    period_no: int | None = Field(None, ge=1, le=20)
    start_time: time | None = None
    end_time: time | None = None
    is_break: bool | None = None
    label: str | None = Field(None, min_length=1, max_length=30)


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    period_no: int
    start_time: time
    end_time: time
    is_break: bool
    label: str


class SlotCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    teacher_id: uuid.UUID | None = None
    day_of_week: int = Field(ge=1, le=6)
    period_id: uuid.UUID
    room: str | None = Field(None, max_length=30)


class SlotUpdate(BaseModel):
    subject_id: uuid.UUID | None = None
    teacher_id: uuid.UUID | None = None
    day_of_week: int | None = Field(None, ge=1, le=6)
    period_id: uuid.UUID | None = None
    room: str | None = Field(None, max_length=30)


class SlotOut(BaseModel):
    id: uuid.UUID
    section_id: uuid.UUID
    section_label: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    teacher_id: uuid.UUID
    teacher_name: str | None = None
    day_of_week: int
    period_id: uuid.UUID
    period_no: int
    start_time: time
    end_time: time
    room: str | None = None
