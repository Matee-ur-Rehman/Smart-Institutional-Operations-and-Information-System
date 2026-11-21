import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/quick_form.dart';
import '../timetable/timetable_models.dart' show parseTimeOfDay;

const List<MapEntry<String, String>> _kTypes = <MapEntry<String, String>>[
  MapEntry('holiday', 'Holiday'),
  MapEntry('exam', 'Exam'),
  MapEntry('meeting', 'Meeting'),
  MapEntry('sports', 'Sports'),
  MapEntry('activity', 'Activity'),
  MapEntry('other', 'Other'),
];
const List<MapEntry<String, String>> _kAudiences = <MapEntry<String, String>>[
  MapEntry('all', 'Everyone'),
  MapEntry('teachers', 'Teachers'),
  MapEntry('students', 'Students'),
  MapEntry('parents', 'Parents'),
  MapEntry('class', 'A specific section'),
];

Color eventColor(String type) {
  switch (type) {
    case 'holiday':
      return Brand.danger;
    case 'exam':
      return Brand.warning;
    case 'meeting':
      return Brand.info;
    case 'sports':
      return Brand.success;
    default:
      return Brand.primary;
  }
}

class _Event {
  _Event(this.json);
  final Map<String, dynamic> json;
  String get id => asStr(json['id']);
  String get title => asStr(json['title']);
  String? get description => asStrN(json['description']);
  String get type => asStr(json['event_type'], 'other');
  DateTime get start => asDate(json['start_date']);
  DateTime get end => asDate(json['end_date'], start);
  String? get startTime => asStrN(json['start_time']);
  String? get endTime => asStrN(json['end_time']);
  String? get location => asStrN(json['location']);
  String get audience => asStr(json['audience'], 'all');
  String get audienceLabel => asStr(json['audience_label']);
  String? get sectionId => asStrN(json['section_id']);
}

/// Month view of school events (holidays, exams, meetings...). Holidays also block attendance marking.
class CalendarPage extends StatefulWidget {
  const CalendarPage({super.key, required this.isAdmin});
  final bool isAdmin;
  @override
  State<CalendarPage> createState() => _CalendarPageState();
}

class _CalendarPageState extends State<CalendarPage> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  int _rev = 0;

  String get _monthKey => '${_month.year.toString().padLeft(4, '0')}-${_month.month.toString().padLeft(2, '0')}';

  void _shift(int delta) => setState(() => _month = DateTime(_month.year, _month.month + delta));

  Future<void> _form({_Event? event}) async {
    final api = context.read<ApiClient>();
    final List<SectionRef> sections;
    try {
      sections = await context.read<Lookups>().sections(all: true);
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: event == null ? 'New event' : 'Edit event',
      width: 600,
      builder: (_) => QuickForm(
        fields: [
          QField('title', 'Title', QType.text, required: true, initial: event?.title),
          QField('event_type', 'Type', QType.dropdown, required: true, initial: event?.type ?? 'other', options: _kTypes),
          QField('start_date', 'Starts on', QType.date, required: true, initial: event?.start ?? dateOnly(DateTime.now())),
          QField('end_date', 'Ends on (optional)', QType.date, clearable: true, initial: event == null || event.end == event.start ? null : event.end),
          QField('start_time', 'Start time (optional)', QType.time, initial: parseTimeOfDay(event?.startTime)),
          QField('end_time', 'End time (optional)', QType.time, initial: parseTimeOfDay(event?.endTime)),
          QField('location', 'Location (optional)', QType.text, initial: event?.location),
          QField('description', 'Details (optional)', QType.multiline, initial: event?.description),
          QField('audience', 'Audience', QType.dropdown, required: true, initial: event?.audience ?? 'all', options: _kAudiences),
          QField('section_id', 'Section (only for "specific section")', QType.dropdown, clearable: true, initial: event?.sectionId, options: sections.map((s) => MapEntry(s.id, s.label)).toList()),
          if (event == null) const QField('notify', 'Notify the audience', QType.toggle, initial: true),
        ],
        onSubmit: (v) {
          final audience = v['audience'] as String;
          final sectionId = audience == 'class' ? v['section_id'] : null;
          if (audience == 'class' && sectionId == null) {
            throw ApiException(422, 'validation_error', 'Please choose a section', fieldErrors: const [FieldError('section_id', 'Choose the section')]);
          }
          final start = v['start_date'] as DateTime;
          final end = v['end_date'] as DateTime?;
          if (end != null && end.isBefore(start)) {
            throw ApiException(422, 'validation_error', 'Please correct the dates', fieldErrors: const [FieldError('end_date', 'The end date cannot be before the start date')]);
          }
          String? t(dynamic x) => x == null ? null : hhmm(x as TimeOfDay);
          String? s(dynamic x) => (x as String).isEmpty ? null : x;
          final body = <String, dynamic>{
            'title': v['title'],
            'event_type': v['event_type'],
            'start_date': isoDate(start),
            'end_date': end == null ? isoDate(start) : isoDate(end),
            'start_time': t(v['start_time']),
            'end_time': t(v['end_time']),
            'location': s(v['location']),
            'description': s(v['description']),
            'audience': audience,
            'section_id': sectionId,
            if (event == null) 'notify': v['notify'],
          };
          return event == null ? api.post('/events', body: body) : api.patch('/events/${event.id}', body: body);
        },
      ),
    );
    if (ok == true) setState(() => _rev++);
  }

  Future<void> _delete(_Event e) async {
    final ok = await confirmDialog(context, title: 'Delete "${e.title}"?', message: 'The event is removed from everyone\'s calendar.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/events/${e.id}');
      if (mounted) setState(() => _rev++);
    } catch (err) {
      if (mounted) showError(context, err);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return PageFrame(
      title: 'Calendar',
      subtitle: 'Holidays, exams and school events',
      actions: [if (widget.isAdmin) FilledButton.icon(onPressed: () => _form(), icon: const Icon(Icons.add), label: const Text('New event'))],
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          IconButton(tooltip: 'Previous month', onPressed: () => _shift(-1), icon: const Icon(Icons.chevron_left)),
          SizedBox(width: 180, child: Text(formatMonthYear(_month), textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17))),
          IconButton(tooltip: 'Next month', onPressed: () => _shift(1), icon: const Icon(Icons.chevron_right)),
          TextButton(onPressed: () => setState(() => _month = DateTime(DateTime.now().year, DateTime.now().month)), child: const Text('Today')),
        ]),
        const SizedBox(height: 8),
        Expanded(
          child: AsyncView<List<_Event>>(
            loadKey: '$_monthKey|$_rev',
            loader: () async => asMapList(asMap(await api.get('/events', query: {'month': _monthKey, 'page_size': 100}))['items']).map(_Event.new).toList(),
            builder: (context, events, reload) {
              if (events.isEmpty) return const EmptyState(icon: Icons.event_available_outlined, title: 'No events this month');
              return ListView.separated(
                itemCount: events.length,
                separatorBuilder: (context, i) => const SizedBox(height: 8),
                itemBuilder: (context, i) {
                  final e = events[i];
                  final c = eventColor(e.type);
                  final multi = e.end != e.start;
                  return AppCard(
                    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Container(
                        width: 58,
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(10)),
                        child: Column(children: [
                          Text(e.start.day.toString().padLeft(2, '0'), style: TextStyle(fontWeight: FontWeight.w800, fontSize: 20, color: c)),
                          Text(formatDayMonth(e.start).substring(3), style: TextStyle(color: c, fontSize: 12)),
                        ]),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Row(children: [
                            Flexible(child: Text(e.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                            const SizedBox(width: 8),
                            StatusChip(e.type, color: c),
                          ]),
                          Text(
                            [
                              if (multi) '${formatDayMonth(e.start)} – ${formatDayMonth(e.end)}' else formatWeekday(e.start),
                              if (e.startTime != null) formatTimeRange(e.startTime, e.endTime ?? e.startTime),
                              if ((e.location ?? '').isNotEmpty) e.location!,
                              e.audienceLabel,
                            ].join(' · '),
                            style: const TextStyle(color: Brand.muted, fontSize: 12.5),
                          ),
                          if ((e.description ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 6), child: Text(e.description!)),
                        ]),
                      ),
                      if (widget.isAdmin)
                        PopupMenuButton<String>(
                          onSelected: (v) {
                            if (v == 'edit') _form(event: e);
                            if (v == 'delete') _delete(e);
                          },
                          itemBuilder: (_) => const [PopupMenuItem(value: 'edit', child: Text('Edit')), PopupMenuItem(value: 'delete', child: Text('Delete'))],
                        ),
                    ]),
                  );
                },
              );
            },
          ),
        ),
      ]),
    );
  }
}
