import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import 'json.dart';

final DateFormat _dmy = DateFormat('dd MMM yyyy');
final DateFormat _dm = DateFormat('dd MMM');
final DateFormat _dmyHm = DateFormat('dd MMM yyyy, hh:mm a');
final NumberFormat _money = NumberFormat('#,##0.##');
final NumberFormat _money2 = NumberFormat('#,##0.00');

String formatDate(DateTime? d) => d == null ? '—' : _dmy.format(d);
String formatDayMonth(DateTime? d) => d == null ? '—' : _dm.format(d);
String formatDateTime(DateTime? d) => d == null ? '—' : _dmyHm.format(d.toLocal());
String formatWeekday(DateTime d) => DateFormat('EEEE').format(d);
String formatMonthYear(DateTime d) => DateFormat('MMMM yyyy').format(d);

/// "PKR 3,500" (whole rupees drop the decimals, anything else keeps two).
String formatMoney(num? v) {
  if (v == null) return 'PKR —';
  final whole = v == v.roundToDouble();
  return 'PKR ${whole ? _money.format(v) : _money2.format(v)}';
}

String formatNumber(num? v, {int decimals = 1}) {
  if (v == null) return '—';
  return v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(decimals);
}

String formatPercent(num? v) => v == null ? '—' : '${formatNumber(v)}%';

/// "08:00 AM" from an API time string ("08:00:00").
String formatTimeStr(String? s) {
  final t = parseTime(s);
  if (t == null) return '—';
  final h = t.hourOfPeriod == 0 ? 12 : t.hourOfPeriod;
  final suffix = t.period == DayPeriod.am ? 'AM' : 'PM';
  return '${h.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')} $suffix';
}

String formatTimeRange(String? start, String? end) => '${formatTimeStr(start)} – ${formatTimeStr(end)}';

String formatTimeOfDay(TimeOfDay t) => formatTimeStr(hhmm(t));

/// "snake_case" -> "Snake case".
String humanize(String s) {
  if (s.isEmpty) return s;
  final t = s.replaceAll('_', ' ');
  return t[0].toUpperCase() + t.substring(1);
}

const List<String> kWeekdayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

/// 1 = Monday … 6 = Saturday (API convention).
String weekdayName(int day) => (day >= 1 && day <= 6) ? kWeekdayNames[day - 1] : 'Day $day';
