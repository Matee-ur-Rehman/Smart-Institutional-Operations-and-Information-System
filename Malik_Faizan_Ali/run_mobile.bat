@echo off
rem Emulator: API at 10.0.2.2. Real phone: set API=http://PC-IP:8000 first. Needs Android SDK (flutter doctor).
cd /d "%~dp0mobile_app"
if not exist android (
  call flutter create . --platforms=android --org pk.edu.trends --project-name siois_mobile
  if errorlevel 1 exit /b 1
  python tool\patch_android.py --allow-cleartext
)
if "%API%"=="" set API=http://10.0.2.2:8000
call flutter pub get
if errorlevel 1 exit /b 1
call flutter run --dart-define=API_BASE_URL=%API% --dart-define=DEMO_PASSWORD=School@12345