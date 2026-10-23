# INTEGRATION_GUIDE.md

**Status: PROPOSED — needs agreement from Faizan (Member 1) and Matee (Member 2).**
This describes how the two of us work in one repository without breaking each other's work. Companion files: `API_CONTRACT.md`, `DATABASE_SCHEMA.md`.

---

## 1. Who owns what

| Area | Member 1 — Faizan | Member 2 — Matee |
|---|---|---|
| Backend modules | auth, users, students, parents, teachers, classes (class/section/subject), attendance, leave, reports | homework, exams, fees, timetable, calendar, announcements, notifications, complaints |
| Shared backend core (`app/core/`) | **owns**: config, database, security (JWT), access helpers, error handlers | uses; proposes changes by PR |
| Database tables | section 2 of DATABASE_SCHEMA.md | section 3 of DATABASE_SCHEMA.md |
| Flutter shared app shell | **owns** (see section 5) | uses; adds own screens |
| PDF engine | **owns** | supplies data functions |
| Notification service | calls it | **owns** |
| Admin web screens | students, parents, teachers, classes, attendance, leave, reports | homework, exams/marks/results, fees, timetable, calendar, announcements, complaints |

## 2. Repository layout (proposed)

```
Smart-Institutional-Operations-and-Information-System/
├── README.md
├── docs/                      API_CONTRACT.md, DATABASE_SCHEMA.md, INTEGRATION_GUIDE.md
├── backend/
│   ├── requirements.txt
│   ├── .env.example           names only, no real secrets
│   ├── alembic.ini
│   ├── migrations/versions/   0001_core_foundation.py (M1), 0002_m2_...py (M2) ...
│   ├── seeds/                 seed_core.py (M1), seed_ops.py (M2)
│   ├── app/
│   │   ├── main.py            registers every router (see 3)
│   │   ├── core/              config.py, database.py, security.py, access.py, errors.py   (M1)
│   │   └── modules/
│   │       ├── auth/ students/ parents/ teachers/ academics/ attendance/ leave/ reports/   (M1)
│   │       └── homework/ exams/ fees/ timetable/ calendar/ announcements/ notifications/ complaints/   (M2)
│   └── tests/
│       ├── conftest.py        shared fixtures (M1 creates, M2 extends only by adding)
│       ├── core/  ...         (M1)
│       └── ops/   ...         (M2)
├── web_app/                   Flutter Web: Admin + Teacher dashboards
└── mobile_app/                Flutter Android: Teacher, Student, Parent dashboards
```

Each backend module folder has the same files: `models.py`, `schemas.py`, `router.py`, `service.py`, `__init__.py`. **Never edit a file inside the other member's module folder.** Need a change there? Open an issue or ask in chat; the owner makes it.

## 3. Shared files we both touch (handle with care)

| File | Rule |
|---|---|
| `backend/app/main.py` | Only add one `include_router(...)` line per module. Keep lines alphabetical to reduce merge conflicts |
| `backend/requirements.txt` | Add packages on new lines at the end of your own section (`# --- member 1 ---`, `# --- member 2 ---`). Pin versions |
| `backend/.env.example` | Same: add under your own heading |
| `backend/tests/conftest.py` | Faizan creates it; Matee only appends fixtures, never changes existing ones |
| `README.md` | Each member owns their own "Modules" section; the setup section is Faizan's, and Matee proposes edits |
| Flutter `pubspec.yaml`, router, API client | See section 5 |
| `docs/*.md` | Edit only in a PR that the other member approves |

## 4. Git workflow

- `main` is always runnable. **Nobody pushes directly to `main`** (turn on branch protection: require 1 approving review).
- Branch names: `m1/<short-topic>`, `m2/<short-topic>` (e.g. `m2/fees-backend`).
- Small, frequent PRs (a module slice, not a whole month). The other member reviews and merges.
- Commit messages: `<module>: <what>` (e.g. `fees: add payment recording`).
- Before starting work each day: `git checkout main && git pull`, then rebase your branch on `main`.
- Never commit: `.env`, `google-services.json`, Firebase service-account JSON, uploaded files, `__pycache__`, `.venv`, Flutter `build/`. `.gitignore` covers all of these (Faizan adds it in the first PR; Matee checks it).
- **Order of first merges:** (1) Faizan: `backend/app/core`, `0001_core_foundation` migration, auth and `seed_core.py`; (2) Matee branches from that. Until it lands, Matee builds against a temporary stub that has the same function signatures as API_CONTRACT section 2 and is deleted when the real one merges.

## 5. Flutter applications

Two separate Flutter projects, one backend.

- **Faizan** creates the project skeleton first: folder structure, theme, router, login screen, secure token storage, the API client (Dio, adds the Bearer header, refreshes tokens, sends `X-Client-Platform`), role-based navigation shell, and shared widgets. He merges it before Matee adds screens.
- **Matee** adds screens inside `features/<module>/` folders only (e.g. `lib/features/fees/`), plus one line per feature in the router/menu.
- `web_app/` shows Admin and Teacher dashboards. `mobile_app/` shows Teacher, Student and Parent dashboards. The login response's `role` decides which dashboard loads, and a role not allowed on that platform is signed out with a clear message.
- API base URL comes from a `--dart-define=API_BASE_URL=...` build argument, never hard-coded. Local Android emulator: `http://10.0.2.2:8000/api/v1`.
- Suggested packages (agree before adding): `dio`, `flutter_riverpod` (or `provider`; pick one), `go_router`, `flutter_secure_storage`, `intl`, `firebase_messaging` (added only when Firebase is configured).

## 6. Authentication and authorization rules (summary)

1. Every endpoint except `/auth/login`, `/auth/refresh` and `/health` requires a valid access token.
2. Role checks use `require_roles(...)`. Record-level checks (own child, own section, teaches this subject) use the helpers in `app/core/access.py`. Role check alone is **not** enough for records.
3. Return `404` instead of `403` for records the caller must not know exist (another family's child).
4. List endpoints must filter by the caller's scope in the database query itself, not after fetching.
5. Passwords: bcrypt hashes only. No password ever appears in logs, responses or seeds committed with real values.
6. Every module has a test that proves an unauthorised user cannot read or write protected records (a parent cannot read another parent's child, a teacher cannot enter marks for a section they don't teach, a student cannot see fees, and so on).

## 7. Environment variables

`backend/.env.example` lists the names. Real values live only in each developer's local `.env`.

```
# --- shared (Member 1) ---
DATABASE_URL=postgresql+psycopg2://school_user:CHANGE_ME@localhost:5432/school_db
JWT_SECRET_KEY=CHANGE_ME_LONG_RANDOM_STRING
JWT_ACCESS_MINUTES=30
JWT_REFRESH_DAYS=7
CORS_ORIGINS=http://localhost:5000,http://localhost:3000
APP_ENV=development
SEED_ADMIN_PASSWORD=CHANGE_ME
# --- member 2 ---
UPLOAD_DIR=./uploads
MAX_UPLOAD_MB=5
FCM_ENABLED=false
FCM_CREDENTIALS_FILE=            # path to Firebase service-account JSON; leave empty until available
```

## 8. Testing

- Backend tests use `pytest` against a **separate test database** (`school_test_db`), never the dev database. Faizan's `conftest.py` creates the schema by running Alembic migrations, so migrations are tested too.
- Each member tests their own modules: `tests/core/` and `tests/ops/`.
- Required for every module: happy path, validation errors, unauthenticated (401), wrong role (403), and wrong-owner (404) cases.
- Before opening a PR: `pytest` passes locally. Flutter: `flutter analyze` and `flutter test` pass.
- Run the app locally: `uvicorn app.main:app --reload` from `backend/`.

## 9. Notifications and Firebase

- The in-app notification inbox works with no Firebase at all.
- Push is off by default (`FCM_ENABLED=false`). To enable later: create a Firebase project, add the Android app, download `google-services.json` into `mobile_app/android/app/` (git-ignored), create a service-account key and point `FCM_CREDENTIALS_FILE` at it, set `FCM_ENABLED=true`. Matee wires and tests the sender; this cannot be verified until real credentials exist.

## 10. PDFs

Faizan owns the PDF engine and endpoints. Matee supplies the data functions listed in API_CONTRACT section 5. Matee does not write PDF code. Faizan does not query fee/exam tables directly and always goes through those data functions, so a schema change on one side doesn't silently break the other.

## 11. Communication and decisions

- Questions about the other person's module → ask in chat first; if it changes a table, endpoint or contract → update the docs in a PR.
- Record agreements by editing the "Status" line at the top of each doc to `AGREED — <date> — Faizan ✔ Matee ✔`.
- Open issues on GitHub for bugs and for "I need X from your module".

## 12. Proposal conflicts and decisions log

| # | Topic | Decision (2026-10-21/22) |
|---|---|---|
| 1 | Proposal says "Supabase / PostgreSQL"; task brief says FastAPI + PostgreSQL | **FastAPI + PostgreSQL.** The supervisor should be told the proposal's backend line changed |
| 2 | Proposal lists a Teacher *app* only; brief gives teachers web + mobile | Teachers have both |
| 3 | Fees | Recorded by admin only. No online payment gateway |
| 4 | Student fee visibility | Proposal gives fee status to parents only, so students do not see fees |
| 5 | Student homework submission | Disabled for now. Table exists, no endpoints |
| 6 | Complaints | Parents submit; admin manages. Students and teachers cannot submit (not in the proposal) |
| 7 | Leave requests | Parents submit (Member 1's module) |
| 8 | Push notifications | In-app inbox first; FCM later |
| 9 | School defaults | Grades, fee heads, period timings, classes and subjects are seeded defaults and can be customised later |

## 13. Definition of "done" for a module

Backend endpoints + migration + seed + tests passing + this doc updated + Flutter screens for each allowed role + listed in README. Anything not yet tested is labelled **untested** in the README, not described as complete.