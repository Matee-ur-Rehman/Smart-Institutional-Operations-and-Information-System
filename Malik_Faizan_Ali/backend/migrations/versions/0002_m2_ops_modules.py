"""m2_ops_modules

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-23 09:24:36.593859
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Human-readable document numbers (invoice / receipt / ticket) come from sequences,
    # so they are unique even under concurrent requests.
    for seq in ('invoice_no_seq', 'receipt_no_seq', 'ticket_no_seq'):
        op.execute(f'CREATE SEQUENCE {seq} START 1')
    op.create_table('fee_heads',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('frequency', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("frequency IN ('monthly', 'quarterly', 'yearly', 'one_time')", name=op.f('ck_fee_heads_frequency')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_heads')),
    sa.UniqueConstraint('name', name=op.f('uq_fee_heads_name'))
    )
    op.create_table('grade_scales',
    sa.Column('grade', sa.String(length=3), nullable=False),
    sa.Column('min_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('max_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('gpa_points', sa.Numeric(precision=3, scale=2), nullable=True),
    sa.Column('remark', sa.String(length=50), nullable=False),
    sa.Column('is_pass', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_grade_scales')),
    sa.UniqueConstraint('grade', name=op.f('uq_grade_scales_grade'))
    )
    op.create_table('period_definitions',
    sa.Column('period_no', sa.SmallInteger(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('is_break', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('label', sa.String(length=30), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_time > start_time', name=op.f('ck_period_definitions_times')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_period_definitions')),
    sa.UniqueConstraint('period_no', name=op.f('uq_period_definitions_period_no'))
    )
    op.create_table('device_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token', sa.String(length=500), nullable=False),
    sa.Column('platform', sa.String(length=10), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("platform IN ('android', 'web')", name=op.f('ck_device_tokens_platform')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_device_tokens_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_device_tokens')),
    sa.UniqueConstraint('token', name=op.f('uq_device_tokens_token'))
    )
    op.create_table('exams',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('exam_type', sa.String(length=20), nullable=False),
    sa.Column('academic_year_id', sa.Uuid(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=25), server_default='draft', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("exam_type IN ('monthly', 'midterm', 'final', 'other')", name=op.f('ck_exams_exam_type')),
    sa.CheckConstraint("status IN ('draft', 'scheduled', 'ongoing', 'completed', 'results_published')", name=op.f('ck_exams_status')),
    sa.CheckConstraint('end_date >= start_date', name=op.f('ck_exams_dates')),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], name=op.f('fk_exams_academic_year_id_academic_years')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_exams'))
    )
    op.create_table('fee_structures',
    sa.Column('class_id', sa.Uuid(), nullable=False),
    sa.Column('fee_head_id', sa.Uuid(), nullable=False),
    sa.Column('academic_year_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('amount > 0', name=op.f('ck_fee_structures_amount_positive')),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], name=op.f('fk_fee_structures_academic_year_id_academic_years')),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_fee_structures_class_id_classes')),
    sa.ForeignKeyConstraint(['fee_head_id'], ['fee_heads.id'], name=op.f('fk_fee_structures_fee_head_id_fee_heads')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_structures')),
    sa.UniqueConstraint('class_id', 'fee_head_id', 'academic_year_id', name=op.f('uq_fee_structures_class_id'))
    )
    op.create_table('notifications',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('reference_type', sa.String(length=30), nullable=True),
    sa.Column('reference_id', sa.Uuid(), nullable=True),
    sa.Column('is_read', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('push_status', sa.String(length=20), server_default='not_sent', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.CheckConstraint("push_status IN ('not_sent', 'queued', 'sent', 'failed', 'disabled')", name=op.f('ck_notifications_push_status')),
    sa.CheckConstraint("type IN ('announcement', 'homework', 'marks', 'fee', 'event', 'leave', 'attendance', 'complaint', 'system')", name=op.f('ck_notifications_type')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index('ix_notifications_user_created', 'notifications', ['user_id', 'created_at'], unique=False)
    op.create_table('announcements',
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('audience', sa.String(length=20), nullable=False),
    sa.Column('class_id', sa.Uuid(), nullable=True),
    sa.Column('section_id', sa.Uuid(), nullable=True),
    sa.Column('priority', sa.String(length=20), server_default='normal', nullable=False),
    sa.Column('publish_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
    sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("audience <> 'class' OR class_id IS NOT NULL OR section_id IS NOT NULL", name=op.f('ck_announcements_class_target')),
    sa.CheckConstraint("audience IN ('all', 'teachers', 'students', 'parents', 'class')", name=op.f('ck_announcements_audience')),
    sa.CheckConstraint("priority IN ('normal', 'important', 'urgent')", name=op.f('ck_announcements_priority')),
    sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name=op.f('ck_announcements_status')),
    sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_announcements_class_id_classes')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_announcements_created_by_users')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_announcements_section_id_sections')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_announcements'))
    )
    op.create_table('assignments',
    sa.Column('teacher_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('subject_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('assigned_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('max_marks', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('attachment_path', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='published', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('draft', 'published', 'closed')", name=op.f('ck_assignments_status')),
    sa.CheckConstraint('due_date >= assigned_date', name=op.f('ck_assignments_due_after_assigned')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_assignments_section_id_sections')),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_assignments_subject_id_subjects')),
    sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('fk_assignments_teacher_id_teachers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignments'))
    )
    op.create_index('ix_assignments_section_due', 'assignments', ['section_id', 'due_date'], unique=False)
    op.create_table('events',
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('end_time', sa.Time(), nullable=True),
    sa.Column('location', sa.String(length=150), nullable=True),
    sa.Column('audience', sa.String(length=20), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("audience <> 'class' OR section_id IS NOT NULL", name=op.f('ck_events_class_target')),
    sa.CheckConstraint("audience IN ('all', 'teachers', 'students', 'parents', 'class')", name=op.f('ck_events_audience')),
    sa.CheckConstraint("event_type IN ('holiday', 'exam', 'meeting', 'sports', 'activity', 'other')", name=op.f('ck_events_event_type')),
    sa.CheckConstraint('end_date >= start_date', name=op.f('ck_events_dates')),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_events_created_by_users')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_events_section_id_sections')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_events'))
    )
    op.create_table('exam_schedules',
    sa.Column('exam_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('subject_id', sa.Uuid(), nullable=False),
    sa.Column('exam_date', sa.Date(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.Column('room', sa.String(length=30), nullable=True),
    sa.Column('total_marks', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('passing_marks', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_time > start_time', name=op.f('ck_exam_schedules_times')),
    sa.CheckConstraint('passing_marks >= 0 AND passing_marks <= total_marks', name=op.f('ck_exam_schedules_passing_range')),
    sa.CheckConstraint('total_marks > 0', name=op.f('ck_exam_schedules_total_positive')),
    sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], name=op.f('fk_exam_schedules_exam_id_exams')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_exam_schedules_section_id_sections')),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_exam_schedules_subject_id_subjects')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_exam_schedules')),
    sa.UniqueConstraint('exam_id', 'section_id', 'subject_id', name=op.f('uq_exam_schedules_exam_id'))
    )
    op.create_table('timetable_slots',
    sa.Column('academic_year_id', sa.Uuid(), nullable=False),
    sa.Column('section_id', sa.Uuid(), nullable=False),
    sa.Column('subject_id', sa.Uuid(), nullable=False),
    sa.Column('teacher_id', sa.Uuid(), nullable=False),
    sa.Column('day_of_week', sa.SmallInteger(), nullable=False),
    sa.Column('period_id', sa.Uuid(), nullable=False),
    sa.Column('room', sa.String(length=30), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('day_of_week BETWEEN 1 AND 6', name=op.f('ck_timetable_slots_day')),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], name=op.f('fk_timetable_slots_academic_year_id_academic_years')),
    sa.ForeignKeyConstraint(['period_id'], ['period_definitions.id'], name=op.f('fk_timetable_slots_period_id_period_definitions')),
    sa.ForeignKeyConstraint(['section_id'], ['sections.id'], name=op.f('fk_timetable_slots_section_id_sections')),
    sa.ForeignKeyConstraint(['subject_id'], ['subjects.id'], name=op.f('fk_timetable_slots_subject_id_subjects')),
    sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('fk_timetable_slots_teacher_id_teachers')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_timetable_slots')),
    sa.UniqueConstraint('academic_year_id', 'section_id', 'day_of_week', 'period_id', name=op.f('uq_timetable_slots_academic_year_id'))
    )
    op.create_table('assignment_submissions',
    sa.Column('assignment_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('file_path', sa.String(length=500), nullable=True),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('marks_obtained', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['assignment_id'], ['assignments.id'], name=op.f('fk_assignment_submissions_assignment_id_assignments')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_assignment_submissions_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignment_submissions')),
    sa.UniqueConstraint('assignment_id', 'student_id', name=op.f('uq_assignment_submissions_assignment_id'))
    )
    op.create_table('complaints',
    sa.Column('ticket_no', sa.String(length=30), nullable=False),
    sa.Column('submitted_by', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=True),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=20), server_default='complaint', nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
    sa.Column('priority', sa.String(length=20), server_default='normal', nullable=False),
    sa.Column('assigned_to', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category IN ('academic', 'fee', 'teacher', 'facility', 'transport', 'other')", name=op.f('ck_complaints_category')),
    sa.CheckConstraint("kind IN ('complaint', 'feedback', 'suggestion')", name=op.f('ck_complaints_kind')),
    sa.CheckConstraint("priority IN ('low', 'normal', 'high')", name=op.f('ck_complaints_priority')),
    sa.CheckConstraint("status IN ('open', 'in_review', 'resolved', 'closed')", name=op.f('ck_complaints_status')),
    sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], name=op.f('fk_complaints_assigned_to_users')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_complaints_student_id_students')),
    sa.ForeignKeyConstraint(['submitted_by'], ['users.id'], name=op.f('fk_complaints_submitted_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_complaints')),
    sa.UniqueConstraint('ticket_no', name=op.f('uq_complaints_ticket_no'))
    )
    op.create_index('ix_complaints_submitter', 'complaints', ['submitted_by', 'created_at'], unique=False)
    op.create_table('fee_invoices',
    sa.Column('invoice_no', sa.String(length=30), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('academic_year_id', sa.Uuid(), nullable=False),
    sa.Column('period_label', sa.String(length=30), nullable=False),
    sa.Column('issue_date', sa.Date(), nullable=False),
    sa.Column('due_date', sa.Date(), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('paid_amount', sa.Numeric(precision=12, scale=2), server_default='0', nullable=False),
    sa.Column('status', sa.String(length=20), server_default='unpaid', nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('unpaid', 'partial', 'paid', 'overdue', 'cancelled')", name=op.f('ck_fee_invoices_status')),
    sa.CheckConstraint('discount_amount <= total_amount', name=op.f('ck_fee_invoices_discount_range')),
    sa.CheckConstraint('due_date >= issue_date', name=op.f('ck_fee_invoices_dates')),
    sa.CheckConstraint('total_amount >= 0 AND discount_amount >= 0 AND paid_amount >= 0', name=op.f('ck_fee_invoices_amounts')),
    sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id'], name=op.f('fk_fee_invoices_academic_year_id_academic_years')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_fee_invoices_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_invoices')),
    sa.UniqueConstraint('invoice_no', name=op.f('uq_fee_invoices_invoice_no'))
    )
    op.create_index('ix_fee_invoices_student_status', 'fee_invoices', ['student_id', 'status'], unique=False)
    op.create_table('marks',
    sa.Column('exam_schedule_id', sa.Uuid(), nullable=False),
    sa.Column('student_id', sa.Uuid(), nullable=False),
    sa.Column('marks_obtained', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('is_absent', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('remarks', sa.String(length=200), nullable=True),
    sa.Column('entered_by', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('marks_obtained IS NULL OR marks_obtained >= 0', name=op.f('ck_marks_non_negative')),
    sa.ForeignKeyConstraint(['entered_by'], ['users.id'], name=op.f('fk_marks_entered_by_users')),
    sa.ForeignKeyConstraint(['exam_schedule_id'], ['exam_schedules.id'], name=op.f('fk_marks_exam_schedule_id_exam_schedules')),
    sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_marks_student_id_students')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_marks')),
    sa.UniqueConstraint('exam_schedule_id', 'student_id', name=op.f('uq_marks_exam_schedule_id'))
    )
    op.create_table('complaint_comments',
    sa.Column('complaint_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('is_internal', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], name=op.f('fk_complaint_comments_author_id_users')),
    sa.ForeignKeyConstraint(['complaint_id'], ['complaints.id'], name=op.f('fk_complaint_comments_complaint_id_complaints'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_complaint_comments'))
    )
    op.create_table('fee_invoice_items',
    sa.Column('invoice_id', sa.Uuid(), nullable=False),
    sa.Column('fee_head_id', sa.Uuid(), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.ForeignKeyConstraint(['fee_head_id'], ['fee_heads.id'], name=op.f('fk_fee_invoice_items_fee_head_id_fee_heads')),
    sa.ForeignKeyConstraint(['invoice_id'], ['fee_invoices.id'], name=op.f('fk_fee_invoice_items_invoice_id_fee_invoices'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_invoice_items'))
    )
    op.create_table('fee_payments',
    sa.Column('receipt_no', sa.String(length=30), nullable=False),
    sa.Column('invoice_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('payment_date', sa.Date(), nullable=False),
    sa.Column('method', sa.String(length=20), nullable=False),
    sa.Column('reference', sa.String(length=100), nullable=True),
    sa.Column('recorded_by', sa.Uuid(), nullable=False),
    sa.Column('remarks', sa.Text(), nullable=True),
    sa.Column('is_reversal', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('reversal_of_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("method IN ('cash', 'bank_transfer', 'cheque', 'other')", name=op.f('ck_fee_payments_method')),
    sa.CheckConstraint('(is_reversal AND reversal_of_id IS NOT NULL) OR (NOT is_reversal AND reversal_of_id IS NULL)', name=op.f('ck_fee_payments_reversal_link')),
    sa.CheckConstraint('amount > 0', name=op.f('ck_fee_payments_amount_positive')),
    sa.ForeignKeyConstraint(['invoice_id'], ['fee_invoices.id'], name=op.f('fk_fee_payments_invoice_id_fee_invoices')),
    sa.ForeignKeyConstraint(['recorded_by'], ['users.id'], name=op.f('fk_fee_payments_recorded_by_users')),
    sa.ForeignKeyConstraint(['reversal_of_id'], ['fee_payments.id'], name=op.f('fk_fee_payments_reversal_of_id_fee_payments')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_payments')),
    sa.UniqueConstraint('receipt_no', name=op.f('uq_fee_payments_receipt_no')),
    sa.UniqueConstraint('reversal_of_id', name=op.f('uq_fee_payments_reversal_of_id'))
    )


def downgrade() -> None:
    op.drop_table('fee_payments')
    op.drop_table('fee_invoice_items')
    op.drop_table('complaint_comments')
    op.drop_table('marks')
    op.drop_index('ix_fee_invoices_student_status', table_name='fee_invoices')
    op.drop_table('fee_invoices')
    op.drop_index('ix_complaints_submitter', table_name='complaints')
    op.drop_table('complaints')
    op.drop_table('assignment_submissions')
    op.drop_table('timetable_slots')
    op.drop_table('exam_schedules')
    op.drop_table('events')
    op.drop_index('ix_assignments_section_due', table_name='assignments')
    op.drop_table('assignments')
    op.drop_table('announcements')
    op.drop_index('ix_notifications_user_created', table_name='notifications')
    op.drop_table('notifications')
    op.drop_table('fee_structures')
    op.drop_table('exams')
    op.drop_table('device_tokens')
    op.drop_table('period_definitions')
    op.drop_table('grade_scales')
    op.drop_table('fee_heads')
    for seq in ('invoice_no_seq', 'receipt_no_seq', 'ticket_no_seq'):
        op.execute(f'DROP SEQUENCE IF EXISTS {seq}')
