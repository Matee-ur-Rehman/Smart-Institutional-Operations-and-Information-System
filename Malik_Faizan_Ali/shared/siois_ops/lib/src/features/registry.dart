import '../core/auth.dart';
import '../core/nav.dart';
import 'academics/academics_nav.dart';
import 'announcements/announcements_nav.dart';
import 'attendance/attendance_nav.dart';
import 'calendar/calendar_nav.dart';
import 'complaints/complaints_nav.dart';
import 'dashboard/dashboard_nav.dart';
import 'exams/exams_nav.dart';
import 'fees/fees_nav.dart';
import 'homework/homework_nav.dart';
import 'leave/leave_nav.dart';
import 'notifications/notifications_nav.dart';
import 'parents/parents_nav.dart';
import 'profile/profile_nav.dart';
import 'reports/reports_nav.dart';
import 'students/students_nav.dart';
import 'teachers/teachers_nav.dart';
import 'timetable/timetable_nav.dart';
import 'users/users_nav.dart';

/// Sidebar / drawer entries for a role, in display order. One line per feature:
/// a feature returns an empty list for roles that have no screen in that module.
/// (The shell groups entries by `NavEntry.group`.)
List<NavEntry> buildNav(Role role) => <NavEntry>[
      ...dashboardNav(role),
      // People & structure (Member 1)
      ...studentsNav(role),
      ...parentsNav(role),
      ...teachersNav(role),
      ...academicsNav(role),
      // Daily school work
      ...attendanceNav(role),
      ...leaveNav(role),
      ...homeworkNav(role),
      ...examsNav(role),
      ...timetableNav(role),
      ...reportsNav(role),
      ...calendarNav(role),
      // Communication & money
      ...announcementsNav(role),
      ...notificationsNav(role),
      ...feesNav(role),
      ...complaintsNav(role),
      // Administration & account
      ...usersNav(role),
      ...profileNav(role),
    ];
