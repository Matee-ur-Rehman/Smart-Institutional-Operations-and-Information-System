"""core_foundation  -- TEMPORARY STUB (Member 1 owns the real one)

Minimal shared-foundation tables so the operations modules run end-to-end. Member 1 replaces this
file with the real 0001_core_foundation (same revision id "0001") when it is merged.

Revision ID: 0001
Revises: 
Create Date: 2026-10-23 09:24:35.167568
"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('academic_years',
    sa.Column('name', sa.String(length=20), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('is_current', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_academic_years')),
    sa.UniqueConstraint('name', name=op.f('uq_academic_years_name'))
    )
    op.create_index('uq_academic_years_current', 'academic_years', ['is_current'], unique=True, postgresql_where=sa.text('is_current'))
    op.create_table('classes',
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.Column('grade_level', sa.SmallInteger(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_classes'))
    )
    op.create_table('subjects',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subjects')),
    sa.UniqueConstraint('code', name=op.f('uq_subjects_code'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('login_id', sa.String(length=50), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('admin', 'teacher', 'student', 'parent')", name=op.f('ck_users_role')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('login_id', name=op.f('uq_users_login_id'))
    )
    op.create_table('parents',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('cnic', sa.String(length=15), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_parents_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_parents')),
    sa.UniqueConstraint('user_id', name=op.f('uq_parents_user_id'))
    )
    op.create_table('teachers',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('employee_no', sa.String(length=30), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_teachers_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teachers')),
    sa.UniqueConstraint('employee_no', name=op.f('uq_teachers_employee_no')),
    sa.UniqueConstraint('user_id', name=op.f('uq_teachers_user_id'))
    )
    op.create_table('sections',
    sa.Column('class_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=10), nullable=False),
    sa.Column('class_teacher_id', sa.Uuid(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_sections_class_id_classes')),
    sa.ForeignKeyConstraint(['class_teacher_id'], ['teachers.id'], name=op.f('fk_sections_class_teacher_id_teachers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sections')),
    sa.UniqueConstraint('class_id', 'name', name=op.f('uq_sections_class_id'))
    )
    op.create_table('students',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('roll_no', sa.String(length=30), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_students_section_id_sections')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_students_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_students')),
    sa.UniqueConstraint('roll_no', name=op.f('uq_students_roll_no')),
    sa.UniqueConstraint('user_id', name=op.f('uq_students_user_id'))
    )
    op.create_table('teacher_assignments',
    sa.Column('teacher_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('subject_id', sa.Uuid(), nullable=False),
    sa.Column('academic_year_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], name=op.f('fk_teacher_assignments_academic_year_id_academic_years')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_teacher_assignments_section_id_sections')),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_teacher_assignments_subject_id_subjects')),
    sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('fk_teacher_assignments_teacher_id_teachers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teacher_assignments')),
    sa.UniqueConstraint('section_id', 'subject_id', 'academic_year_id', name=op.f('uq_teacher_assignments_section_id'))
    )
    op.create_table('student_parents',
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('parent_id', sa.Uuid(), nullable=False),
    sa.Column('relation', sa.String(length=20), nullable=True),
    sa.ForeignKeyConstraint(['parent_id'], ['parents.id'], name=op.f('fk_student_parents_parent_id_parents')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_student_parents_student_id_students')),
    sa.PrimaryKeyConstraint('student_id', 'parent_id', name=op.f('pk_student_parents'))
    )


def downgrade() -> None:
    op.drop_table('student_parents')
    op.drop_table('teacher_assignments')
    op.drop_table('students')
    op.drop_table('sections')
    op.drop_table('teachers')
    op.drop_table('parents')
    op.drop_table('users')
    op.drop_table('subjects')
    op.drop_table('classes')
    op.drop_index('uq_academic_years_current', table_name='academic_years', postgresql_where=sa.text('is_current'))
    op.drop_table('academic_years')
