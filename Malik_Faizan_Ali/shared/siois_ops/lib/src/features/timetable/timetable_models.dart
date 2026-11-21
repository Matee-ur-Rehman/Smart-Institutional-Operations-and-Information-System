import 'package:flutter/material.dart';

import '../../core/json.dart';

TimeOfDay? parseTimeOfDay(String? s) {
  if (s == null || s.length < 4) return null;
  final p = s.split(':');
  final h = int.tryParse(p[0]);
  final m = p.length > 1 ? int.tryParse(p[1]) : 0;
  if (h == null || m == null) return null;
  return TimeOfDay(hour: h, minute: m);
}

class Period {
  Period({required this.id, required this.periodNo, required this.start, required this.end, required this.isBreak, required this.label});
  final String id;
  final int periodNo;
  final String start;
  final String end;
  final bool isBreak;
  final String label;
  factory Period.fromJson(Map<String, dynamic> j) => Period(
      id: asStr(j['id']),
      periodNo: asInt(j['period_no']),
      start: asStr(j['start_time']),
      end: asStr(j['end_time']),
      isBreak: asBool(j['is_break']),
      label: asStr(j['label']));
}

class Slot {
  Slot({required this.id, required this.sectionId, required this.sectionLabel, required this.subjectId, required this.subjectName, required this.teacherId, required this.teacherName, required this.day, required this.periodId, required this.room});
  final String id;
  final String sectionId;
  final String sectionLabel;
  final String subjectId;
  final String subjectName;
  final String teacherId;
  final String teacherName;
  final int day; // 1 = Monday ... 6 = Saturday
  final String periodId;
  final String? room;
  factory Slot.fromJson(Map<String, dynamic> j) => Slot(
      id: asStr(j['id']),
      sectionId: asStr(j['section_id']),
      sectionLabel: asStr(j['section_label']),
      subjectId: asStr(j['subject_id']),
      subjectName: asStr(j['subject_name']),
      teacherId: asStr(j['teacher_id']),
      teacherName: asStr(j['teacher_name']),
      day: asInt(j['day_of_week']),
      periodId: asStr(j['period_id']),
      room: asStrN(j['room']));
}

class TimetableData {
  TimetableData({required this.periods, required this.slots});
  final List<Period> periods;
  final List<Slot> slots;
  factory TimetableData.fromJson(dynamic json) {
    final m = asMap(json);
    return TimetableData(
      periods: asMapList(m['periods']).map(Period.fromJson).toList()..sort((a, b) => a.periodNo.compareTo(b.periodNo)),
      slots: asMapList(m['slots']).map(Slot.fromJson).toList(),
    );
  }
  Slot? slotAt(int day, String periodId) {
    for (final s in slots) {
      if (s.day == day && s.periodId == periodId) return s;
    }
    return null;
  }
}
