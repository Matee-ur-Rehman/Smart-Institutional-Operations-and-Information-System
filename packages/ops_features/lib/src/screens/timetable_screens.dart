import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

/// Weekly grid: rows are periods, columns are Monday to Saturday.
class WeekGrid extends StatelessWidget {
  const WeekGrid({super.key, required this.week, this.showSection = false, this.showTeacher = true, this.onCellTap});

  final Week week;
  final bool showSection;
  final bool showTeacher;
  final void Function(int day, Period period, Slot? slot)? onCellTap;

  Widget _cell(BuildContext context, String text, {bool bold = false, Color? fill, VoidCallback? onTap, String? sub}) {
    return InkWell(
      onTap: onTap,
      child: Container(
        constraints: const BoxConstraints(minHeight: 58),
        padding: const EdgeInsets.all(6),
        color: fill,
        alignment: Alignment.centerLeft,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(text, style: TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w500, fontSize: 13)),
            if (sub != null && sub.isNotEmpty) Text(sub, style: TextStyle(fontSize: 11, color: Theme.of(context).hintColor)),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (week.periods.isEmpty) {
      return const EmptyView('No periods are defined yet. The admin sets them up under Timetable.');
    }
    final grey = Colors.blueGrey.withAlpha(25);
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Table(
          border: TableBorder.all(color: Colors.black12),
          defaultColumnWidth: const FixedColumnWidth(130),
          columnWidths: const <int, TableColumnWidth>{0: FixedColumnWidth(96)},
          children: [
            TableRow(
              decoration: BoxDecoration(color: Theme.of(context).colorScheme.primary.withAlpha(25)),
              children: [
                _cell(context, 'Period', bold: true),
                for (var d = 1; d <= 6; d++) _cell(context, weekdayNames[d], bold: true),
              ],
            ),
            for (final p in week.periods)
              TableRow(
                children: [
                  _cell(context, p.label, bold: true, fill: grey, sub: '${hhmm(p.startTime)} - ${hhmm(p.endTime)}'),
                  for (var d = 1; d <= 6; d++)
                    if (p.isBreak)
                      _cell(context, 'Break', fill: grey)
                    else
                      Builder(builder: (ctx) {
                        final slot = week.at(d, p.id);
                        final subs = <String>[
                          if (slot != null && showSection) slot.sectionName,
                          if (slot != null && showTeacher) slot.teacherName,
                          if (slot != null && slot.room.isNotEmpty) 'Room ${slot.room}',
                        ];
                        return _cell(
                          ctx,
                          slot?.subjectName ?? (onCellTap != null ? '+' : ''),
                          bold: slot != null,
                          sub: subs.join(' - '),
                          onTap: onCellTap == null ? null : () => onCellTap!(d, p, slot),
                        );
                      }),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// Read-only timetable. [loader] decides whose timetable it is (own, a child's, a section's).
class TimetableViewScreen extends StatefulWidget {
  const TimetableViewScreen({super.key, required this.title, required this.loader, this.showTeacher = true, this.showSection = false});

  final String title;
  final Future<Week> Function(OpsApi api) loader;
  final bool showTeacher;
  final bool showSection;

  @override
  State<TimetableViewScreen> createState() => _TimetableViewScreenState();
}

class _TimetableViewScreenState extends State<TimetableViewScreen> {
  late Future<Week> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.loader(context.read<OpsApi>());
  }

  void _reload() => setState(() => _future = widget.loader(context.read<OpsApi>()));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: FutureView<Week>(
        future: _future,
        onRetry: _reload,
        builder: (ctx, week) => WeekGrid(week: week, showTeacher: widget.showTeacher, showSection: widget.showSection),
      ),
    );
  }
}

/// Admin timetable editor: pick a section, tap an empty cell to add a lesson, tap a lesson to remove it.
/// The teacher is filled in by the server from the teacher assignments.
class AdminTimetableScreen extends StatefulWidget {
  const AdminTimetableScreen({super.key});

  @override
  State<AdminTimetableScreen> createState() => _AdminTimetableScreenState();
}

class _AdminTimetableScreenState extends State<AdminTimetableScreen> {
  late Future<List<SectionItem>> _sectionsFuture;
  String? _sectionId;
  Future<Week>? _weekFuture;

  @override
  void initState() {
    super.initState();
    _sectionsFuture = context.read<OpsApi>().sections();
  }

  void _loadWeek() {
    final id = _sectionId;
    if (id == null) return;
    setState(() => _weekFuture = context.read<OpsApi>().sectionWeek(id));
  }

  Future<void> _cellTap(int day, Period period, Slot? slot) async {
    final api = context.read<OpsApi>();
    if (slot != null) {
      if (!await confirmDialog(context, 'Remove lesson?',
          '${slot.subjectName} on ${weekdayNames[day]}, ${period.label}, will be removed.', yes: 'Remove')) {
        return;
      }
      if (!mounted) return;
      final ok = await runAction(context, () => api.deleteSlot(slot.id), success: 'Lesson removed');
      if (ok) _loadWeek();
      return;
    }
    List<SubjectItem> subjects;
    try {
      subjects = await api.subjects();
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.message, error: true);
      return;
    }
    if (!mounted) return;
    String? subjectId;
    var room = '';
    final saved = await showFormDialog(
      context,
      title: '${weekdayNames[day]} - ${period.label}',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          pickString('Subject', subjectId, [for (final s in subjects) MapEntry(s.id, s.name)], (v) => set(() => subjectId = v)),
          formText('Room (optional)', room, (v) => room = v),
          const Text('The teacher is taken from the teacher assignments for this class and subject.'),
        ]),
      ),
      validate: () => subjectId == null ? 'Choose a subject' : null,
      onSubmit: () => api.createSlot(<String, dynamic>{
        'section_id': _sectionId,
        'subject_id': subjectId,
        'day_of_week': day,
        'period_id': period.id,
        if (room.trim().isNotEmpty) 'room': room.trim(),
      }),
    );
    if (saved) {
      _loadWeek();
      if (mounted) showMessage(context, 'Lesson added');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Timetable'),
        actions: [
          TextButton.icon(
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const PeriodsScreen()));
              if (mounted) _loadWeek();
            },
            icon: const Icon(Icons.schedule),
            label: const Text('Periods'),
          ),
          IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _loadWeek),
        ],
      ),
      body: FutureView<List<SectionItem>>(
        future: _sectionsFuture,
        onRetry: () => setState(() => _sectionsFuture = context.read<OpsApi>().sections()),
        builder: (ctx, sections) => Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: ContentWidth(
                maxWidth: 420,
                child: pickString('Section', _sectionId, [for (final s in sections) MapEntry(s.id, s.display)], (v) {
                  _sectionId = v;
                  _loadWeek();
                }),
              ),
            ),
            Expanded(
              child: _weekFuture == null
                  ? const EmptyView('Choose a section to see and edit its timetable', icon: Icons.calendar_view_week)
                  : FutureView<Week>(
                      future: _weekFuture!,
                      onRetry: _loadWeek,
                      builder: (ctx, week) => WeekGrid(week: week, onCellTap: _cellTap),
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Define the school day: period numbers, timings and breaks.
class PeriodsScreen extends StatefulWidget {
  const PeriodsScreen({super.key});

  @override
  State<PeriodsScreen> createState() => _PeriodsScreenState();
}

class _PeriodsScreenState extends State<PeriodsScreen> {
  late Future<List<Period>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().periods();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().periods());

  Future<void> _add(List<Period> existing) async {
    final api = context.read<OpsApi>();
    var number = '${existing.isEmpty ? 1 : existing.last.periodNo + 1}';
    var label = '';
    String? start;
    String? end;
    var isBreak = false;
    final saved = await showFormDialog(
      context,
      title: 'New period',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Period number', number, (v) => number = v, number: true),
          formText('Label (e.g. Period 1, Break)', label, (v) => label = v),
          TimeField(label: 'Starts', value: start, onChanged: (t) => set(() => start = t)),
          TimeField(label: 'Ends', value: end, onChanged: (t) => set(() => end = t)),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('This is a break'),
            value: isBreak,
            onChanged: (v) => set(() => isBreak = v),
          ),
        ]),
      ),
      validate: () {
        final n = int.tryParse(number.trim());
        if (n == null || n < 1 || n > 20) return 'Period number must be between 1 and 20';
        if (start == null || end == null) return 'Choose the start and end time';
        return Validators.required(label, 'Label') ?? Validators.timeOrder(start, end);
      },
      onSubmit: () => api.createPeriod(<String, dynamic>{
        'period_no': int.parse(number.trim()),
        'label': label.trim(),
        'start_time': start,
        'end_time': end,
        'is_break': isBreak,
      }),
    );
    if (saved) _reload();
  }

  Future<void> _delete(Period p) async {
    if (!await confirmDialog(context, 'Delete period?', '${p.label} will be removed (not possible while lessons use it).', yes: 'Delete')) return;
    if (!mounted) return;
    final ok = await runAction(context, () => context.read<OpsApi>().deletePeriod(p.id), success: 'Period deleted');
    if (ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('School day periods')),
      body: ContentWidth(
        maxWidth: 700,
        child: FutureView<List<Period>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, periods) => Column(
            children: [
              Expanded(
                child: periods.isEmpty
                    ? const EmptyView('No periods yet')
                    : ListView(
                        children: [
                          for (final p in periods)
                            ListTile(
                              leading: CircleAvatar(child: Text('${p.periodNo}')),
                              title: Text(p.label),
                              subtitle: Text('${hhmm(p.startTime)} - ${hhmm(p.endTime)}${p.isBreak ? '  (break)' : ''}'),
                              trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(p)),
                            ),
                        ],
                      ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: FilledButton.icon(onPressed: () => _add(periods), icon: const Icon(Icons.add), label: const Text('Add period')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
