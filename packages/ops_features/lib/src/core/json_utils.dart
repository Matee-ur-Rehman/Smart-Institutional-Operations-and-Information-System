

String jStr(dynamic v, [String fallback = '']) => v == null ? fallback : v.toString();

String? jStrN(dynamic v) => v?.toString();

double jNum(dynamic v, [double fallback = 0]) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? fallback;
  return fallback;
}

double? jNumN(dynamic v) {
  if (v == null) return null;
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v);
  return null;
}

int jInt(dynamic v, [int fallback = 0]) {
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}

bool jBool(dynamic v, [bool fallback = false]) => v is bool ? v : fallback;

DateTime? jDateN(dynamic v) {
  if (v == null) return null;
  return DateTime.tryParse(v.toString());
}

DateTime jDate(dynamic v) => jDateN(v) ?? DateTime.fromMillisecondsSinceEpoch(0);

/// Accepts a plain JSON list or a `{items: [...]}` page and returns the list.
List<dynamic> jList(dynamic v) {
  if (v is List) return v;
  if (v is Map && v['items'] is List) return v['items'] as List<dynamic>;
  return const <dynamic>[];
}

Map<String, dynamic> jMap(dynamic v) {
  if (v is Map) return Map<String, dynamic>.from(v);
  return <String, dynamic>{};
}

List<T> jMapList<T>(dynamic v, T Function(Map<String, dynamic>) build) {
  return jList(v).whereType<Map>().map((e) => build(Map<String, dynamic>.from(e))).toList();
}

Map<String, int> jIntMap(dynamic v) {
  final out = <String, int>{};
  if (v is Map) {
    v.forEach((key, value) => out[key.toString()] = jInt(value));
  }
  return out;
}
