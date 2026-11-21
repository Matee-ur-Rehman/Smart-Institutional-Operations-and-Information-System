import uuid
from datetime import date, datetime, time
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

EventType = Literal["holiday", "exam", "meeting", "sports", "activity", "other"]
EAudience = Literal["all", "teachers", "students", "parents", "class"]


class EventCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=3000)
    event_type: EventType = "other"
    start_date: date
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(None, max_length=150)
    audience: EAudience = "all"
    section_id: uuid.UUID | None = None
    notify: bool = True

    @model_validator(mode="after")
    def _check(self) -> Self:
        end = self.end_date or self.start_date
        if end < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        if self.audience == "class" and not self.section_id:
            raise ValueError("section_id is required when audience is 'class'")
        if self.start_time and self.end_time and end == self.start_date and self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=3000)
    event_type: EventType | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = Field(None, max_length=150)
    audience: EAudience | None = None
    section_id: uuid.UUID | None = None


class EventOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None = None
    event_type: str
    start_date: date
    end_date: date
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    audience: str
    section_id: uuid.UUID | None = None
    audience_label: str
    created_by: uuid.UUID
    created_at: datetime
