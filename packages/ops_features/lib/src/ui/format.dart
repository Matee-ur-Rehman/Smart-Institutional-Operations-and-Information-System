import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

const List<String> weekdayNames = <String>['', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

String fmtDate(DateTime? d) => d == null ? '' : DateFormat('d MMM yyyy').format(d);

String fmtDateTime(DateTime? d) => d == null ? '' : DateFormat('d MMM yyyy, h:mm a').format(d.toLocal());

/// API date format: YYYY-MM-DD.
String ymd(DateTime d) => DateFormat('yyyy-MM-dd').format(d);

String monthKey(DateTime d) => DateFormat('yyyy-MM').format(d);

String monthTitle(DateTime d) => DateFormat('MMMM yyyy').format(d);

/// "Rs 12,500" (decimals only when there are some).
String fmtMoney(double v) => 'Rs ${NumberFormat('#,##0.##').format(v)}';

/// 80 -> "80", 79.5 -> "79.5".
String fmtNum(double? v) {
  if (v == null) return '-';
  return v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);
}

/// "08:30:00" -> "08:30".
String hhmm(String? t) {
  if (t == null || t.isEmpty) return '';
  return t.length >= 5 ? t.substring(0, 5) : t;
}

String timeOfDayToApi(TimeOfDay t) =>
    '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

TimeOfDay? timeOfDayFromApi(String? t) {
  if (t == null || t.length < 5) return null;
  final h = int.tryParse(t.substring(0, 2));
  final m = int.tryParse(t.substring(3, 5));
  if (h == null || m == null) return null;
  return TimeOfDay(hour: h, minute: m);
}

/// "in_review" -> "In review".
String titleCase(String s) {
  if (s.isEmpty) return s;
  final t = s.replaceAll('_', ' ');
  return t[0].toUpperCase() + t.substring(1);
}

Color statusColor(String status) {
  switch (status) {
    case 'published':
    case 'paid':
    case 'resolved':
    case 'results_published':
    case 'pass':
      return Colors.green.shade700;
    case 'overdue':
    case 'urgent':
    case 'high':
    case 'fail':
      return Colors.red.shade700;
    case 'partial':
    case 'in_review':
    case 'important':
    case 'ongoing':
      return Colors.orange.shade800;
    case 'closed':
    case 'archived':
    case 'cancelled':
    case 'draft':
      return Colors.blueGrey.shade600;
    default:
      return Colors.blue.shade700;
  }
}
