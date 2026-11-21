"""attendance and leave

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26 12:45:04.886830
"""
from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('attendance',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('attendance_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('remarks', sa.String(length=200), nullable=True),
    sa.Column('marked_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('present', 'absent', 'late', 'leave')", name=op.f('ck_attendance_status')),
    sa.ForeignKeyConstraint(['marked_by'], ['users.id'], name=op.f('fk_attendance_marked_by_users')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_attendance_section_id_sections')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_attendance_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attendance')),
    sa.UniqueConstraint('student_id', 'attendance_date', name='student_date')
    )
    op.create_index('ix_attendance_section_date', 'attendance', ['section_id', 'attendance_date'], unique=False)
    op.create_table('leave_requests',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('applied_by', sa.Uuid(), nullable=False),
    sa.Column('from_date', sa.Date(), nullable=False),
    sa.Column('to_date', sa.Date(), nullable=False),
    sa.Column('leave_type', sa.String(length=10), server_default='other', nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=10), server_default='pending', nullable=False),
    sa.Column('decided_by', sa.Uuid(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_note', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("leave_type IN ('sick', 'family', 'other')", name=op.f('ck_leave_requests_leave_type')),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name=op.f('ck_leave_requests_status')),
    sa.CheckConstraint('to_date >= from_date', name=op.f('ck_leave_requests_dates')),
    sa.ForeignKeyConstraint(['applied_by'], ['users.id'], name=op.f('fk_leave_requests_applied_by_users')),
    sa.ForeignKeyConstraint(['decided_by'], ['users.id'], name=op.f('fk_leave_requests_decided_by_users')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_leave_requests_student_id_students'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_leave_requests'))
    )
    op.create_index('ix_leave_student_dates', 'leave_requests', ['student_id', 'from_date', 'to_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_leave_student_dates', table_name='leave_requests')
    op.drop_table('leave_requests')
    op.drop_index('ix_attendance_section_date', table_name='attendance')
    op.drop_table('attendance')
