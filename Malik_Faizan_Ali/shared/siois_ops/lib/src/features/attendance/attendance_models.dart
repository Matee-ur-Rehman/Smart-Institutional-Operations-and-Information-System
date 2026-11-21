import 'package:flutter/material.dart';

import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';

const List<String> kAttendanceStatuses = <String>['present', 'absent', 'late', 'leave'];

String attendanceLabel(String s) {
  switch (s) {
    case 'present':
      return 'Present';
    case 'absent':
      return 'Absent';
    case 'late':
      return 'Late';
    case 'leave':
      return 'Leave';
    default:
      return s;
  }
}

class AttendanceSummary {
  AttendanceSummary({required this.totalDays, required this.present, required this.absent, required this.late, required this.leave, this.percentage});
  final int totalDays;
  final int present;
  final int absent;
  final int late;
  final int leave;
  final double? percentage;

  factory AttendanceSummary.fromJson(dynamic json) {
    final m = asMap(json);
    return AttendanceSummary(
      totalDays: asInt(m['total_days']),
      present: asInt(m['present']),
      absent: asInt(m['absent']),
      late: asInt(m['late']),
      leave: asInt(m['leave']),
      percentage: m['percentage'] == null ? null : asDouble(m['percentage']),
    );
  }
}

class SheetRow {
  SheetRow({required this.studentId, required this.rollNo, required this.fullName, this.status, this.remarks, this.onApprovedLeave = false});
  final String studentId;
  final String rollNo;
  final String fullName;
  final String? status;
  final String? remarks;
  final bool onApprovedLeave;

  factory SheetRow.fromJson(Map<String, dynamic> j) => SheetRow(
        studentId: asStr(j['student_id']),
        rollNo: asStr(j['roll_no']),
        fullName: asStr(j['full_name']),
        status: asStrN(j['status']),
        remarks: asStrN(j['remarks']),
        onApprovedLeave: asBool(j['on_approved_leave']),
      );
}

class AttendanceSheet {
  AttendanceSheet({required this.sectionId, required this.sectionLabel, required this.date, required this.editable, required this.rows});
  final String sectionId;
  final String sectionLabel;
  final DateTime date;
  final bool editable;
  final List<SheetRow> rows;

  factory AttendanceSheet.fromJson(dynamic json) {
    final m = asMap(json);
    return AttendanceSheet(
      sectionId: asStr(m['section_id']),
      sectionLabel: asStr(m['section_label']),
      date: asDate(m['date']),
      editable: asBool(m['editable']),
      rows: asMapList(m['rows']).map(SheetRow.fromJson).toList(),
    );
  }
}

class AttendanceRecord {
  AttendanceRecord({required this.date, required this.status, this.remarks});
  final DateTime date;
  final String status;
  final String? remarks;
  factory AttendanceRecord.fromJson(Map<String, dynamic> j) =>
      AttendanceRecord(date: asDate(j['date']), status: asStr(j['status']), remarks: asStrN(j['remarks']));
}

Color attendanceColor(String s) {
  switch (s) {
    case 'present':
      return Brand.success;
    case 'absent':
      return Brand.danger;
    case 'late':
      return Brand.warning;
    case 'leave':
      return Brand.info;
    default:
      return Brand.muted;
  }
}

class AttendanceChip extends StatelessWidget {
  const AttendanceChip(this.status, {super.key});
  final String status;
  @override
  Widget build(BuildContext context) => StatusChip(attendanceLabel(status), color: attendanceColor(status));
}
