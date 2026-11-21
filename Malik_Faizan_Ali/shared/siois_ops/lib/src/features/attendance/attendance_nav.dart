import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'attendance_staff_page.dart';
import 'attendance_view_page.dart';

List<NavEntry> attendanceNav(Role role) {
  switch (role) {
    case Role.admin:
    case Role.teacher:
      return <NavEntry>[
        NavEntry(id: 'attendance', title: 'Attendance', icon: Icons.fact_check_outlined, group: 'Academics', builder: (context) => const AttendanceStaffPage()),
      ];
    case Role.student:
    case Role.parent:
      return <NavEntry>[
        NavEntry(id: 'attendance', title: 'Attendance', icon: Icons.fact_check_outlined, group: 'Academics', builder: (context) => const AttendanceViewPage()),
      ];
  }
}
