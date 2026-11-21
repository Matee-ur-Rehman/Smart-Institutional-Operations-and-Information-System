import 'package:flutter/material.dart';
import 'package:siois_ops/siois_ops.dart';

/// Admin + Teacher web dashboard.
///
/// Run (backend on port 8000, CORS allows http://localhost:5000):
///   flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000
/// Optional one-tap demo logins (development only): --dart-define=DEMO_PASSWORD=School@12345
const String _apiBaseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://localhost:8000');
const String _demoPassword = String.fromEnvironment('DEMO_PASSWORD');

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SiOisApp(
    config: AppConfig(
      platform: 'web',
      title: 'SIOIS Admin Portal',
      allowedRoles: <Role>[Role.admin, Role.teacher],
      apiBaseUrl: _apiBaseUrl,
      demoPassword: _demoPassword,
      demoLoginIds: <Role, List<String>>{
        Role.admin: <String>['admin'],
        Role.teacher: <String>['teacher1', 'teacher2'],
      },
    ),
  ));
}
