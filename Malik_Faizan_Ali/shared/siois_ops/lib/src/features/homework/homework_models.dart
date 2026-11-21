import '../../core/json.dart';

/// `AssignmentOut` from `GET /assignments`.
class Assignment {
  Assignment({
    required this.id,
    required this.teacherName,
    required this.sectionId,
    required this.sectionLabel,
    required this.subjectId,
    required this.subjectName,
    required this.title,
    required this.description,
    required this.assignedDate,
    required this.dueDate,
    required this.maxMarks,
    required this.hasAttachment,
    required this.status,
    required this.isOverdue,
    required this.daysLeft,
  });

  final String id;
  final String teacherName;
  final String sectionId;
  final String sectionLabel;
  final String subjectId;
  final String subjectName;
  final String title;
  final String? description;
  final DateTime assignedDate;
  final DateTime dueDate;
  final double? maxMarks;
  final bool hasAttachment;
  final String status; // draft | published | closed
  final bool isOverdue;
  final int daysLeft;

  factory Assignment.fromJson(Map<String, dynamic> j) => Assignment(
        id: asStr(j['id']),
        teacherName: asStr(j['teacher_name']),
        sectionId: asStr(j['section_id']),
        sectionLabel: asStr(j['section_label']),
        subjectId: asStr(j['subject_id']),
        subjectName: asStr(j['subject_name']),
        title: asStr(j['title']),
        description: asStrN(j['description']),
        assignedDate: asDate(j['assigned_date']),
        dueDate: asDate(j['due_date']),
        maxMarks: asDoubleN(j['max_marks']),
        hasAttachment: asBool(j['has_attachment']),
        status: asStr(j['status'], 'published'),
        isOverdue: asBool(j['is_overdue']),
        daysLeft: asInt(j['days_left']),
      );
}
