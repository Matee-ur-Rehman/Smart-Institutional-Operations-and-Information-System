#!/usr/bin/env sh
# Android emulator (API at 10.0.2.2). For a real phone set API=http://<PC-LAN-IP>:8000 first. UNTESTED.
cd "$(dirname "$0")/mobile_app" || exit 1
[ -d android ] || { flutter create . --platforms=android --org pk.edu.trends --project-name siois_mobile && python3 tool/patch_android.py --allow-cleartext; }
flutter pub get && flutter run --dart-define=API_BASE_URL="${API:-http://10.0.2.2:8000}" --dart-define=DEMO_PASSWORD=School@12345
