import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

IconData _eventIcon(String type) {
  switch (type) {
    case 'holiday':
      return Icons.beach_access_outlined;
    case 'exam':
      return Icons.edit_note;
    case 'meeting':
      return Icons.groups_outlined;
    case 'sports':
      return Icons.sports_soccer_outlined;
    case 'activity':
      return Icons.celebration_outlined;
    default:
      return Icons.event_outlined;
  }
}

/// School calendar, one month at a time. Everyone reads; the admin ([canManage]) adds and deletes events.
class CalendarScreen extends StatefulWidget {
  const CalendarScreen({super.key, this.canManage = false});

  final bool canManage;

  @override
  State<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends State<CalendarScreen> {
  late DateTime _month;
  late Future<Paged<EventItem>> _future;

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _month = DateTime(now.year, now.month);
    _future = _load();
  }

  Future<Paged<EventItem>> _load() => context.read<OpsApi>().events(month: monthKey(_month));

  void _reload() => setState(() => _future = _load());

  void _shift(int delta) {
    _month = DateTime(_month.year, _month.month + delta);
    _reload();
  }

  Future<void> _create() async {
    final api = context.read<OpsApi>();
    List<SectionItem> sections;
    try {
      sections = await api.sections();
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.message, error: true);
      return;
    }
    if (!mounted) return;
    var title = '';
    var description = '';
    var location = '';
    var type = 'activity';
    var audience = 'all';
    var notify = true;
    DateTime? start;
    DateTime? end;
    String? startTime;
    String? endTime;
    String? sectionId;

    final saved = await showFormDialog(
      context,
      title: 'New event',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Title', title, (v) => title = v),
          pickString('Type', type, const [
            MapEntry('holiday', 'Holiday'),
            MapEntry('exam', 'Exam'),
            MapEntry('meeting', 'Meeting'),
            MapEntry('sports', 'Sports'),
            MapEntry('activity', 'Activity'),
            MapEntry('other', 'Other'),
          ], (v) => set(() => type = v ?? type)),
          DateField(label: 'Start date', value: start, onChanged: (d) => set(() => start = d)),
          DateField(label: 'End date (optional)', value: end, onChanged: (d) => set(() => end = d)),
          TimeField(label: 'Start time (optional)', value: startTime, onChanged: (t) => set(() => startTime = t)),
          TimeField(label: 'End time (optional)', value: endTime, onChanged: (t) => set(() => endTime = t)),
          formText('Location (optional)', location, (v) => location = v),
          formText('Details (optional)', description, (v) => description = v, maxLines: 3),
          pickString('Who is it for?', audience, const [
            MapEntry('all', 'Everyone'),
            MapEntry('teachers', 'Teachers'),
            MapEntry('students', 'Students'),
            MapEntry('parents', 'Parents'),
            MapEntry('class', 'One class section'),
          ], (v) => set(() => audience = v ?? audience)),
          if (audience == 'class')
            pickString('Section', sectionId, [for (final s in sections) MapEntry(s.id, s.display)],
                (v) => set(() => sectionId = v)),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Notify people'),
            value: notify,
            onChanged: (v) => set(() => notify = v),
          ),
        ]),
      ),
      validate: () {
        if (audience == 'class' && sectionId == null) return 'Choose a section';
        return Validators.minLength(title, 3, 'Title') ??
            Validators.requiredDate(start, 'Start date') ??
            Validators.dateOrder(start, end) ??
            (end == null || end == start ? Validators.timeOrder(startTime, endTime) : null);
      },
      onSubmit: () => api.createEvent(<String, dynamic>{
        'title': title.trim(),
        'event_type': type,
        'start_date': ymd(start!),
        if (end != null) 'end_date': ymd(end!),
        if (startTime != null) 'start_time': startTime,
        if (endTime != null) 'end_time': endTime,
        if (location.trim().isNotEmpty) 'location': location.trim(),
        if (description.trim().isNotEmpty) 'description': description.trim(),
        'audience': audience,
        if (audience == 'class') 'section_id': sectionId,
        'notify': notify,
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Event added');
    }
  }

  Future<void> _delete(EventItem e) async {
    if (!await confirmDialog(context, 'Delete event?', '"${e.title}" will be removed from the calendar.', yes: 'Delete')) return;
    if (!mounted) return;
    final ok = await runAction(context, () => context.read<OpsApi>().deleteEvent(e.id), success: 'Event deleted');
    if (ok) _reload();
  }

  String _when(EventItem e) {
    final sameDay = e.startDate == e.endDate;
    final days = sameDay ? fmtDate(e.startDate) : '${fmtDate(e.startDate)} - ${fmtDate(e.endDate)}';
    final time = e.startTime == null ? '' : '  ${hhmm(e.startTime)}${e.endTime == null ? '' : ' - ${hhmm(e.endTime)}'}';
    return '$days$time';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('School calendar'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      floatingActionButton: widget.canManage
          ? FloatingActionButton.extended(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New event'))
          : null,
      body: ContentWidth(
        child: Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(icon: const Icon(Icons.chevron_left), onPressed: () => _shift(-1)),
                SizedBox(
                  width: 180,
                  child: Text(monthTitle(_month), textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                ),
                IconButton(icon: const Icon(Icons.chevron_right), onPressed: () => _shift(1)),
              ],
            ),
            Expanded(
              child: FutureView<Paged<EventItem>>(
                future: _future,
                onRetry: _reload,
                builder: (ctx, page) {
                  if (page.items.isEmpty) return const EmptyView('No events this month', icon: Icons.event_available_outlined);
                  return ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 88),
                    itemCount: page.items.length,
                    itemBuilder: (ctx, i) {
                      final e = page.items[i];
                      return Card(
                        child: ListTile(
                          leading: Icon(_eventIcon(e.eventType)),
                          title: Text(e.title, style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Text([
                            _when(e),
                            if (e.location.isNotEmpty) e.location,
                            if (e.description.isNotEmpty) e.description,
                          ].join('\n')),
                          isThreeLine: e.location.isNotEmpty || e.description.isNotEmpty,
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              StatusChip(e.eventType),
                              if (widget.canManage)
                                IconButton(tooltip: 'Delete', icon: const Icon(Icons.delete_outline), onPressed: () => _delete(e)),
                            ],
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
