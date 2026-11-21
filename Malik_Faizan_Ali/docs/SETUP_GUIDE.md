# Setup guide

## FAST PATH (recommended) - 4 commands

```bash
python setup.py              # venv + pip install + PostgreSQL user/DBs + backend/.env + migrations + demo data + tests
start_backend.bat            # Windows   (macOS/Linux: ./start_backend.sh)   -> API on http://localhost:8000/docs
python check_system.py       # 2nd terminal: logs in as every role and prints a PASS/FAIL table (27 checks)
run_web.bat                  # Flutter web (macOS/Linux: ./run_web.sh)       -> needs Flutter >= 3.27, UNTESTED
run_mobile.bat               # Android (./run_mobile.sh)                     -> UNTESTED
```
Requirements before `setup.py`: Python 3.11+ and PostgreSQL running (note the password of its `postgres` user, asked once).
`setup.py` was tested on Linux against a fresh database (migrations, seeds, then `check_system.py`: 27/27). It was **not** run on Windows.
It never overwrites an existing `backend/.env` (use `--force-env`), and generates a new random JWT secret.

**About the `*.whl` files that were in `backend/`:** they were stray downloads (Flask, SQLAlchemy 2.1 etc.) and are not used. They are
removed from the zip. `pip install -r requirements.txt` (run by `setup.py`) downloads everything the backend needs.

**`.env`:** created for you by `setup.py`. Fields: `DATABASE_URL`, `TEST_DATABASE_URL`, `JWT_SECRET_KEY` (random), `CORS_ORIGINS`
(must contain the web app origin; the run scripts use port 5000), `SEED_*_PASSWORD` (demo passwords), `FCM_*` (push, off).

The manual step-by-step version follows.

Tested: steps 1-5 (backend) on Linux with Python 3.13 and PostgreSQL 16. **Not tested:** steps 6-8 (Flutter) - no Flutter SDK was available.
Windows/macOS commands differ only in venv activation (`.venv\Scripts\activate` on Windows).

## 1. Requirements

| Tool | Version | Needed for |
|---|---|---|
| Python | 3.11+ (3.13 used) | backend |
| PostgreSQL | 14+ (16 used) | database |
| Flutter | **3.27+** (Dart 3.6+) | web and mobile apps |
| Android Studio / SDK | recent, with an emulator or a USB phone | mobile app |
| Chrome | any recent | web app |

## 2. Database

```sql
-- in psql as a superuser
CREATE USER school_user WITH PASSWORD 'choose-a-password';
CREATE DATABASE school_db OWNER school_user;
CREATE DATABASE school_test_db OWNER school_user;   -- used only by the tests
```

## 3. Backend install

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```
Edit `.env`: set `DATABASE_URL`, `TEST_DATABASE_URL`, a long random `JWT_SECRET_KEY`
(`python -c "import secrets;print(secrets.token_urlsafe(48))"`), and `CORS_ORIGINS` (must include the web app origin, e.g. `http://localhost:5000`).
`SEED_ADMIN_PASSWORD` / `SEED_USER_PASSWORD` may be left unset only while `APP_ENV=development` (dev defaults are then `Admin@12345` / `School@12345`).
**Never run with those defaults in production.**

## 4. Migrate and seed

```bash
alembic upgrade head                 # migrations 0001-0004
python -m seeds.seed_core            # year, classes, sections, subjects, teachers, 48 students, 40 parents, accounts
python -m seeds.seed_ops             # fee heads, exams, homework, timetable, calendar, announcements, complaints...
python -m seeds.seed_attendance      # ~35 days of attendance + leave requests (run after seed_ops)
```
All seeds are idempotent (safe to rerun). All people and phone numbers are FAKE.

## 5. Run and test the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# http://localhost:8000/docs  -> interactive API
python -m pytest                     # expect: 281 passed, 29 skipped
```
Uploads are stored in `UPLOAD_DIR` (default `backend/uploads`). `--host 0.0.0.0` is needed if a physical phone must reach the API.

## 6. Flutter: check the code first

```bash
cd shared/siois_ops
bash tool/verify.sh        # python heuristics, then flutter pub get / analyze / test if Flutter is installed
```
Fix what `flutter analyze` reports before running anything. See [FLUTTER_VERIFICATION.md](FLUTTER_VERIFICATION.md).

## 7. Web app (Admin + Teacher)

```bash
cd web_app
flutter pub get
flutter run -d chrome --web-port 5000 \
  --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=DEMO_PASSWORD=School@12345
```
`DEMO_PASSWORD` only enables the demo-account chips on the login page; omit it for a real deployment.
Production build: `flutter build web --release --dart-define=API_BASE_URL=https://your-api-host`, then serve `build/web` with any static host
and add that origin to `CORS_ORIGINS`.

## 8. Mobile app (Android)

```bash
cd mobile_app
flutter create . --platforms=android --org pk.edu.trends --project-name siois_mobile
python3 tool/patch_android.py --allow-cleartext     # INTERNET permission, app label, minSdk 23, http allowed for dev
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=DEMO_PASSWORD=School@12345
```
* Emulator reaches the host machine at `10.0.2.2`. For a real phone use your PC's LAN IP, same Wi-Fi, and run uvicorn with `--host 0.0.0.0`.
* Drop `--allow-cleartext` and use https for any real deployment.
* Release APK: `flutter build apk --release --dart-define=API_BASE_URL=https://your-api-host` (signing setup is up to you).
* `patch_android.py` was tested only on an imitation of the generated files. If it reports a file that looks different, make the four edits by hand
  (see the script header).

## 9. Push notifications (optional, untested)

In-app notifications work without Firebase. For real push: create a Firebase project, put the service-account JSON on the server, set
`FCM_ENABLED=true` and `FCM_CREDENTIALS_FILE=...`, `pip install firebase-admin==6.9.0`, and follow `mobile_app/PUSH_SETUP.md` for the app side.

## 10. Demo walkthrough (suggested order)

1. Web as `admin`: dashboard, students, classes, fees (generate invoices, record payment, receipt PDF), exams (publish results), reports.
2. Web as `teacher1`: mark attendance, create homework, enter marks.
3. Mobile as `parent1`: child attendance, apply leave, fees and receipt, complaints.
4. Mobile as `student1`: homework, timetable, results. No Fees menu.
5. Back as admin: approve the leave, post an announcement; parent/student see a notification.

## 11. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Login says wrong platform | student/parent on web, or admin on mobile: by design |
| 400 on login, missing header | client must send `X-Client-Platform` (Swagger: add it manually) |
| Web app: CORS error | add the exact web origin (scheme+host+port) to `CORS_ORIGINS`, restart |
| Phone cannot connect | wrong IP, firewall, or uvicorn not on `0.0.0.0`; cleartext not allowed without the patch |
| Signed out after changing password | intended; all sessions are revoked, log in again |
| `alembic` cannot connect | check `DATABASE_URL` user/password/db exist (step 2) |
| Tests fail to connect | create `school_test_db` and set `TEST_DATABASE_URL` |
