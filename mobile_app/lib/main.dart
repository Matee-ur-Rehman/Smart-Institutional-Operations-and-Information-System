import 'package:flutter/material.dart';
import 'package:ops_features/ops_features.dart';

/// Mobile app: teachers, students and parents.
///
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1      (Android emulator)
///   flutter run --dart-define=API_BASE_URL=http://<PC-IP>:8000/api/v1       (real phone, same Wi-Fi)
///
/// Member 1 adds attendance, leave and reports by passing `extraItems` to the dashboards below.
void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    OpsApp(
      title: 'Trends High School',
      platform: 'mobile',
      allowedRoles: const {'teacher', 'student', 'parent'},
      homeForRole: (context, user) {
        switch (user.role) {
          case 'teacher':
            return const TeacherDashboard();
          case 'student':
            return const StudentDashboard();
          case 'parent':
            return const ParentDashboard();
          default:
            return const Scaffold(body: Center(child: Text('This account cannot use the mobile app.')));
        }
      },
    ),
  );
}
