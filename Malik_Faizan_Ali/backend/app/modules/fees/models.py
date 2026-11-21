import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.timeutil import school_today
from app.core.database import Base, Timestamps, UUIDPk, in_check

FEE_FREQUENCIES = ("monthly", "quarterly", "yearly", "one_time")
INVOICE_STATUSES = ("unpaid", "partial", "paid", "overdue", "cancelled")
PAYMENT_METHODS = ("cash", "bank_transfer", "cheque", "other")


class FeeHead(UUIDPk, Timestamps, Base):
    __tablename__ = "fee_heads"
    __table_args__ = (CheckConstraint(in_check("frequency", FEE_FREQUENCIES), name="frequency"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class FeeStructure(UUIDPk, Timestamps, Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint("class_id", "fee_head_id", "academic_year_id"),
        CheckConstraint("amount > 0", name="amount_positive"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id"), nullable=False)
    fee_head_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_heads.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class FeeInvoice(UUIDPk, Timestamps, Base):
    __tablename__ = "fee_invoices"
    __table_args__ = (
        CheckConstraint(in_check("status", INVOICE_STATUSES), name="status"),
        CheckConstraint("total_amount >= 0 AND discount_amount >= 0 AND paid_amount >= 0", name="amounts"),
        CheckConstraint("discount_amount <= total_amount", name="discount_range"),
        CheckConstraint("due_date >= issue_date", name="dates"),
        Index("ix_fee_invoices_student_status", "student_id", "status"),
    )

    invoice_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(30), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, default=school_today)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid", server_default="unpaid")


class FeeInvoiceItem(UUIDPk, Base):
    __tablename__ = "fee_invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_invoices.id", ondelete="CASCADE"), nullable=False)
    fee_head_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_heads.id"), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class FeePayment(UUIDPk, Timestamps, Base):
    """Append-only. A mistake is corrected by a reversal row (is_reversal=true), never an edit/delete."""
    __tablename__ = "fee_payments"
    __table_args__ = (
        CheckConstraint(in_check("method", PAYMENT_METHODS), name="method"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("(is_reversal AND reversal_of_id IS NOT NULL) OR (NOT is_reversal AND reversal_of_id IS NULL)",
                        name="reversal_link"),
        UniqueConstraint("reversal_of_id"),
    )

    receipt_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("fee_invoices.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)
    # additive columns (Member 2) for the reversal workflow
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fee_payments.id"))
