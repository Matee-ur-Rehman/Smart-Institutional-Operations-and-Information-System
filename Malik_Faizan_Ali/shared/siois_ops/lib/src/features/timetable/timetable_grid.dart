import 'package:flutter/material.dart';

import '../../core/format.dart';
import '../../core/theme.dart';
import 'timetable_models.dart';

/// Weekly grid: one row per period, one column per day (Mon-Sat). Scrolls sideways on small screens.
/// [subtitle] picks the second line of a lesson cell (teacher name for classes, class label for a teacher).
class TimetableGrid extends StatelessWidget {
  const TimetableGrid({super.key, required this.data, this.subtitle, this.onCellTap});
  final TimetableData data;
  final String Function(Slot slot)? subtitle;

  /// Called with (day, period, slot-or-null) when a lesson cell is tapped (admin editing).
  final void Function(int day, Period period, Slot? slot)? onCellTap;

  static const double _cellW = 128;
  static const double _timeW = 92;

  @override
  Widget build(BuildContext context) {
    if (data.periods.isEmpty) {
      return const Center(child: Text('No periods are defined yet.', style: TextStyle(color: Brand.muted)));
    }
    final header = Row(children: [
      const SizedBox(width: _timeW),
      for (var d = 1; d <= 6; d++)
        SizedBox(width: _cellW, child: Padding(padding: const EdgeInsets.all(6), child: Text(weekdayName(d), style: const TextStyle(fontWeight: FontWeight.w700)))),
    ]);
    final rows = <Widget>[];
    for (final p in data.periods) {
      rows.add(IntrinsicHeight(child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(
          width: _timeW,
          child: Padding(
            padding: const EdgeInsets.all(6),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(p.label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5)),
              Text(formatTimeRange(p.start, p.end), style: const TextStyle(color: Brand.muted, fontSize: 11)),
            ]),
          ),
        ),
        for (var d = 1; d <= 6; d++) _cell(context, d, p),
      ])));
    }
    return SingleChildScrollView(
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [header, ...rows]),
      ),
    );
  }

  Widget _cell(BuildContext context, int day, Period p) {
    if (p.isBreak) {
      return Container(
        width: _cellW,
        height: 46,
        margin: const EdgeInsets.all(2),
        alignment: Alignment.center,
        decoration: BoxDecoration(color: Brand.surfaceTint, borderRadius: BorderRadius.circular(8)),
        child: Text(p.label, style: const TextStyle(color: Brand.muted, fontSize: 12)),
      );
    }
    final slot = data.slotAt(day, p.id);
    final child = slot == null
        ? Center(child: Icon(onCellTap == null ? null : Icons.add, size: 16, color: Brand.muted))
        : Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
            Text(slot.subjectName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5), maxLines: 1, overflow: TextOverflow.ellipsis),
            if (subtitle != null) Text(subtitle!(slot), style: const TextStyle(color: Brand.muted, fontSize: 11), maxLines: 1, overflow: TextOverflow.ellipsis),
            if ((slot.room ?? '').isNotEmpty) Text('Room ${slot.room}', style: const TextStyle(color: Brand.muted, fontSize: 11)),
          ]);
    return InkWell(
      onTap: onCellTap == null ? null : () => onCellTap!(day, p, slot),
      borderRadius: BorderRadius.circular(8),
      child: Container(
        width: _cellW,
        height: 64,
        margin: const EdgeInsets.all(2),
        padding: const EdgeInsets.all(6),
        decoration: BoxDecoration(
          color: slot == null ? Colors.white : Brand.primary.withValues(alpha: 0.08),
          border: Border.all(color: slot == null ? const Color(0xFFE2E8F0) : Brand.primary.withValues(alpha: 0.35)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: child,
      ),
    );
  }
}
