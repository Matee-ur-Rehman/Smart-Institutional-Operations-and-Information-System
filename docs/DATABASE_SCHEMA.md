# DATABASE_SCHEMA.md

**Status: PROPOSED — needs agreement from Faizan (Member 1) and Matee (Member 2) before either member writes migrations.**
Once both agree, change the status line to `AGREED` and record the date. After that, changing a shared table needs the other member's sign-off (see INTEGRATION_GUIDE.md).

Project: Trends High School Hassan Abdal — Smart Institutional Operations and Information System
Database: one PostgreSQL 16 database, shared by all modules.

---

## 1. Global conventions

| Topic | Rule |
|---|---|
| Primary keys | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` on every table (built in since PostgreSQL 13, no extension needed). No integer IDs. |
| Foreign keys | UUID, named `<entity>_id` (e.g. `student_id`, `class_id`). Always declared as real FK constraints. |
| Table names | `snake_case`, plural (`students`, `fee_invoices`). Junction tables `a_b` (`student_parents`). |
| Timestamps | `created_at TIMESTAMPTZ NOT NULL DEFAULT now()` and `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` on every mutable table. Stored in UTC; the apps display Asia/Karachi (UTC+5). |
| Dates | `DATE` for calendar dates (due dates, event dates). `TIME` for timetable periods. |
| Money | `NUMERIC(12,2)`, currency is PKR everywhere. Never `FLOAT`. |
| Enums | Stored as `VARCHAR` with a `CHECK` constraint (not native PG enums), so adding a value is a simple migration. |
| Soft delete | `is_active BOOLEAN NOT NULL DEFAULT TRUE` on users, students, teachers, classes, subjects. Records that other tables point to are deactivated, never hard-deleted. |
| Ownership | Each table has exactly one owner module (and one owner member). Others read it and may reference it with a FK, but never write to it directly. They call the owner's service function or API. |

### Roles (fixed list, used in `users.role` and in JWT)

`admin`, `teacher`, `student`, `parent`

---

## 2. Tables owned by Member 1 (Faizan) — the shared foundation

These are the **minimum required columns**. Faizan may add columns freely. Renaming or removing a column, or changing a type, needs Matee's sign-off because Member 2's tables and queries depend on them.

### users
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| email | VARCHAR(255) UNIQUE NULL | login identifier; may be null for students who log in by `login_id` |
| login_id | VARCHAR(50) UNIQUE NOT NULL | username / roll no / employee no |
| password_hash | VARCHAR(255) NOT NULL | bcrypt |
| role | VARCHAR(20) NOT NULL | CHECK in (`admin`,`teacher`,`student`,`parent`) |
| full_name | VARCHAR(150) NOT NULL | |
| phone | VARCHAR(20) NULL | |
| is_active | BOOLEAN NOT NULL DEFAULT TRUE | |
| last_login_at | TIMESTAMPTZ NULL | |
| created_at, updated_at | TIMESTAMPTZ | |

### academic_years
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(20) UNIQUE NOT NULL | e.g. `2026-2027` |
| start_date, end_date | DATE NOT NULL | |
| is_current | BOOLEAN NOT NULL DEFAULT FALSE | exactly one row TRUE (partial unique index) |

### classes
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(50) NOT NULL | e.g. `Class 8`, `Nursery` |
| grade_level | SMALLINT NOT NULL | ordering, e.g. Nursery = 0, Class 1 = 1 … Class 10 = 10 |
| is_active | BOOLEAN | |

### sections
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| class_id | UUID FK → classes.id NOT NULL | |
| name | VARCHAR(10) NOT NULL | `A`, `B` … ; UNIQUE (class_id, name) |
| class_teacher_id | UUID FK → teachers.id NULL | |
| is_active | BOOLEAN | |

### subjects
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(100) NOT NULL | |
| code | VARCHAR(20) UNIQUE NOT NULL | |
| is_active | BOOLEAN | |

### teachers
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id UNIQUE NOT NULL | |
| employee_no | VARCHAR(30) UNIQUE NOT NULL | |
| is_active | BOOLEAN | |

### students
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id UNIQUE NULL | student login account (NULL if the student has no login) |
| roll_no | VARCHAR(30) UNIQUE NOT NULL | |
| full_name | VARCHAR(150) NOT NULL | |
| section_id | UUID FK → sections.id NOT NULL | current section; class is reached via section |
| is_active | BOOLEAN | |

### parents
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK → users.id UNIQUE NOT NULL | |
| cnic | VARCHAR(15) NULL | optional |

### student_parents (parent–child link)
| Column | Type | Notes |
|---|---|---|
| student_id | UUID FK → students.id | |
| parent_id | UUID FK → parents.id | |
| relation | VARCHAR(20) | `father`, `mother`, `guardian` |
| PRIMARY KEY (student_id, parent_id) | | |

### teacher_assignments (who teaches what to whom)
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| teacher_id | UUID FK → teachers.id NOT NULL | |
| section_id | UUID FK → sections.id NOT NULL | |
| subject_id | UUID FK → subjects.id NOT NULL | |
| academic_year_id | UUID FK → academic_years.id NOT NULL | |
| UNIQUE (section_id, subject_id, academic_year_id) | | one teacher per subject per section per year |

**This table is the authority for "may this teacher touch this section/subject".** All of Member 2's teacher permission checks (homework, marks, timetable) read it.

### attendance, leave_requests
Owned by Member 1 and not referenced by Member 2's tables. Member 1 documents their columns in their own section of this file.

---

## 3. Tables owned by Member 2 (Matee)

### Module: Homework & Assignments
**assignments**
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| teacher_id | UUID FK → teachers.id NOT NULL | creator |
| section_id | UUID FK → sections.id NOT NULL | |
| subject_id | UUID FK → subjects.id NOT NULL | |
| title | VARCHAR(200) NOT NULL | |
| description | TEXT NULL | |
| assigned_date | DATE NOT NULL DEFAULT CURRENT_DATE | |
| due_date | DATE NOT NULL | CHECK (due_date >= assigned_date) |
| max_marks | NUMERIC(6,2) NULL | |
| attachment_path | VARCHAR(500) NULL | relative path under `UPLOAD_DIR` |
| status | VARCHAR(20) NOT NULL DEFAULT `published` | CHECK in (`draft`,`published`,`closed`) |

**assignment_submissions** — table is created now but **disabled**: no student endpoints exist yet (decision 2026-10-21). Columns: `id, assignment_id FK, student_id FK, submitted_at, file_path, remarks, marks_obtained, UNIQUE(assignment_id, student_id)`.

### Module: Exams, Marks & Results
**grade_scales** — one row per grade band: `id, grade VARCHAR(3), min_percentage NUMERIC(5,2), max_percentage NUMERIC(5,2), gpa_points NUMERIC(3,2) NULL, remark VARCHAR(50), is_pass BOOLEAN`.
**exams**: `id, name VARCHAR(100), exam_type VARCHAR(20) CHECK in (monthly, midterm, final, other), academic_year_id FK, start_date, end_date, status CHECK in (draft, scheduled, ongoing, completed, results_published)`.
**exam_schedules**: `id, exam_id FK, section_id FK, subject_id FK, exam_date DATE, start_time TIME, end_time TIME, room VARCHAR(30) NULL, total_marks NUMERIC(6,2) NOT NULL, passing_marks NUMERIC(6,2) NOT NULL, UNIQUE (exam_id, section_id, subject_id)`.
**marks**: `id, exam_schedule_id FK, student_id FK, marks_obtained NUMERIC(6,2) NULL, is_absent BOOLEAN DEFAULT FALSE, remarks VARCHAR(200) NULL, entered_by UUID FK → users.id, UNIQUE (exam_schedule_id, student_id)`. CHECK `marks_obtained >= 0`; the API also rejects marks above `total_marks`.
**Results are computed, not stored**, from `marks` + `exam_schedules` + `grade_scales`, and only visible to students/parents when `exams.status = results_published`.

### Module: Fees
**fee_heads**: `id, name VARCHAR(100) UNIQUE, frequency CHECK in (monthly, quarterly, yearly, one_time), is_active`.
**fee_structures**: `id, class_id FK, fee_head_id FK, academic_year_id FK, amount NUMERIC(12,2) CHECK > 0, UNIQUE (class_id, fee_head_id, academic_year_id)`.
**fee_invoices**: `id, invoice_no VARCHAR(30) UNIQUE, student_id FK, academic_year_id FK, period_label VARCHAR(30) (e.g. "October 2026"), issue_date DATE, due_date DATE, total_amount NUMERIC(12,2), discount_amount NUMERIC(12,2) DEFAULT 0, paid_amount NUMERIC(12,2) DEFAULT 0, status CHECK in (unpaid, partial, paid, overdue, cancelled)`.
**fee_invoice_items**: `id, invoice_id FK, fee_head_id FK, description, amount NUMERIC(12,2)`.
**fee_payments**: `id, receipt_no VARCHAR(30) UNIQUE, invoice_id FK, amount NUMERIC(12,2) CHECK > 0, payment_date DATE, method CHECK in (cash, bank_transfer, cheque, other), reference VARCHAR(100) NULL, recorded_by UUID FK → users.id, remarks`.
Invoice `paid_amount` and `status` are updated in the same transaction as each payment. Payments are never edited or deleted. A mistake is corrected by a reversing record (see API_CONTRACT).

### Module: Timetable
**period_definitions**: `id, period_no SMALLINT UNIQUE, start_time TIME, end_time TIME, is_break BOOLEAN DEFAULT FALSE, label VARCHAR(30)`.
**timetable_slots**: `id, academic_year_id FK, section_id FK, subject_id FK, teacher_id FK, day_of_week SMALLINT CHECK 1..6 (1 = Monday … 6 = Saturday), period_id FK → period_definitions.id, room VARCHAR(30) NULL, UNIQUE (academic_year_id, section_id, day_of_week, period_id)`. The API also rejects a teacher being in two sections in the same period (conflict check).

### Module: Calendar & Events
**events**: `id, title VARCHAR(200), description, event_type CHECK in (holiday, exam, meeting, sports, activity, other), start_date DATE, end_date DATE (>= start_date), start_time TIME NULL, end_time TIME NULL, location VARCHAR(150) NULL, audience VARCHAR(20) CHECK in (all, teachers, students, parents, class), section_id FK NULL, created_by FK → users.id`.

### Module: Announcements & Notifications
**announcements**: `id, title VARCHAR(200), body TEXT, audience VARCHAR(20) CHECK in (all, teachers, students, parents, class), class_id FK NULL, section_id FK NULL, priority CHECK in (normal, important, urgent), publish_at TIMESTAMPTZ, expires_at TIMESTAMPTZ NULL, created_by FK → users.id, status CHECK in (draft, published, archived)`.
**notifications** (one row per recipient): `id, user_id FK → users.id, title, body, type VARCHAR(30) (announcement, homework, marks, fee, event, leave, attendance, complaint, system), reference_type VARCHAR(30) NULL, reference_id UUID NULL, is_read BOOLEAN DEFAULT FALSE, read_at TIMESTAMPTZ NULL, push_status CHECK in (not_sent, queued, sent, failed, disabled) DEFAULT not_sent, created_at`.
**device_tokens**: `id, user_id FK, token VARCHAR(500) UNIQUE, platform CHECK in (android, web), last_seen_at`. Stored now; used only when FCM is enabled.

### Module: Complaints & Feedback
**complaints**: `id, ticket_no VARCHAR(30) UNIQUE, submitted_by FK → users.id, student_id FK NULL, category CHECK in (academic, fee, teacher, facility, transport, other), kind CHECK in (complaint, feedback, suggestion), subject VARCHAR(200), description TEXT, status CHECK in (open, in_review, resolved, closed), priority CHECK in (low, normal, high), assigned_to FK → users.id NULL`.
**complaint_comments**: `id, complaint_id FK, author_id FK → users.id, message TEXT, is_internal BOOLEAN DEFAULT FALSE (hidden from the submitter)`.

---

## 4. Migrations (Alembic)

- One Alembic environment at `backend/migrations/`, one linear history.
- Member 1's first migration `0001_core_foundation` creates every table in section 2 and MUST be merged first. Member 2's migrations depend on it.
- File naming: `NNNN_<member>_<short_description>.py`, e.g. `0002_m2_homework_exams.py`.
- Before generating a migration: `git pull`, run `alembic heads`. There must be exactly one head. If two members create a migration at the same time and two heads appear, whoever pushes second runs `alembic merge -m "merge heads" <head1> <head2>`.
- Never edit a migration that has been pushed. Add a new one.

## 5. Seed data

- `backend/seeds/` has one script per member: `seed_core.py` (Member 1: admin, sample teachers/students/parents, classes, subjects) and `seed_ops.py` (Member 2: grade scale, fee heads, period definitions, sample homework/events). `seed_ops.py` needs `seed_core.py` to have run first.
- Seeds are idempotent (running twice creates no duplicates) and use obviously fake data. Seed passwords come from env vars, never hard-coded in production.

## 6. Open questions for agreement

1. Does `students.section_id` change when a student is promoted, or do we want a `student_enrollments` history table? Proposal: start with the simple column, add history later.
2. Should `users.login_id` be required for parents too? Proposal: yes (phone number is fine).
3. Faizan to confirm the exact column names in section 2 once his models exist.