import uuid
from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

ExamType = Literal["monthly", "midterm", "final", "other"]
Money2 = Decimal


class ExamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    exam_type: ExamType
    academic_year_id: uuid.UUID | None = None
    start_date: date
    end_date: date
    status: Literal["draft", "scheduled"] = "draft"

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ExamUpdate(BaseModel):
    name: str | None = Field(None, min_length=3, max_length=100)
    exam_type: ExamType | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: Literal["draft", "scheduled", "ongoing", "completed"] | None = None


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    exam_type: str
    academic_year_id: uuid.UUID
    start_date: date
    end_date: date
    status: str
    schedule_count: int = 0


class ScheduleCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    exam_date: date
    start_time: time
    end_time: time
    room: str | None = Field(None, max_length=30)
    total_marks: Decimal = Field(gt=0, le=1000, decimal_places=2)
    passing_marks: Decimal = Field(ge=0, le=1000, decimal_places=2)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.passing_marks > self.total_marks:
            raise ValueError("passing_marks cannot exceed total_marks")
        return self


class ScheduleUpdate(BaseModel):
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(None, max_length=30)
    total_marks: Decimal | None = Field(None, gt=0, le=1000, decimal_places=2)
    passing_marks: Decimal | None = Field(None, ge=0, le=1000, decimal_places=2)


class ScheduleOut(BaseModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    exam_name: str
    section_id: uuid.UUID
    section_label: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    exam_date: date
    start_time: time
    end_time: time
    room: str | None = None
    total_marks: Decimal
    passing_marks: Decimal
    marks_entered: int | None = None
    student_count: int | None = None


class MarkEntry(BaseModel):
    student_id: uuid.UUID
    marks_obtained: Decimal | None = Field(None, decimal_places=2)
    is_absent: bool = False
    remarks: str | None = Field(None, max_length=200)


class MarksBulk(BaseModel):
    entries: list[MarkEntry] = Field(min_length=1, max_length=300)


class MarkSheetRow(BaseModel):
    student_id: uuid.UUID
    roll_no: str
    full_name: str
    marks_obtained: Decimal | None = None
    is_absent: bool = False
    remarks: str | None = None
    percentage: Decimal | None = None
    grade: str | None = None
    passed: bool | None = None


class MarkSheetOut(BaseModel):
    schedule: ScheduleOut
    exam_status: str
    locked: bool
    rows: list[MarkSheetRow]


class GradeBand(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    grade: str = Field(min_length=1, max_length=3)
    min_percentage: Decimal = Field(ge=0, le=100, decimal_places=2)
    max_percentage: Decimal = Field(ge=0, le=100, decimal_places=2)
    gpa_points: Decimal | None = Field(None, ge=0, le=9.99, decimal_places=2)
    remark: str = Field("", max_length=50)
    is_pass: bool = True

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.max_percentage < self.min_percentage:
            raise ValueError("max_percentage cannot be below min_percentage")
        return self


class GradeScaleBody(BaseModel):
    bands: list[GradeBand] = Field(min_length=2, max_length=15)
