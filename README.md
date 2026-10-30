# Smart Institutional Operations and Information System
Trends High School, Hassan Abdal — final year project.

Flutter Web (Admin + Teacher) · Flutter Android (Teacher, Student, Parent) · FastAPI · PostgreSQL · REST/JSON.
Shared contracts live in `docs/` (`API_CONTRACT.md`, `DATABASE_SCHEMA.md`, `INTEGRATION_GUIDE.md`). Read those first.

> **Honest status (read this).**
> - **Backend:** all 236 automated tests pass on SQLite (run on Windows, Python 3.11, 2026-10-27). Not yet
>   verified: the Alembic migrations and the PostgreSQL-specific behaviour (run `pytest` against PostgreSQL, see
>   *Testing*), and Firebase push notifications (need real credentials).
> - **Flutter:** the shared API package (`packages/ops_features/lib/src/core`) passes `flutter analyze`. Everything
>   else in Flutter (all screens, the dashboards, `web_app`, `mobile_app`) was written without a Flutter SDK and
>   **has never been compiled or run**. Expect analyzer errors on the first run; fix them in rounds.

## Who owns what
| | Member 1 (Faizan) | Member 2 (Matee) |
|---|---|---|
| Modules | Auth & roles, students & parents, teachers, classes/sections/subjects, attendance, leave, reports & PDF | Homework, exams/marks/results, fees, timetable, calendar & events, announcements & notifications, complaints & feedback |

Files marked `TEMPORARY STUB` (in `backend/app/core/`, `backend/app/modules/auth_stub/`,
`backend/migrations/versions/0001_core_foundation.py`, `backend/seeds/seed_core.py`, `backend/tests/conftest.py`)
were written by Member 2 only so his modules can run before Member 1's code is merged. **Member 1 replaces
them with the real versions**; see "Merging with Member 1" below.

## Backend setup (Member 2 modules)
Requirements: Python 3.11+ (written for 3.13), PostgreSQL 16.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env            # Linux/macOS: cp .env.example .env
# edit .env: DATABASE_URL, JWT_SECRET_KEY (long random string), SEED_DEFAULT_PASSWORD
```
Create the database once (psql):
```sql
CREATE USER school_user WITH PASSWORD 'your-password';
CREATE DATABASE school_db OWNER school_user;
CREATE DATABASE school_test_db OWNER school_user;   -- optional, only for PostgreSQL test runs
```
Then, from `backend/`:
```bash
alembic upgrade head              # creates all tables (0001 = temporary core stub, 0002 = Member 2 tables)
python -m seeds.seed_core         # DEMO foundation data (temporary stub) - demo accounts only!
python -m seeds.seed_ops          # grade scale, fee heads/fees, period timings, holidays, samples
uvicorn app.main:app --reload     # http://localhost:8000
```
API docs: http://localhost:8000/docs · health check: http://localhost:8000/health

### Demo accounts (created by `seed_core`, password = `SEED_DEFAULT_PASSWORD` from your `.env`)
| login_id | role | platform |
|---|---|---|
| `admin` | admin | web |
| `t.ahmed`, `t.fatima` | teacher | web or mobile |
| `s.ali`, `s.sara` | student | mobile |
| `p.ali`, `p.sara` | parent | mobile |

Login: `POST /api/v1/auth/login` with header `X-Client-Platform: web` or `mobile` and body
`{"login_id": "...", "password": "..."}`. Then send `Authorization: Bearer <access_token>`.

## Testing
```bash
cd backend
pytest                            # default: in-memory SQLite, needs no PostgreSQL
```
Against PostgreSQL (also exercises the Alembic migrations; **use a separate database, every test wipes tables**):
```bash
set TEST_DATABASE_URL=postgresql+psycopg2://school_user:your-password@localhost:5432/school_test_db
pytest
```
`backend/tests/ops/` has 182 test functions covering each module's happy path, validation errors, and
access control (401 without a token, 403 for the wrong role, 404 for another family's records).
All 236 pass on SQLite. The PostgreSQL run (which also exercises the migrations) has not been done yet.

## Flutter apps (UNTESTED: never compiled)
Requires the Flutter SDK (written against 3.47) plus Android Studio for the Android app. `flutter doctor` must
show Flutter, Android toolchain and Chrome as OK (the Visual Studio line is not needed).

One-time setup, from the repository root:
```bash
cd packages/ops_features && flutter pub get && flutter analyze && cd ../..
flutter create --org pk.edu.trends --project-name trends_mobile --platforms android mobile_app
flutter create --project-name trends_web --platforms web web_app
```
`flutter create` generates the platform folders; then keep the committed `lib/main.dart`, `pubspec.yaml` and
`mobile_app/android/app/src/debug/AndroidManifest.xml` (overwrite the generated ones) and delete the generated
`test/widget_test.dart` in both apps. Then `flutter pub get` inside each app.

Run (start the backend first, see above):
```bash
cd web_app
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000/api/v1

cd ../mobile_app
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1     # Android emulator
```
For a real phone use `http://<your-PC-IP>:8000/api/v1` and start the backend with `--host 0.0.0.0`.
Web port 5000 is in the backend's `CORS_ORIGINS`; if you use another port, add it there.
Platform rule: `admin` can only sign in on the web app; `student` and `parent` only on the mobile app.

## What is implemented
| Module | Backend | Flutter screens |
|---|---|---|
| Homework & assignments (create, due dates, attachment, student/parent view; student submission **disabled** by decision) | tests pass (SQLite) | written, not yet compiled |
| Exams, marks, grade scale, results, publish | tests pass (SQLite) | written, not yet compiled |
| Fees (heads, structures, invoices, admin-recorded payments, reversals, statements) | tests pass (SQLite) | written, not yet compiled |
| Timetable (periods, slots, clash checks, grids) | tests pass (SQLite) | written, not yet compiled |
| Calendar & events (audience-filtered) | tests pass (SQLite) | written, not yet compiled |
| Announcements & notifications (in-app inbox) | tests pass (SQLite) | written, not yet compiled |
| Complaints & feedback | tests pass (SQLite) | written, not yet compiled |
| Read-only lookup endpoints for the Flutter forms | written | n/a |

Flutter: `packages/ops_features` holds every screen, the login page and the role dashboards (admin, teacher,
student, parent). `web_app/` and `mobile_app/` are thin apps that only start it. Fees screens and the dashboards were
added last. Parents see fees; students do not. Homework attachments cannot be opened in the app yet.

## Known limitations / setup still needed
- **Push notifications:** off (`FCM_ENABLED=false`). The in-app inbox works without Firebase. To enable later:
  Firebase project → add the Android app → put `google-services.json` in `mobile_app/android/app/` (git-ignored)
  → service-account key path in `FCM_CREDENTIALS_FILE` → `FCM_ENABLED=true`. The sender code is **untested**
  and needs real credentials to test.
- **No online payments:** fees are recorded by the admin only (project decision).
- **Platform rule** (admin web only, students/parents mobile only) is enforced at login using a header sent by
  the client. It is a product restriction, not a security boundary; real protection is the per-endpoint role
  and ownership checks.
- **Announcements:** scheduled publishing is not implemented (an announcement is published when its status
  is set to `published`).
- **PDFs:** owned by Member 1. Member 2 only supplies data functions (see `docs/API_CONTRACT.md` section 5).
- Default grade bands, fee heads and amounts, period timings and subjects are placeholders to customise.

## Merging with Member 1
1. Both agree the three docs in `docs/` (set the Status line to AGREED).
2. Member 1 adds his real `app/core/*`, auth module, models, `0001_core_foundation` migration, `seed_core.py`
   and `tests/conftest.py`, replacing the stub versions (his must keep the names listed in each stub's header).
3. Delete `backend/app/modules/auth_stub/` and its `include_router` line in `app/main.py`.
4. Change only the import block in `backend/app/modules/ops_common/core_refs.py` (and `app/db_models.py`) to point at his models.
5. Run `pytest` again.

## Git workflow
Branches `m1/<topic>` and `m2/<topic>`, small pull requests, the other member reviews. Never commit `.env`,
Firebase files or uploads (`.gitignore` covers them). Details: `docs/INTEGRATION_GUIDE.md`.
