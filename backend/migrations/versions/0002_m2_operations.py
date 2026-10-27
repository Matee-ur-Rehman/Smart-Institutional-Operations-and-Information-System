"""Member 2 tables: homework, exams, fees, timetable, calendar, announcements, notifications, complaints.

Tables are created from the model definitions with a frozen list of names (see 0001 for why).
`assignment_submissions` is created but unused: student homework submission is disabled.

Revision ID: 0002_m2_operations
Revises: 0001_core_foundation
"""
from alembic import op

import app.db_models  # noqa: F401
from app.core.database import Base

revision = "0002_m2_operations"
down_revision = "0001_core_foundation"
branch_labels = None
depends_on = None

TABLES = [
    # homework
    "assignments", "assignment_submissions",
    # exams / results
    "grade_scales", "exams", "exam_schedules", "marks",
    # fees
    "fee_heads", "fee_structures", "fee_invoices", "fee_invoice_items", "fee_payments",
    # timetable
    "period_definitions", "timetable_slots",
    # calendar, announcements, notifications
    "events", "announcements", "notifications", "device_tokens",
    # complaints
    "complaints", "complaint_comments",
]


def _tables():
    return [Base.metadata.tables[name] for name in TABLES]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_tables())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), tables=_tables())
