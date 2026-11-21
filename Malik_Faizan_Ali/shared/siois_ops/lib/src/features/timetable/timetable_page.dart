import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/auth.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/quick_form.dart';
import '../common/report_download.dart';
import '../dashboard/role_scope.dart';
import 'timetable_grid.dart';
import 'timetable_models.dart';

class TimetablePage extends StatelessWidget {
  const TimetablePage({super.key, required this.role});
  final Role role;

  @override
  Widget build(BuildContext context) {
    switch (role) {
      case Role.student:
        return PageFrame(title: 'Timetable', subtitle: 'Your weekly timetable', child: const _OwnTimetable(showTeacher: true));
      case Role.parent:
        return PageFrame(
          title: 'Timetable',
          subtitle: 'Weekly timetable of your child',
          child: StudentScope(builder: (context, c) => _ParentTimetable(child: c)),
        );
      case Role.teacher:
        return PageFrame(
          title: 'Timetable',
          subtitle: 'Your lessons and class timetables',
          child: DefaultTabController(
            length: 2,
            child: Column(children: const [
              Align(alignment: Alignment.centerLeft, child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [Tab(text: 'My timetable'), Tab(text: 'Class timetable')])),
              SizedBox(height: 12),
              Expanded(child: TabBarView(children: [_OwnTimetable(showTeacher: false), _SectionTimetable(editable: false)])),
            ]),
          ),
        );
      case Role.admin:
        return PageFrame(
          title: 'Timetable',
          subtitle: 'Build class timetables and define periods',
          child: DefaultTabController(
            length: 2,
            child: Column(children: const [
              Align(alignment: Alignment.centerLeft, child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [Tab(text: 'Class timetable'), Tab(text: 'Periods')])),
              SizedBox(height: 12),
              Expanded(child: TabBarView(children: [_SectionTimetable(editable: true), _PeriodsTab()])),
            ]),
          ),
        );
    }
  }
}

// ================================================================== student / teacher: /timetable/me
class _OwnTimetable extends StatelessWidget {
  const _OwnTimetable({required this.showTeacher});
  final bool showTeacher;

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<TimetableData>(
      loader: () async => TimetableData.fromJson(await api.get('/timetable/me')),
      builder: (context, data, reload) => data.slots.isEmpty
          ? const EmptyState(icon: Icons.calendar_view_week_outlined, title: 'No timetable yet', message: 'The timetable has not been set up for this year.')
          : TimetableGrid(data: data, subtitle: (s) => showTeacher ? s.teacherName : s.sectionLabel),
    );
  }
}

class _ParentTimetable extends StatelessWidget {
  const _ParentTimetable({required this.child});
  final ChildRef child;

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Align(alignment: Alignment.centerRight, child: ReportButton(label: 'Download PDF', path: '/reports/timetable/${child.sectionId}', fallbackName: 'timetable.pdf')),
      const SizedBox(height: 8),
      Expanded(
        child: AsyncView<TimetableData>(
          loader: () async => TimetableData.fromJson(await api.get('/timetable/students/${child.studentId}')),
          builder: (context, data, reload) => data.slots.isEmpty
              ? const EmptyState(icon: Icons.calendar_view_week_outlined, title: 'No timetable yet')
              : TimetableGrid(data: data, subtitle: (s) => s.teacherName),
        ),
      ),
    ]);
  }
}

// ================================================================== class timetable (admin edit / teacher view)
class _SectionTimetable extends StatefulWidget {
  const _SectionTimetable({required this.editable});
  final bool editable;
  @override
  State<_SectionTimetable> createState() => _SectionTimetableState();
}

class _SectionTimetableState extends State<_SectionTimetable> with AutomaticKeepAliveClientMixin {
  late Future<List<SectionRef>> _sections;
  String? _sectionId;
  int _version = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections(all: true);
  }

  Future<void> _cellTapped(int day, Period period, Slot? slot) async {
    if (slot == null) {
      await _slotForm(day, period);
      return;
    }
    final action = await showDialog<String>(
      context: context,
      builder: (ctx) => SimpleDialog(title: Text('${weekdayName(day)} · ${period.label}'), children: [
        SimpleDialogOption(onPressed: () => Navigator.pop(ctx, 'edit'), child: const Text('Change lesson')),
        SimpleDialogOption(onPressed: () => Navigator.pop(ctx, 'delete'), child: const Text('Remove lesson', style: TextStyle(color: Brand.danger))),
      ]),
    );
    if (!mounted || action == null) return;
    if (action == 'edit') {
      await _slotForm(day, period, slot: slot);
    } else {
      try {
        await context.read<ApiClient>().delete('/timetable-slots/${slot.id}');
        setState(() => _version++);
      } catch (e) {
        if (mounted) showError(context, e);
      }
    }
  }

  Future<void> _slotForm(int day, Period period, {Slot? slot}) async {
    final api = context.read<ApiClient>();
    final l = context.read<Lookups>();
    final List<SubjectRef> subjects;
    final List<TeacherRef> teachers;
    try {
      subjects = await l.subjects();
      teachers = await l.teachers();
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: '${weekdayName(day)} · ${period.label}',
      builder: (_) => QuickForm(
        intro: 'Leave the teacher empty to use the teacher assigned to this subject in this class.',
        fields: [
          QField('subject_id', 'Subject', QType.dropdown, required: true, initial: slot?.subjectId, options: subjects.map((s) => MapEntry(s.id, s.name)).toList()),
          QField('teacher_id', 'Teacher (optional)', QType.dropdown, clearable: true, initial: slot?.teacherId, options: teachers.map((t) => MapEntry(t.id, t.fullName)).toList()),
          QField('room', 'Room (optional)', QType.text, initial: slot?.room),
        ],
        onSubmit: (v) {
          final room = (v['room'] as String);
          if (slot == null) {
            return api.post('/timetable-slots', body: {
              'section_id': _sectionId,
              'subject_id': v['subject_id'],
              'teacher_id': v['teacher_id'],
              'day_of_week': day,
              'period_id': period.id,
              'room': room.isEmpty ? null : room,
            });
          }
          return api.patch('/timetable-slots/${slot.id}', body: {'subject_id': v['subject_id'], 'teacher_id': v['teacher_id'], 'room': room.isEmpty ? null : room});
        },
      ),
    );
    if (ok == true) setState(() => _version++);
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final api = context.read<ApiClient>();
    return FutureBuilder<List<SectionRef>>(
      future: _sections,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: () => setState(() { _sections = context.read<Lookups>().sections(all: true); }));
        final sections = snap.data ?? <SectionRef>[];
        if (sections.isEmpty) return const EmptyState(icon: Icons.meeting_room_outlined, title: 'No classes yet');
        _sectionId ??= sections.first.id;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            SizedBox(
              width: 260,
              child: AppDropdown<String>(
                label: 'Class / section',
                value: _sectionId,
                items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(),
                onChanged: (v) => setState(() => _sectionId = v),
              ),
            ),
            ReportButton(label: 'Download PDF', path: '/reports/timetable/$_sectionId', fallbackName: 'timetable.pdf'),
            if (widget.editable) const Text('Tap a cell to add or change a lesson', style: TextStyle(color: Brand.muted)),
          ]),
          const SizedBox(height: 10),
          Expanded(
            child: AsyncView<TimetableData>(
              loadKey: '$_sectionId|$_version',
              loader: () async => TimetableData.fromJson(await api.get('/timetable/sections/$_sectionId')),
              builder: (context, data, reload) => TimetableGrid(
                data: data,
                subtitle: (s) => s.teacherName,
                onCellTap: widget.editable ? _cellTapped : null,
              ),
            ),
          ),
        ]);
      },
    );
  }
}

// ================================================================== period definitions (admin)
class _PeriodsTab extends StatelessWidget {
  const _PeriodsTab();

  Future<void> _form(BuildContext context, Future<void> Function() reload, {Period? p, int? nextNo}) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: p == null ? 'New period' : 'Edit period',
      builder: (_) => QuickForm(
        fields: [
          QField('period_no', 'Period number', QType.number, required: true, initial: p?.periodNo ?? nextNo),
          QField('label', 'Label', QType.text, required: true, initial: p?.label, helper: 'e.g. Period 1, Break'),
          QField('start_time', 'Starts', QType.time, required: true, initial: parseTimeOfDay(p?.start)),
          QField('end_time', 'Ends', QType.time, required: true, initial: parseTimeOfDay(p?.end)),
          QField('is_break', 'This is a break (no lessons)', QType.toggle, initial: p?.isBreak ?? false),
        ],
        onSubmit: (v) {
          final body = {
            'period_no': int.parse(v['period_no'] as String),
            'label': v['label'],
            'start_time': hhmm(v['start_time'] as TimeOfDay),
            'end_time': hhmm(v['end_time'] as TimeOfDay),
            'is_break': v['is_break'],
          };
          return p == null ? api.post('/period-definitions', body: body) : api.patch('/period-definitions/${p.id}', body: body);
        },
      ),
    );
    if (ok == true) await reload();
  }

  Future<void> _delete(BuildContext context, Period p, Future<void> Function() reload) async {
    final ok = await confirmDialog(context, title: 'Delete "${p.label}"?', message: 'A period that is used by lessons cannot be deleted.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !context.mounted) return;
    try {
      await context.read<ApiClient>().delete('/period-definitions/${p.id}');
      await reload();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<Period>>(
      loader: () async => (asMapList(await api.get('/period-definitions')).map(Period.fromJson).toList())..sort((a, b) => a.periodNo.compareTo(b.periodNo)),
      builder: (context, periods, reload) => Column(children: [
        Align(
          alignment: Alignment.centerRight,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: FilledButton.icon(
              onPressed: () => _form(context, reload, nextNo: periods.isEmpty ? 1 : periods.last.periodNo + 1),
              icon: const Icon(Icons.add),
              label: const Text('New period'),
            ),
          ),
        ),
        Expanded(
          child: periods.isEmpty
              ? const EmptyState(icon: Icons.schedule, title: 'No periods yet', message: 'Define the school day first, then build class timetables.')
              : ListView.separated(
                  itemCount: periods.length,
                  separatorBuilder: (context, i) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final p = periods[i];
                    return AppCard(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      child: Row(children: [
                        CircleAvatar(radius: 16, backgroundColor: p.isBreak ? Brand.muted : Brand.primary, child: Text('${p.periodNo}', style: const TextStyle(color: Colors.white, fontSize: 13))),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(p.label + (p.isBreak ? ' (break)' : ''), style: const TextStyle(fontWeight: FontWeight.w600)),
                            Text(formatTimeRange(p.start, p.end), style: const TextStyle(color: Brand.muted)),
                          ]),
                        ),
                        IconButton(tooltip: 'Edit', icon: const Icon(Icons.edit_outlined), onPressed: () => _form(context, reload, p: p)),
                        IconButton(tooltip: 'Delete', icon: const Icon(Icons.delete_outline, color: Brand.danger), onPressed: () => _delete(context, p, reload)),
                      ]),
                    );
                  },
                ),
        ),
      ]),
    );
  }
}
