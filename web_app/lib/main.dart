import 'package:flutter/material.dart';
import 'package:ops_features/ops_features.dart';

/// Web app: administrators and teachers.
///
///   flutter run -d chrome --web-port 5000 --dart-define=API_BASE_URL=http://localhost:8000/api/v1
///
/// Port 5000 matches CORS_ORIGINS in backend/.env.example.
/// Member 1 adds students, parents, teachers, attendance, leave and reports by passing
/// `extraItems` to the dashboards below.
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    OpsApp(
      title: 'Trends High School',
      platform: 'web',
      allowedRoles: const {'admin', 'teacher'},
      homeForRole: (context, user) {
        switch (user.role) {
          case 'admin':
            return const AdminDashboard();
          case 'teacher':
            return const TeacherDashboard();
          default:
            return const Scaffold(body: Center(child: Text('This account cannot use the web app.')));
        }
      },
    ),
  );
}
