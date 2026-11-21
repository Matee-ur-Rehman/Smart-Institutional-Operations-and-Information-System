import 'package:flutter/material.dart';
import 'package:siois_ops/siois_ops.dart';

/// Teacher + Student + Parent Android app.
///
/// Android emulator reaches the PC's backend at 10.0.2.2. For a real phone use the PC's LAN address:
///   flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000
/// Optional one-tap demo logins (development only): --dart-define=DEMO_PASSWORD=School@12345
const String _apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');
const String _demoPassword = String.fromEnvironment('DEMO_PASSWORD');

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SiOisApp(
    config: AppConfig(
      platform: 'mobile',
      title: 'SIOIS',
      allowedRoles: <Role>[Role.teacher, Role.student, Role.parent],
      apiBaseUrl: _apiBaseUrl,
      demoPassword: _demoPassword,
      demoLoginIds: <Role, List<String>>{
        Role.teacher: <String>['teacher1'],
        Role.student: <String>['student1'],
        Role.parent: <String>['parent1'],
      },
      // pushTokenProvider: see PUSH_SETUP.md (needs your Firebase project)
    ),
  ));
}
