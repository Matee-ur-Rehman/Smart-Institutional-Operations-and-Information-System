import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.ops_common.base import Money, NonNegativeMoney, PositiveMoney

Frequency = Literal["monthly", "quarterly", "yearly", "one_time"]
Method = Literal["cash", "bank_transfer", "cheque", "other"]


class FeeHeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    frequency: Frequency


class FeeHeadUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    frequency: Frequency | None = None
    is_active: bool | None = None


class FeeHeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    frequency: str
    is_active: bool


class FeeStructureCreate(BaseModel):
    class_id: uuid.UUID
    fee_head_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    amount: PositiveMoney


class FeeStructureUpdate(BaseModel):
    amount: PositiveMoney


class FeeStructureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    class_id: uuid.UUID
    fee_head_id: uuid.UUID
    academic_year_id: uuid.UUID
    amount: Money


class InvoiceItemIn(BaseModel):
    fee_head_id: uuid.UUID | None = None
    description: str = Field(min_length=2, max_length=200)
    amount: PositiveMoney


class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    period_label: str = Field(min_length=3, max_length=30)
    due_date: date
    academic_year_id: uuid.UUID | None = None
    # Omit items to build the invoice from the class fee structure (monthly heads).
    items: list[InvoiceItemIn] | None = Field(default=None, min_length=1, max_length=20)
    discount_amount: NonNegativeMoney = 0

    @field_validator("period_label")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class InvoiceGenerate(BaseModel):
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    period_label: str = Field(min_length=3, max_length=30)
    due_date: date
    academic_year_id: uuid.UUID | None = None
    fee_head_ids: list[uuid.UUID] | None = None  # default: every active MONTHLY head in the class structure

    @model_validator(mode="after")
    def _one_target(self):
        if (self.class_id is None) == (self.section_id is None):
            raise ValueError("provide exactly one of class_id or section_id")
        return self

    @field_validator("period_label")
    @classmethod
    def _strip(cls, value: str) -> str:
        return value.strip()


class PaymentCreate(BaseModel):
    amount: PositiveMoney
    payment_date: date
    method: Method
    reference: str | None = Field(default=None, max_length=100)
    remarks: str | None = Field(default=None, max_length=1000)

    @field_validator("payment_date")
    @classmethod
    def _not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("payment_date cannot be in the future")
        return value


class ReverseIn(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    fee_head_id: uuid.UUID | None
    description: str
    amount: Money


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    receipt_no: str
    invoice_id: uuid.UUID
    amount: Money
    payment_date: date
    method: str
    reference: str | None
    remarks: str | None
    is_reversal: bool
    reverses_payment_id: uuid.UUID | None
    created_at: datetime


class InvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_no: str
    student_id: uuid.UUID
    student_name: str | None = None
    roll_no: str | None = None
    section_name: str | None = None
    period_label: str
    issue_date: date
    due_date: date
    total_amount: Money
    discount_amount: Money
    net_amount: Money
    paid_amount: Money
    balance: Money
    status: str  # unpaid | partial | paid | overdue | cancelled  (overdue is derived)


class InvoiceDetailOut(InvoiceOut):
    items: list[ItemOut]
    payments: list[PaymentOut]


class GenerateResult(BaseModel):
    created: int
    skipped_existing: int
    skipped_no_fee_structure: int


class FeeSummaryOut(BaseModel):
    billed: Money
    collected: Money
    outstanding: Money
    overdue: Money
    invoice_count: int
