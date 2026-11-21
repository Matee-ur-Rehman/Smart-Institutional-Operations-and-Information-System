@echo off
cd /d "%~dp0web_app"
call flutter pub get
if errorlevel 1 exit /b 1
call flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000 --dart-define=DEMO_PASSWORD=School@12345