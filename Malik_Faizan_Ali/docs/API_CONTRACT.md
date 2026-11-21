# API_CONTRACT.md

**Status: PROPOSED — needs agreement from Matee (Member 1) and Malik (Member 2).**
Member 1 (foundation) endpoints are implemented in `backend/app/modules/foundation` and listed in section 2.

Base URL (local): `http://localhost:8000/api/v1`
Interactive docs: `http://localhost:8000/docs` (Swagger) and `/redoc`
Format: JSON over HTTPS in production. Request and response bodies are `application/json`, except file upload/download.

---

## 1. Conventions

**Naming:** URLs are lowercase, plural nouns, hyphenated (`/fee-invoices`). JSON fields are `snake_case`.
**IDs:** UUID strings.
**Dates:** `YYYY-MM-DD`. Date-times: ISO 8601 UTC, e.g. `2026-10-22T07:53:00Z`. Times: `HH:MM`.
**Money:** JSON number with two decimals, PKR.

**Pagination** (list endpoints): `?page=1&page_size=20` (max 100). Response:
```json
{ "items": [ ... ], "total": 134, "page": 1, "page_size": 20 }
```

**Errors** (all modules use the same shape):
```json
{ "detail": "Human readable message", "code": "machine_code", "errors": [ { "field": "due_date", "message": "..." } ] }
```
`errors` is only present for validation failures.

| HTTP | `code` | When |
|---|---|---|
| 400 | `bad_request` | Logically invalid request |
| 401 | `not_authenticated` / `token_expired` | Missing, invalid or expired token |
| 403 | `forbidden` | Authenticated but role or ownership does not allow it |
| 404 | `not_found` | Missing record. **Also returned when the record exists but the caller may not know it exists** (e.g. another family's child) |
| 409 | `conflict` | Duplicate or clashing record (e.g. teacher double-booked) |
| 422 | `validation_error` | Field validation failed |

---

## 2. Authentication (owned by Member 1)

### JWT
- Algorithm HS256, secret from env `JWT_SECRET_KEY` (never committed).
- **Access token:** 30 minutes. **Refresh token:** 7 days.
- Access token claims — **this is the contract both members rely on:**
```json
{ "sub": "<user uuid>", "role": "admin|teacher|student|parent", "type": "access", "iat": 0, "exp": 0 }
```
- Header on every protected request: `Authorization: Bearer <access_token>`
- Role is also re-checked against the database on each request (a deactivated user is rejected even if the token is valid).

### Auth endpoints (implemented)
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/login` | Body `{ "login_id", "password" }`. Header `X-Client-Platform: web` or `mobile` (required). Returns `{ access_token, refresh_token, token_type, user }` |
| POST | `/auth/refresh` | Body `{ refresh_token }` |
| POST | `/auth/logout` | Body `{refresh_token?}`: deletes that session; with no body, ends all sessions of the caller |
| GET | `/auth/me` | Current user |
| POST | `/auth/change-password` | `{current_password, new_password}` (min 8 chars, letter + digit). Ends all other sessions |
| PATCH | `/auth/me` | `{phone?, email?}` — own profile only |

**Security behaviour:** refresh tokens are rotated on every refresh and stored server-side (sha256). Re-using an already rotated token returns `401 token_reused` and ends every session of that user. 5 failed logins lock the account for 15 minutes (`429 too_many_attempts`); an admin can unlock. Access tokens already issued stay valid until they expire (max 30 min) after logout; deactivating a user takes effect immediately.

### Platform rule
| Role | `web` | `mobile` |
|---|---|---|
| admin | ✅ | ❌ |
| teacher | ✅ | ✅ |
| student | ❌ | ✅ |
| parent | ❌ | ✅ |

The login endpoint returns `403 forbidden` for a disallowed combination. **Honest limitation:** `X-Client-Platform` is declared by the client, so this rule is a product restriction and not a hard security boundary. The real protection is the role checks on every endpoint.

### Foundation endpoints (implemented — Member 1 modules)
All paths under `/api/v1`. "A" = admin, "T" = teacher, "auth" = any signed-in user.

| Method | Path | Roles | Notes |
|---|---|---|---|
| GET/POST | `/users` | A | List (`role,q,is_active`) / create **admin** accounts. Teacher, student, parent accounts are created via their profile endpoints |
| GET/PATCH | `/users/{id}` | A | PATCH `full_name,email,phone,is_active`. Cannot deactivate yourself or the last admin |
| POST | `/users/{id}/reset-password` | A | `{new_password?}`; omitted → temporary password returned once; user must change it at next login |
| POST | `/users/{id}/unlock` | A | Clears a login lock |
| GET/POST | `/teachers` | A | Create makes the login + teacher profile; returns `temporary_password` once if none supplied |
| GET/PATCH | `/teachers/{id}` | A (any), T (self) | Detail includes current-year `assignments` and `class_teacher_of` |
| GET/POST | `/students` | A all; T only students of sections they teach (GET) | filters `section_id,class_id,q,is_active` |
| GET | `/students/{id}` | auth (via `can_access_student`) | Parent phone numbers hidden from the student role |
| PATCH | `/students/{id}` | A | Includes section transfer and `is_active` |
| POST | `/students/{id}/login` | A | Create a login for a student created without one |
| POST/DELETE | `/students/{id}/parents[/{parent_id}]` | A | Parent–child links; access follows immediately |
| GET/POST | `/parents`, GET/PATCH `/parents/{id}` | A | CNIC format `12345-1234567-1`; `children` may be linked on create |
| GET | `/academic-years`, `/classes`, `/sections`, `/subjects` | auth | Reference data (`include_inactive` for classes/sections/subjects) |
| POST/PATCH | same four | A | `POST /academic-years/{id}/set-current` flips the single current year. Classes/sections with active students cannot be deactivated (409) |
| GET | `/teacher-assignments` | A, T | filters `teacher_id, section_id, academic_year_id` (defaults to the current year) |
| POST/PATCH/DELETE | `/teacher-assignments[/{id}]` | A | One teacher per subject per section per year (409 otherwise). This table is the authority for teacher permissions |

### Attendance (implemented)
| Method | Path | Roles | Purpose |
|---|---|---|---|
| GET | `/attendance/sections/{section_id}?date=` | admin, teacher (own sections) | Daily sheet: every active student with `status` (null = not marked), `on_approved_leave`, `editable` |
| PUT | `/attendance/sections/{section_id}?date=` | admin, teacher (own sections) | Bulk upsert `{entries:[{student_id,status,remarks?}]}`; status `present|absent|late|leave` |
| GET | `/attendance/sections/{section_id}/summary?from_date&to_date` | admin, teacher | Per-student summary, `low_attendance` flag (< 75%) |
| GET | `/attendance/overview?date=` | admin, teacher | Which sections have marked attendance for the day |
| GET | `/attendance/students/{student_id}?from_date&to_date` | admin, teacher (own section), parent (own child), student (self) | Records + summary |
| GET | `/attendance/me` | student | Own records + summary |

Rules: no future dates (`400 future_date`); Sundays are not school days (`400 not_school_day`); a `holiday` event for all / the section's class blocks marking (`400 holiday`); teachers may only change the last 7 days (`403`), admins any past date. Default range is the 1st of the month to today, max 366 days. **Percentage** = (present + late) / (present + late + absent) x 100; approved-leave days are excluded. Marking a student absent *today* notifies the linked parents (`type="attendance"`, once per change).

### Leave requests (implemented)
| Method | Path | Roles | Purpose |
|---|---|---|---|
| POST | `/leave-requests` | parent | Apply for a linked child: `{student_id, from_date, to_date, leave_type: sick|family|other, reason}` |
| GET | `/leave-requests?status&student_id&section_id&from_date&to_date` | admin (all), teacher (own sections), parent (own children) | Paginated list |
| GET | `/leave-requests/{id}` | same scope | Detail |
| POST | `/leave-requests/{id}/approve` | admin, teacher (own sections) | `{note?}`; absences inside the range become `leave` |
| POST | `/leave-requests/{id}/reject` | admin, teacher (own sections) | `{note}` required (min 3 chars) |
| POST | `/leave-requests/{id}/cancel` | parent (owner) | Only while `pending` |

Rules: max 30 days per request; may start at most 7 days in the past; overlapping pending/approved requests for the same child are `409 leave_overlap`; a decided request is `409 already_decided`. Parents apply (students do not, per the proposal). Staff + admins are notified on apply, parents on approve/reject (`type="leave"`).

### Reports (implemented, `/reports/...`)
All return a file download (`Content-Disposition: attachment`). PDFs are rendered with reportlab (school header, page footer). Authorization mirrors the JSON endpoints; an unauthorized caller gets `404`/`403` exactly as on those endpoints.

| Path | Roles | Output |
|---|---|---|
| `GET /reports/result-card/{student_id}?exam_id=` | admin; teacher (own section); parent (own child); student (self). Student/parent only after `results_published` | PDF result card (marks per subject, %, grade, position, pass/fail) |
| `GET /reports/results/sections/{section_id}?exam_id=&format=pdf\|csv` | admin, teacher (own section) | Class result sheet |
| `GET /reports/fee-receipt/{payment_id}` | admin, parent (own child; not cancelled) | PDF receipt (shows REVERSED banner for reversed payments) |
| `GET /reports/fee-statement/{student_id}` | admin, parent (own child) | PDF statement with totals |
| `GET /reports/timetable/{section_id}` | any role that may see the section | Landscape weekly timetable PDF |
| `GET /reports/attendance/students/{student_id}?from_date&to_date&format=pdf\|csv` | admin, teacher (own section), parent (own child), student (self) | Student attendance report |
| `GET /reports/attendance/sections/{section_id}?from_date&to_date&format=pdf\|csv` | admin, teacher (own section) | Class attendance report, low-attendance rows flagged |
| `GET /reports/students?section_id=` | admin | CSV of active students with parent names/phones |

CSV files are UTF-8 with BOM so Excel opens them correctly.

---

### Shared dependencies (Python) — Member 1 provides, Member 2 imports
In `backend/app/core/security.py`:
```python
get_current_user()                 # FastAPI dependency -> User (raises 401)
require_roles("admin", "teacher")  # dependency factory (raises 403)
```
In `backend/app/core/database.py`: `get_db()` session dependency and the declarative `Base`.
In `backend/app/core/access.py` (Member 1) — ownership helpers that Member 2 calls instead of re-implementing:
```python
teacher_id_for(user, db) -> UUID                       # teachers.id for a teacher user
teacher_teaches(db, teacher_id, section_id, subject_id) -> bool   # reads teacher_assignments
student_id_for(user, db) -> UUID                       # students.id for a student user
parent_child_ids(user, db) -> list[UUID]               # students linked via student_parents
can_access_student(user, student_id, db) -> bool       # admin: any; teacher: teaches their section; student: self; parent: linked child
```
Until Member 1 pushes these, Member 2 develops against a clearly marked temporary stub with the same signatures, which is removed when the real one lands.

---

## 3. Permission matrix for Member 2's modules

A = admin, T = teacher, S = student, P = parent. "own" = limited to their own records / children.

| Module | A | T | S | P |
|---|---|---|---|---|
| Homework | full | create/edit/delete **own** for sections+subjects they teach | view for own section | view for linked children |
| Homework submission by students | — disabled — | | | |
| Exams & schedules | full | view | view own section's schedule | view linked children's schedule |
| Marks entry | full | enter/edit for sections+subjects they teach, while exam not `results_published` | — | — |
| Results | full | view for sections they teach | own, after `results_published` | linked children, after `results_published` |
| Fee structures / invoices / payments | full (admin records payments) | — | — | view linked children's invoices & payment history only |
| Timetable | full | view own + section timetables | own section | linked children |
| Calendar & events | full | view | view | view (only events whose audience includes them) |
| Announcements | create/edit/publish/archive | view (audience-filtered) | view (audience-filtered) | view (audience-filtered) |
| Notifications | — | own inbox | own inbox | own inbox |
| Complaints & feedback | view all, assign, change status, comment | — | — | submit, view own tickets, reply |

Students do **not** see fees (the proposal gives fee status only to parents).

---

## 4. Member 2 endpoints

All paths are under `/api/v1` and all require a Bearer token unless stated.

### 4.1 Homework & Assignments
| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/assignments` | A, T | Body: `section_id, subject_id, title, description?, due_date, max_marks?, status?`. `due_date` must be ≥ today. Teachers: 403 unless they teach that section+subject |
| GET | `/assignments` | all | Filters: `section_id, subject_id, status, due_from, due_to, student_id` (parent). Results are auto-scoped to the caller |
| GET | `/assignments/{id}` | all (scoped) | |
| PATCH | `/assignments/{id}` | A, owner T | |
| DELETE | `/assignments/{id}` | A, owner T | |
| POST | `/assignments/{id}/attachment` | A, owner T | multipart upload, PDF/PNG/JPG/DOCX, max 5 MB |
| GET | `/assignments/{id}/attachment` | all (scoped) | file download |

Publishing an assignment creates notifications for the students and parents of that section.

### 4.2 Exams, Marks & Results
| Method | Path | Roles | Notes |
|---|---|---|---|
| POST / GET | `/exams` | A (create), all (list, status filter) | |
| GET / PATCH / DELETE | `/exams/{id}` | A (write) | Delete only while `draft` |
| POST | `/exams/{id}/schedules` | A | Create a paper for a section+subject |
| GET | `/exams/{id}/schedules` | all (scoped) | Filters `section_id, subject_id` |
| PATCH / DELETE | `/exam-schedules/{id}` | A | |
| GET | `/exam-schedules/{id}/marks` | A, T (teaches it) | Mark sheet for the section (includes students with no marks yet) |
| PUT | `/exam-schedules/{id}/marks` | A, T (teaches it) | Bulk upsert: `{ "entries": [ { "student_id", "marks_obtained", "is_absent", "remarks" } ] }`. Rejects marks > `total_marks` or < 0; rejects students not in that section; rejects when exam is `results_published` |
| POST | `/exams/{id}/publish-results` | A | Moves status to `results_published`, notifies students and parents |
| GET | `/grade-scales` / PUT `/grade-scales` | all (read) / A (write) | |
| GET | `/results/students/{student_id}` | A, T (teaches), S (self), P (child) | Query `exam_id` optional. Per subject: marks, total, percentage, grade, pass/fail; plus overall total, percentage, grade, position-in-section. Students and parents only receive published exams |
| GET | `/results/sections/{section_id}` | A, T | Query `exam_id` required. Class result summary |

### 4.3 Fees
| Method | Path | Roles | Notes |
|---|---|---|---|
| CRUD | `/fee-heads` | A | |
| CRUD | `/fee-structures` | A | Filter `class_id, academic_year_id` |
| POST | `/fee-invoices` | A | Single invoice for a student |
| POST | `/fee-invoices/generate` | A | Body `{ "section_id" or "class_id", "period_label", "due_date" }` generates invoices from the fee structure for all active students. Idempotent per student + period (skips existing, reports counts) |
| GET | `/fee-invoices` | A (all), P (linked children) | Filters `student_id, status, period_label, section_id, due_from, due_to` |
| GET | `/fee-invoices/{id}` | A, P (child) | Includes items and payments |
| POST | `/fee-invoices/{id}/payments` | A | Body `{ amount, payment_date, method, reference?, remarks? }`. Rejects amount ≤ 0 or > outstanding balance. Updates invoice `paid_amount` and `status` atomically. Generates `receipt_no` |
| POST | `/fee-payments/{id}/reverse` | A | Creates a reversal record with a mandatory reason (payments are never edited or deleted) |
| POST | `/fee-invoices/{id}/cancel` | A | Only if no payments |
| GET | `/fee-summary` | A | Totals: billed, collected, outstanding, overdue; filter by class/section/period |
| GET | `/students/{student_id}/fee-statement` | A, P (child) | JSON statement (see PDF section) |

Overdue status is evaluated when invoices are read (`due_date < today` and balance > 0), so it never depends on a scheduled job.

### 4.4 Timetable
| Method | Path | Roles | Notes |
|---|---|---|---|
| CRUD | `/period-definitions` | A (write), all (read) | |
| POST | `/timetable-slots` | A | 409 if the section's slot is taken, or the teacher is already teaching in another section in that period. 400 if the teacher doesn't teach that subject in that section (via `teacher_assignments`) |
| PATCH / DELETE | `/timetable-slots/{id}` | A | |
| GET | `/timetable/sections/{section_id}` | A, T, S (own), P (child) | Full week grid |
| GET | `/timetable/teachers/{teacher_id}` | A, T (self) | |
| GET | `/timetable/me` | T, S | Convenience: caller's own timetable |
| GET | `/timetable/students/{student_id}` | P (child), A | |

### 4.5 Calendar & Events
| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/events` | A | |
| GET | `/events` | all | Filters `from_date, to_date, event_type, month=YYYY-MM`; auto-filtered by audience |
| GET / PATCH / DELETE | `/events/{id}` | read: all (scoped); write: A | |

### 4.6 Announcements & Notifications
| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/announcements` | A | `status=published` creates notifications for the audience |
| GET | `/announcements` | all | Audience-filtered; only published, not expired. Admin can pass `status=` to see drafts/archived |
| GET / PATCH / DELETE | `/announcements/{id}` | A (write) | |
| POST | `/announcements/{id}/archive` | A | |
| GET | `/notifications` | all (own only) | Filters `is_read, type`; paginated |
| GET | `/notifications/unread-count` | all | `{ "count": 3 }` |
| POST | `/notifications/{id}/read` | owner | |
| POST | `/notifications/read-all` | owner | |
| POST | `/devices/register` | all | Body `{ token, platform }`. Stored always; used only when FCM is enabled |
| DELETE | `/devices/{token}` | owner | Call on logout |

### 4.7 Complaints & Feedback
| Method | Path | Roles | Notes |
|---|---|---|---|
| POST | `/complaints` | P | Body `{ student_id?, category, kind, subject, description }`. `student_id` must be a linked child |
| GET | `/complaints` | A (all), P (own) | Filters `status, category, kind, assigned_to` |
| GET | `/complaints/{id}` | A, P (own) | Parents never see `is_internal` comments |
| PATCH | `/complaints/{id}` | A | `status`, `priority`, `assigned_to` |
| POST | `/complaints/{id}/comments` | A, P (own) | Admin may set `is_internal` |
| GET | `/complaints/summary` | A | Counts by status/category |

Every status change or admin comment notifies the parent.

---

## 5. Cross-module service functions (not HTTP)

### Notifications — Member 2 provides, Member 1 calls
`backend/app/modules/notifications/service.py`:
```python
notify_users(db, user_ids: list[UUID], title: str, body: str, type: str,
             reference_type: str | None = None, reference_id: UUID | None = None) -> int
notify_section(db, section_id, title, body, type, include_parents=True, ...) -> int
```
- It only inserts `notifications` rows inside the caller's transaction; it never commits and never raises because of push failure.
- Member 1 calls it, e.g. after leave approval/rejection (`type="leave"`) and when a student is marked absent (`type="attendance"`). Member 1 should add `leave` and `attendance` to the allowed `notifications.type` values via a migration if they are not already allowed. Malik includes both in the first version of the CHECK constraint.
- Push: if `FCM_ENABLED=true` **and** credentials exist, a background task sends pushes to registered device tokens. Otherwise `push_status = disabled` and nothing else changes. The in-app inbox always works.

### PDF data — Member 2 provides data, Member 1 renders
Member 1 owns all PDF output (the `reports` module, library **reportlab**, school header/footer, fonts). Member 2 exposes plain Python functions returning dicts (the same data as the JSON endpoints):
```python
get_result_card_data(db, student_id, exam_id)    # modules/exams/service.py
get_fee_statement_data(db, student_id)           # modules/fees/service.py
get_fee_receipt_data(db, payment_id)             # modules/fees/service.py
get_timetable_data(db, section_id)               # modules/timetable/service.py
```
Member 1's endpoints (proposed paths): `GET /reports/result-card/{student_id}?exam_id=`, `/reports/fee-receipt/{payment_id}`, `/reports/fee-statement/{student_id}`, `/reports/timetable/{section_id}`, plus their attendance/student reports. Authorization for those PDFs must use the same rules as the JSON endpoints (Member 1 calls `can_access_student`; fee data is restricted to admin and linked parents).

---

## 6. Versioning and changes
- Additive changes (new optional field, new endpoint) can be made by the owner and announced in the PR description.
- Breaking changes (rename, remove, change type or meaning) need the other member's approval **and** an update to this file in the same PR.
- This file is the source of truth. If code and this file disagree, fix one of them in the same PR.