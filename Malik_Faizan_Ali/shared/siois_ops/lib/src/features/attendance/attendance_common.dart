import 'package:flutter/material.dart';

import '../../core/theme.dart';

/// Attendance status helpers shared by the staff and student/parent screens.
const List<String> kAttendanceStatuses = <String>['present', 'late', 'absent', 'leave'];

Color attendanceColor(String? status) {
  switch (status) {
    case 'present':
      return Brand.success;
    case 'late':
      return Brand.warning;
    case 'absent':
      return Brand.danger;
    case 'leave':
      return Brand.info;
    default:
      return Brand.muted;
  }
}

String attendanceLabel(String status) {
  switch (status) {
    case 'present':
      return 'Present';
    case 'late':
      return 'Late';
    case 'absent':
      return 'Absent';
    case 'leave':
      return 'Leave';
    default:
      return status;
  }
}

/// Small coloured count tile ("Present 24").
class CountPill extends StatelessWidget {
  const CountPill(this.label, this.value, this.color, {super.key});
  final String label;
  final Object value;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
        child: Text('$label  $value', style: TextStyle(color: color, fontWeight: FontWeight.w700)),
      );
}
