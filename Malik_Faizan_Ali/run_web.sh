#!/usr/bin/env sh
# Needs Flutter >= 3.27 and the backend running. UNTESTED (Flutter was not available when this was written).
cd "$(dirname "$0")/web_app" && flutter pub get && \
flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=DEMO_PASSWORD=School@12345
