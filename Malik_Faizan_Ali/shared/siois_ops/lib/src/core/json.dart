import 'package:flutter/material.dart';

/// Defensive JSON readers. Note: pydantic v2 serialises Decimal as a *string* ("3500.00"),
/// so every numeric reader accepts num or String.
String asStr(dynamic v, [String def = '']) => v == null ? def : v.toString();
String? asStrN(dynamic v) => v?.toString();

int asInt(dynamic v, [int def = 0]) {
  if (v is int) return v;
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? double.tryParse(v)?.toInt() ?? def;
  return def;
}

double asDouble(dynamic v, [double def = 0]) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? def;
  return def;
}

double? asDoubleN(dynamic v) {
  if (v == null) return null;
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v);
  return null;
}

bool asBool(dynamic v, [bool def = false]) {
  if (v is bool) return v;
  if (v is String) return v.toLowerCase() == 'true';
  return def;
}

DateTime? asDateN(dynamic v) => v == null ? null : DateTime.tryParse(v.toString());
DateTime asDate(dynamic v, [DateTime? def]) => asDateN(v) ?? def ?? DateTime.fromMillisecondsSinceEpoch(0);

Map<String, dynamic> asMap(dynamic v) =>
    v is Map ? v.map((k, val) => MapEntry(k.toString(), val)) : <String, dynamic>{};

List<Map<String, dynamic>> asMapList(dynamic v) =>
    v is List ? v.whereType<Map>().map((m) => asMap(m)).toList() : <Map<String, dynamic>>[];

/// `YYYY-MM-DD` (what the API expects for dates).
String isoDate(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// `HH:MM` (what the API expects for times).
String hhmm(TimeOfDay t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';

/// Parses `HH:MM` or `HH:MM:SS` from the API.
TimeOfDay? parseTime(String? s) {
  if (s == null || s.length < 4) return null;
  final parts = s.split(':');
  if (parts.length < 2) return null;
  final h = int.tryParse(parts[0]);
  final m = int.tryParse(parts[1]);
  if (h == null || m == null) return null;
  return TimeOfDay(hour: h, minute: m);
}

DateTime dateOnly(DateTime d) => DateTime(d.year, d.month, d.day);

/// A paginated response: `{items, total, page, page_size}`.
class PageResult<T> {
  PageResult({required this.items, required this.total, required this.page, required this.pageSize});

  final List<T> items;
  final int total;
  final int page;
  final int pageSize;

  bool get hasMore => page * pageSize < total;

  factory PageResult.fromJson(dynamic json, T Function(Map<String, dynamic>) parse) {
    final m = asMap(json);
    return PageResult<T>(
      items: asMapList(m['items']).map(parse).toList(),
      total: asInt(m['total']),
      page: asInt(m['page'], 1),
      pageSize: asInt(m['page_size'], 20),
    );
  }
}
