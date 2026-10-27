"""Core foundation tables (docs/DATABASE_SCHEMA.md section 2).

TEMPORARY STUB written by Member 2 (Matee) so his migrations can run before Faizan's merge.
Owner: Member 1 (Faizan). When Faizan's real `0001_core_foundation` lands, take HIS file and keep
this revision id so that 0002_m2_operations still chains onto it.

Tables are created from the model definitions with a frozen list of names, so this file stays
correct even if the stub models are later replaced.

Revision ID: 0001_core_foundation
Revises:
"""
from alembic import op

import app.db_models  # noqa: F401
from app.core.database import Base

revision = "0001_core_foundation"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "users", "academic_years", "classes", "subjects", "teachers", "sections",
    "students", "parents", "student_parents", "teacher_assignments",
]


def _tables():
    return [Base.metadata.tables[name] for name in TABLES]


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), tables=_tables())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind(), tables=_tables())
