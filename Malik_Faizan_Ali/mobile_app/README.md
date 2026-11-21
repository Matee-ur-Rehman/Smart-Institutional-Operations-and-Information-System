# SIOIS mobile app (Teacher, Student, Parent) - Android

Flutter. All screens live in `../shared/siois_ops`; this app only supplies its `AppConfig`.

## First-time setup (needs the Flutter SDK >= 3.27)
```bash
cd mobile_app
flutter create . --platforms=android --org pk.edu.trends --project-name siois_mobile   # generates android/ (keeps lib/main.dart)
python3 tool/patch_android.py --allow-cleartext      # INTERNET permission, app name, minSdk 23, http for dev
flutter pub get
```
`--allow-cleartext` is only for a plain `http://` development backend. Remove it (and use https) for a real release.

## Run
```bash
# emulator (backend on the PC, port 8000)
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000 --dart-define=DEMO_PASSWORD=School@12345
# real phone on the same Wi-Fi: use the PC's address, and start the backend with --host 0.0.0.0
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000
# release APK
flutter build apk --release --dart-define=API_BASE_URL=https://your-api-host
```
Roles allowed: teacher, student, parent (admins are told to use the web app).
Push notifications are optional: see `PUSH_SETUP.md`.
Not compiled or run in the environment that produced this code - see `../docs/FLUTTER_VERIFICATION.md`.
