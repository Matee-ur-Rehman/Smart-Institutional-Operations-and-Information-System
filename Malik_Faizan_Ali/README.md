# SIOIS - Trends High School, Hassan Abdal

Smart Institutional Operations and Information System: a school management system with a FastAPI + PostgreSQL backend,
a Flutter Web portal (Admin, Teacher) and a Flutter Android app (Teacher, Student, Parent).

> **Read this first - honest status**
> * **Backend: tested.** 281 automated tests pass (29 are skipped role/route matrix cells that do not apply). Run `cd backend && python -m pytest`.
> * **Flutter apps: compile-checked, not yet run.** They were written without a Flutter SDK. On the first real build (Windows) `flutter analyze` found
>   0 errors and the 20 unit/widget tests passed. The web and mobile apps themselves have not been run or click-tested yet. Use Flutter **stable** >= 3.27.
>   See [docs/FLUTTER_VERIFICATION.md](docs/FLUTTER_VERIFICATION.md) and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).
> * **Push notifications (FCM): untested**, off by default, need your own Firebase project.

## What is in it

| Area | Modules |
|---|---|
| Foundation (Member 1 - Matee) | auth + RBAC, users, students, parents, teachers, classes/sections, subjects, teaching assignments |
| Attendance & leave (Member 1) | daily attendance (teacher edits last 7 days), leave requests, attendance reports |
| Operations (Member 2 - Malik) | homework, exams & results, fees & receipts, timetable, calendar, announcements, notifications, complaints |
| Reports | result card PDF, fee receipt/statement PDF, timetable PDF, attendance report, CSV exports |

Roles: **Admin** (web), **Teacher** (web + mobile), **Student** and **Parent** (mobile only; the API refuses them on web).
Students do not see fees (parents and admin only, by design).

## Repository layout

```
backend/            FastAPI app, Alembic migrations (0001-0004), seeds, tests
  app/modules/      foundation, attendance, leave, lookups, homework, exams, fees, timetable,
                    calendar, announcements, notifications, complaints, reports
shared/siois_ops/   Flutter package with ALL screens, API client, auth, theme (+ tool/ checkers, test/)
web_app/            Flutter Web wrapper (Admin + Teacher)
mobile_app/         Flutter Android wrapper (Teacher, Student, Parent) + PUSH_SETUP.md
docs/               SETUP_GUIDE, API_CONTRACT, DATABASE_SCHEMA, INTEGRATION_GUIDE, KNOWN_LIMITATIONS,
                    FLUTTER_VERIFICATION, openapi.json
PROGRESS.md         build checkpoint log
```

## Quick start (details in [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md))

Fastest: `python setup.py`, then `start_backend.bat` (or `./start_backend.sh`), then `python check_system.py`. Manual version:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit DATABASE_URL and JWT_SECRET_KEY
alembic upgrade head
python -m seeds.seed_core && python -m seeds.seed_ops && python -m seeds.seed_attendance
uvicorn app.main:app --reload   # API docs: http://localhost:8000/docs
```

Demo logins after seeding (dev defaults, FAKE data): `admin` / `Admin@12345`; `teacher1..10`, `student1..48`, `parent1..40` / `School@12345`.
Every login request needs the header `X-Client-Platform: web` or `mobile` (the Flutter apps send it).

## Business rules worth knowing

* Attendance % = (present + late) / (present + late + absent); approved leave days are excluded.
* Teachers can edit attendance for the last 7 days only; Sundays and holiday events block marking.
* A new or admin-reset account must change its password at first login (`must_change_password`).
* Changing a password signs out all sessions (refresh tokens are revoked).

## Docs

[Setup guide](docs/SETUP_GUIDE.md) - [Known limitations](docs/KNOWN_LIMITATIONS.md) - [Flutter verification](docs/FLUTTER_VERIFICATION.md) -
[API contract](docs/API_CONTRACT.md) - [Database schema](docs/DATABASE_SCHEMA.md) - [Integration guide](docs/INTEGRATION_GUIDE.md) -
[OpenAPI](docs/openapi.json)
