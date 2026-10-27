/// Client-side form validation. Every function returns an error message, or null when valid.
/// The server validates again; these exist so the user gets feedback before a network call.
class Validators {
  Validators._();

  static String? required(String? value, [String label = 'This field']) {
    if (value == null || value.trim().isEmpty) return '$label is required';
    return null;
  }

  static String? minLength(String? value, int min, [String label = 'This field']) {
    final missing = required(value, label);
    if (missing != null) return missing;
    if (value!.trim().length < min) return '$label must be at least $min characters';
    return null;
  }

  static String? maxLength(String? value, int max, [String label = 'This field']) {
    if (value != null && value.trim().length > max) return '$label must be at most $max characters';
    return null;
  }

  static double? parseNumber(String? value) {
    if (value == null) return null;
    return double.tryParse(value.trim());
  }

  static bool _tooManyDecimals(String value) {
    final parts = value.trim().split('.');
    return parts.length > 1 && parts[1].length > 2;
  }

  /// Money amount: a number greater than 0 with at most two decimals, optionally capped by [max].
  static String? positiveAmount(String? value, {double? max, String label = 'Amount'}) {
    final missing = required(value, label);
    if (missing != null) return missing;
    final n = parseNumber(value);
    if (n == null) return 'Enter a valid number';
    if (n <= 0) return '$label must be greater than 0';
    if (_tooManyDecimals(value!)) return '$label can have at most 2 decimals';
    if (max != null && n > max) return '$label cannot exceed ${max.toStringAsFixed(2)}';
    return null;
  }

  /// Optional number that, when present, must be greater than 0.
  static String? optionalPositive(String? value, {String label = 'Value'}) {
    if (value == null || value.trim().isEmpty) return null;
    return positiveAmount(value, label: label);
  }

  /// Marks for one student: a number from 0 to [total] (inclusive), at most two decimals.
  static String? marks(String? value, double total) {
    final missing = required(value, 'Marks');
    if (missing != null) return missing;
    final n = parseNumber(value);
    if (n == null) return 'Enter a number';
    if (n < 0) return 'Marks cannot be negative';
    if (n > total) return 'Cannot exceed $total';
    if (_tooManyDecimals(value!)) return 'At most 2 decimals';
    return null;
  }

  static DateTime _day(DateTime d) => DateTime(d.year, d.month, d.day);

  static String? requiredDate(DateTime? value, [String label = 'Date']) {
    if (value == null) return '$label is required';
    return null;
  }

  /// Due dates cannot be in the past (the server rejects them too).
  static String? notPastDate(DateTime? value, {DateTime? today, String label = 'Date'}) {
    if (value == null) return '$label is required';
    final now = _day(today ?? DateTime.now());
    if (_day(value).isBefore(now)) return '$label cannot be in the past';
    return null;
  }

  /// Payment dates cannot be in the future.
  static String? notFutureDate(DateTime? value, {DateTime? today, String label = 'Date'}) {
    if (value == null) return '$label is required';
    final now = _day(today ?? DateTime.now());
    if (_day(value).isAfter(now)) return '$label cannot be in the future';
    return null;
  }

  static String? dateOrder(DateTime? start, DateTime? end) {
    if (start == null || end == null) return null;
    if (_day(end).isBefore(_day(start))) return 'End date cannot be before the start date';
    return null;
  }

  /// Compares two "HH:MM" strings.
  static String? timeOrder(String? start, String? end) {
    if (start == null || end == null) return null;
    if (end.compareTo(start) <= 0) return 'End time must be after the start time';
    return null;
  }
}
