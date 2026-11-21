"""m1_core_enhancements: account security, refresh tokens, richer profiles

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_refresh_tokens_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])
    op.add_column("teachers", sa.Column("qualification", sa.String(length=150), nullable=True))
    op.add_column("teachers", sa.Column("joining_date", sa.Date(), nullable=True))
    op.add_column("students", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("students", sa.Column("gender", sa.String(length=10), nullable=True))
    op.add_column("students", sa.Column("admission_date", sa.Date(), nullable=True))
    op.add_column("students", sa.Column("address", sa.String(length=300), nullable=True))
    op.create_check_constraint(op.f("ck_students_gender"), "students", "gender IS NULL OR gender IN ('male', 'female', 'other')")
    op.add_column("parents", sa.Column("address", sa.String(length=300), nullable=True))
    op.add_column("parents", sa.Column("occupation", sa.String(length=100), nullable=True))
    op.create_unique_constraint(op.f("uq_classes_name"), "classes", ["name"])
    op.create_index("ix_students_section_id", "students", ["section_id"])


def downgrade() -> None:
    op.drop_index("ix_students_section_id", table_name="students")
    op.drop_constraint(op.f("uq_classes_name"), "classes", type_="unique")
    for c in ("occupation", "address"):
        op.drop_column("parents", c)
    op.drop_constraint(op.f("ck_students_gender"), "students", type_="check")
    for c in ("address", "admission_date", "gender", "date_of_birth"):
        op.drop_column("students", c)
    for c in ("joining_date", "qualification"):
        op.drop_column("teachers", c)
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    for c in ("must_change_password", "locked_until", "failed_login_count"):
        op.drop_column("users", c)
