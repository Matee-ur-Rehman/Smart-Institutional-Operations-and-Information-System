# SIOIS web app (Admin + Teacher)

Flutter Web. All screens live in `../shared/siois_ops`; this app only supplies its `AppConfig`.

```bash
cd web_app
flutter pub get
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000
# release build:
flutter build web --release --dart-define=API_BASE_URL=https://your-api-host
```

* The backend's `CORS_ORIGINS` must contain the origin you open (default `http://localhost:5000`).
* Roles allowed: admin, teacher. Student and parent accounts are told to use the mobile app.
* `web/index.html` and `web/manifest.json` are included. If `flutter` complains about missing platform
  files, run `flutter create . --platforms=web --project-name siois_web` once (it keeps `lib/main.dart`).
* Not compiled or run in the environment that produced this code - see `../docs/FLUTTER_VERIFICATION.md`.
