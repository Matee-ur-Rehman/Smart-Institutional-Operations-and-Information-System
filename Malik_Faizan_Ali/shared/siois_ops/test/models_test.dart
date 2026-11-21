import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siois_ops/src/core/api_client.dart';
import 'package:siois_ops/src/core/auth.dart';
import 'package:siois_ops/src/features/attendance/attendance_models.dart';
import 'package:siois_ops/src/features/exams/exams_models.dart';
import 'package:siois_ops/src/features/fees/fee_models.dart';
import 'package:siois_ops/src/features/homework/homework_models.dart';
import 'package:siois_ops/src/features/timetable/timetable_models.dart';

// Model parsing against the exact JSON shapes the backend returns. NOT executed in the authoring environment.
void main() {
  test('ApiException.errorFor matches nested field paths', () {
    final e = ApiException(422, 'validation_error', 'Invalid', fieldErrors: const [FieldError('entries.3.student_id', 'bad'), FieldError('due_date', 'past')]);
    expect(e.errorFor('student_id'), 'bad');
    expect(e.errorFor('due_date'), 'past');
    expect(e.errorFor('missing'), isNull);
    expect(e.fullMessage, contains('due_date'));
  });

  test('AppUser.tryParse reads role and must_change_password', () {
    final u = AppUser.tryParse({'id': '1', 'login_id': 'admin', 'role': 'admin', 'full_name': 'Ada Min', 'must_change_password': true});
    expect(u, isNotNull);
    expect(u!.role, Role.admin);
    expect(u.mustChangePassword, isTrue);
    expect(u.initials, 'AM');
    expect(AppUser.tryParse({'role': 'janitor'}), isNull);
  });

  test('FeeInvoice parses Decimal strings, items and payments', () {
    final inv = FeeInvoice.fromJson({
      'id': 'i1', 'invoice_no': 'INV-1', 'student_id': 's1', 'student_name': 'A', 'roll_no': '1', 'section_label': 'Class 8-A',
      'period_label': 'Nov 2026', 'issue_date': '2026-11-01', 'due_date': '2026-11-15',
      'total_amount': '5000.00', 'discount_amount': '500.00', 'net_amount': '4500.00', 'paid_amount': '1000.00', 'balance': '3500.00',
      'status': 'partial',
      'items': [{'id': 'x', 'description': 'Tuition', 'amount': '5000.00'}],
      'payments': [{'id': 'p', 'receipt_no': 'R-1', 'amount': '1000.00', 'payment_date': '2026-11-02', 'method': 'cash', 'is_reversal': false, 'is_reversed': false}],
    });
    expect(inv.net, 4500.0);
    expect(inv.balance, 3500.0);
    expect(inv.items.single.description, 'Tuition');
    expect(inv.payments.single.receiptNo, 'R-1');
    expect(round2(0.1 + 0.2), 0.3);
  });

  test('Assignment parses days_left and nullable max_marks', () {
    final a = Assignment.fromJson({
      'id': 'a', 'teacher_name': 'T', 'section_id': 's', 'section_label': 'Class 8-A', 'subject_id': 'u', 'subject_name': 'Math',
      'title': 'Ex 4', 'assigned_date': '2026-10-01', 'due_date': '2026-10-05', 'max_marks': null, 'has_attachment': true,
      'status': 'published', 'is_overdue': false, 'days_left': 3,
    });
    expect(a.maxMarks, isNull);
    expect(a.daysLeft, 3);
    expect(a.hasAttachment, isTrue);
  });

  test('Exam and ExamPaper', () {
    final e = Exam.fromJson({'id': 'e', 'name': 'Mid', 'exam_type': 'midterm', 'start_date': '2026-11-01', 'end_date': '2026-11-10', 'status': 'results_published', 'schedule_count': 4});
    expect(e.published, isTrue);
    final p = ExamPaper.fromJson({
      'id': 'p', 'exam_id': 'e', 'section_id': 's', 'section_label': '8-A', 'subject_id': 'u', 'subject_name': 'Math', 'exam_date': '2026-11-02',
      'start_time': '09:00:00', 'end_time': '11:00:00', 'room': null, 'total_marks': '100.00', 'passing_marks': '40.00', 'marks_entered': 3, 'student_count': 5,
    });
    expect(p.total, 100.0);
    expect(p.studentCount, 5);
  });

  test('timetable: parseTimeOfDay and slotAt', () {
    expect(parseTimeOfDay('08:30:00'), const TimeOfDay(hour: 8, minute: 30));
    expect(parseTimeOfDay(null), isNull);
    final t = TimetableData.fromJson({
      'periods': [
        {'id': 'p2', 'period_no': 2, 'start_time': '09:00:00', 'end_time': '09:40:00', 'is_break': false, 'label': 'P2'},
        {'id': 'p1', 'period_no': 1, 'start_time': '08:00:00', 'end_time': '08:40:00', 'is_break': false, 'label': 'P1'},
      ],
      'slots': [
        {'id': 's', 'section_id': 'x', 'section_label': '8-A', 'subject_id': 'm', 'subject_name': 'Math', 'teacher_id': 't', 'teacher_name': 'T', 'day_of_week': 1, 'period_id': 'p1'},
      ],
    });
    expect(t.periods.first.periodNo, 1); // sorted
    expect(t.slotAt(1, 'p1')!.subjectName, 'Math');
    expect(t.slotAt(2, 'p1'), isNull);
  });

  test('AttendanceSummary / sheet', () {
    final s = AttendanceSummary.fromJson({'total_days': 20, 'present': 15, 'absent': 3, 'late': 1, 'leave': 1, 'percentage': '88.89'});
    expect(s.percentage, closeTo(88.89, 0.001));
    expect(AttendanceSummary.fromJson({'percentage': null}).percentage, isNull);
    final sheet = AttendanceSheet.fromJson({
      'section_id': 's', 'section_label': '8-A', 'date': '2026-10-28', 'editable': true,
      'rows': [{'student_id': 'a', 'roll_no': '1', 'full_name': 'Ali', 'status': null, 'on_approved_leave': true}],
    });
    expect(sheet.rows.single.status, isNull);
    expect(sheet.rows.single.onApprovedLeave, isTrue);
    expect(attendanceLabel('late'), 'Late');
  });
}
