import 'package:flutter/material.dart';

import '../../core/json.dart';
import '../../core/theme.dart';

const List<MapEntry<String, String>> kExamTypes = <MapEntry<String, String>>[
  MapEntry('monthly', 'Monthly test'),
  MapEntry('midterm', 'Mid-term'),
  MapEntry('final', 'Final'),
  MapEntry('other', 'Other'),
];

Color examStatusColor(String s) {
  switch (s) {
    case 'results_published':
      return Brand.success;
    case 'ongoing':
    case 'scheduled':
      return Brand.info;
    case 'completed':
      return Brand.warning;
    default:
      return Brand.muted;
  }
}

class Exam {
  Exam({required this.id, required this.name, required this.examType, required this.start, required this.end, required this.status, required this.scheduleCount});
  final String id;
  final String name;
  final String examType;
  final DateTime start;
  final DateTime end;
  final String status;
  final int scheduleCount;
  bool get published => status == 'results_published';
  factory Exam.fromJson(Map<String, dynamic> j) => Exam(
      id: asStr(j['id']),
      name: asStr(j['name']),
      examType: asStr(j['exam_type']),
      start: asDate(j['start_date']),
      end: asDate(j['end_date']),
      status: asStr(j['status']),
      scheduleCount: asInt(j['schedule_count']));
}

class ExamPaper {
  ExamPaper({required this.id, required this.examId, required this.sectionId, required this.sectionLabel, required this.subjectId, required this.subjectName, required this.date, required this.start, required this.end, required this.room, required this.total, required this.passing, this.marksEntered, this.studentCount});
  final String id;
  final String examId;
  final String sectionId;
  final String sectionLabel;
  final String subjectId;
  final String subjectName;
  final DateTime date;
  final String start;
  final String end;
  final String? room;
  final double total;
  final double passing;
  final int? marksEntered;
  final int? studentCount;
  factory ExamPaper.fromJson(Map<String, dynamic> j) => ExamPaper(
      id: asStr(j['id']),
      examId: asStr(j['exam_id']),
      sectionId: asStr(j['section_id']),
      sectionLabel: asStr(j['section_label']),
      subjectId: asStr(j['subject_id']),
      subjectName: asStr(j['subject_name']),
      date: asDate(j['exam_date']),
      start: asStr(j['start_time']),
      end: asStr(j['end_time']),
      room: asStrN(j['room']),
      total: asDouble(j['total_marks']),
      passing: asDouble(j['passing_marks']),
      marksEntered: j['marks_entered'] == null ? null : asInt(j['marks_entered']),
      studentCount: j['student_count'] == null ? null : asInt(j['student_count']));
}
