import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:siois_ops/src/core/format.dart';
import 'package:siois_ops/src/core/json.dart';

// Pure-logic tests. NOT executed in the environment that produced them (no Flutter SDK there).
void main() {
  group('json readers', () {
    test('accept pydantic Decimal strings', () {
      expect(asDouble('3500.00'), 3500.0);
      expect(asDoubleN('12.5'), 12.5);
      expect(asDoubleN(null), isNull);
      expect(asDouble('abc', 7), 7);
    });
    test('asInt / asBool / asStr', () {
      expect(asInt('42'), 42);
      expect(asInt(3.9), 3);
      expect(asInt(null, 5), 5);
      expect(asBool('true'), isTrue);
      expect(asBool(null, true), isTrue);
      expect(asStr(null, 'x'), 'x');
      expect(asStrN(12), '12');
    });
    test('asMap / asMapList tolerate wrong types', () {
      expect(asMap('nope'), isEmpty);
      expect(asMapList({'a': 1}), isEmpty);
      expect(asMapList([{'a': 1}, 'skip']).length, 1);
    });
    test('dates', () {
      expect(isoDate(DateTime(2026, 3, 5)), '2026-03-05');
      expect(asDateN('2026-10-28')!.day, 28);
      expect(asDateN('not a date'), isNull);
      expect(dateOnly(DateTime(2026, 1, 2, 13, 45)), DateTime(2026, 1, 2));
      expect(hhmm(const TimeOfDay(hour: 8, minute: 5)), '08:05');
      expect(parseTime('14:30:00'), const TimeOfDay(hour: 14, minute: 30));
      expect(parseTime('x'), isNull);
    });
    test('PageResult parses the API page envelope', () {
      final p = PageResult<String>.fromJson({'items': [{'n': 'a'}, {'n': 'b'}], 'total': 45, 'page': 2, 'page_size': 20}, (m) => m['n'] as String);
      expect(p.items, ['a', 'b']);
      expect(p.total, 45);
      expect(p.hasMore, isTrue);
      expect(PageResult<String>.fromJson(null, (m) => '').items, isEmpty);
    });
  });

  group('formatting', () {
    test('money', () {
      expect(formatMoney(3500), 'PKR 3,500');
      expect(formatMoney(3500.5), 'PKR 3,500.50');
      expect(formatMoney(null), 'PKR —');
    });
    test('numbers and percent', () {
      expect(formatNumber(45), '45');
      expect(formatNumber(45.5), '45.5');
      expect(formatNumber(null), '—');
      expect(formatPercent(80), '80%');
    });
    test('time strings', () {
      expect(formatTimeStr('08:00:00'), '08:00 AM');
      expect(formatTimeStr('13:05'), '01:05 PM');
      expect(formatTimeStr('00:15'), '12:15 AM');
      expect(formatTimeStr(null), '—');
    });
    test('humanize / weekday names', () {
      expect(humanize('in_review'), 'In review');
      expect(humanize(''), '');
      expect(weekdayName(1), 'Monday');
      expect(weekdayName(6), 'Saturday');
      expect(weekdayName(7), 'Day 7');
    });
  });
}
