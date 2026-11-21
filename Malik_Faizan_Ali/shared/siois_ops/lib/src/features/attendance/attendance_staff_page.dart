import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/report_download.dart';
import 'attendance_models.dart';

/// Admin / teacher: mark the daily register, see which sections have not marked yet, and per-section summaries.
class AttendanceStaffPage extends StatelessWidget {
  const AttendanceStaffPage({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: PageFrame(
        title: 'Attendance',
        subtitle: 'Daily register, today\'s overview and summaries',
        child: Column(children: const [
          Align(
            alignment: Alignment.centerLeft,
            child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [
              Tab(text: 'Mark attendance'),
              Tab(text: 'Overview'),
              Tab(text: 'Section summary'),
            ]),
          ),
          SizedBox(height: 12),
          Expanded(child: TabBarView(children: [_MarkTab(), _OverviewTab(), _SummaryTab()])),
        ]),
      ),
    );
  }
}

// ================================================================== shared: section dropdown
class _SectionPicker extends StatelessWidget {
  const _SectionPicker({required this.sections, required this.value, required this.onChanged});
  final List<SectionRef> sections;
  final String? value;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) => AppDropdown<String>(
        label: 'Class / section',
        value: value,
        items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(),
        onChanged: onChanged,
      );
}

// ================================================================== mark tab
class _MarkTab extends StatefulWidget {
  const _MarkTab();
  @override
  State<_MarkTab> createState() => _MarkTabState();
}

class _MarkTabState extends State<_MarkTab> with AutomaticKeepAliveClientMixin {
  late Future<List<SectionRef>> _sections;
  String? _sectionId;
  DateTime _date = dateOnly(DateTime.now());
  int _version = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return FutureBuilder<List<SectionRef>>(
      future: _sections,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: () => setState(() { _sections = context.read<Lookups>().sections(); }));
        final sections = snap.data ?? <SectionRef>[];
        if (sections.isEmpty) {
          return const EmptyState(icon: Icons.meeting_room_outlined, title: 'No classes assigned to you', message: 'Ask the administrator to assign you to a class.');
        }
        _sectionId ??= sections.first.id;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FilterBar(children: [
            _SectionPicker(sections: sections, value: _sectionId, onChanged: (v) => setState(() => _sectionId = v)),
            DateField(label: 'Date', value: _date, lastDate: dateOnly(DateTime.now()), onChanged: (d) => setState(() => _date = d ?? _date)),
          ]),
          Expanded(
            child: AsyncView<AttendanceSheet>(
              loadKey: '$_sectionId|${isoDate(_date)}|$_version',
              loader: () async => AttendanceSheet.fromJson(
                  await context.read<ApiClient>().get('/attendance/sections/$_sectionId', query: {'date': isoDate(_date)})),
              builder: (context, sheet, reload) => _Sheet(
                key: ValueKey<String>('${sheet.sectionId}|${isoDate(sheet.date)}|$_version'),
                sheet: sheet,
                onSaved: () => setState(() => _version++),
              ),
            ),
          ),
        ]);
      },
    );
  }
}

class _Sheet extends StatefulWidget {
  const _Sheet({super.key, required this.sheet, required this.onSaved});
  final AttendanceSheet sheet;
  final VoidCallback onSaved;
  @override
  State<_Sheet> createState() => _SheetState();
}

class _SheetState extends State<_Sheet> with BusyMixin {
  final Map<String, String> _status = <String, String>{};
  final Map<String, String> _initial = <String, String>{};

  @override
  void initState() {
    super.initState();
    for (final r in widget.sheet.rows) {
      if (r.status != null) {
        _status[r.studentId] = r.status!;
        _initial[r.studentId] = r.status!;
      } else if (r.onApprovedLeave && widget.sheet.editable) {
        // an approved leave request covers this date: pre-select it (the teacher can still change it)
        _status[r.studentId] = 'leave';
      }
    }
  }

  bool get _dirty {
    if (_status.length != _initial.length) return true;
    for (final e in _status.entries) {
      if (_initial[e.key] != e.value) return true;
    }
    return false;
  }

  int _count(String s) => _status.values.where((v) => v == s).length;

  void _markAll(String s) => setState(() {
        for (final r in widget.sheet.rows) {
          _status[r.studentId] = s;
        }
      });

  Future<void> _save() async {
    if (_status.isEmpty) {
      showSnack(context, 'Mark at least one student first', error: true);
      return;
    }
    final unmarked = widget.sheet.rows.length - _status.length;
    if (unmarked > 0) {
      final go = await confirmDialog(context,
          title: 'Save with $unmarked unmarked?',
          message: '$unmarked student(s) have no status yet. They will stay unmarked.',
          confirmLabel: 'Save anyway');
      if (!go || !mounted) return;
    }
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.put('/attendance/sections/${widget.sheet.sectionId}?date=${isoDate(widget.sheet.date)}', body: {
        'entries': [
          for (final r in widget.sheet.rows)
            if (_status.containsKey(r.studentId)) {'student_id': r.studentId, 'status': _status[r.studentId]},
        ],
      });
    });
    if (ok && mounted) {
      showSnack(context, 'Attendance saved');
      widget.onSaved();
    }
  }

  @override
  Widget build(BuildContext context) {
    final sheet = widget.sheet;
    if (sheet.rows.isEmpty) {
      return const EmptyState(icon: Icons.people_outline, title: 'No students in this section');
    }
    final editable = sheet.editable;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (!editable)
        Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: Brand.warning.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
          child: Row(children: const [
            Icon(Icons.lock_outline, size: 18, color: Brand.warning),
            SizedBox(width: 8),
            Expanded(child: Text('This date is read-only (holiday, Sunday, future date, or older than 7 days — ask an admin to correct it).')),
          ]),
        ),
      AppCard(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Wrap(spacing: 14, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Text('${_status.length} / ${sheet.rows.length} marked', style: const TextStyle(fontWeight: FontWeight.w700)),
          for (final s in kAttendanceStatuses) Text('${attendanceLabel(s)}: ${_count(s)}', style: TextStyle(color: attendanceColor(s), fontWeight: FontWeight.w600)),
          if (editable) ...[
            TextButton.icon(onPressed: () => _markAll('present'), icon: const Icon(Icons.done_all, size: 18), label: const Text('All present')),
            FilledButton.icon(
              onPressed: busy || !_dirty ? null : _save,
              icon: busy ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.save_outlined, size: 18),
              label: const Text('Save'),
            ),
          ],
        ]),
      ),
      const SizedBox(height: 8),
      Expanded(
        child: ListView.separated(
          itemCount: sheet.rows.length,
          separatorBuilder: (context, i) => const SizedBox(height: 6),
          itemBuilder: (context, i) {
            final r = sheet.rows[i];
            final current = _status[r.studentId];
            return AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 12, runSpacing: 6, children: [
                SizedBox(
                  width: 210,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(r.fullName, style: const TextStyle(fontWeight: FontWeight.w600), overflow: TextOverflow.ellipsis),
                    Text('Roll ${r.rollNo}${r.onApprovedLeave ? ' · approved leave' : ''}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                  ]),
                ),
                for (final s in kAttendanceStatuses)
                  ChoiceChip(
                    label: Text(attendanceLabel(s)),
                    selected: current == s,
                    selectedColor: attendanceColor(s).withValues(alpha: 0.2),
                    labelStyle: TextStyle(color: current == s ? attendanceColor(s) : null, fontWeight: current == s ? FontWeight.w700 : FontWeight.w500),
                    onSelected: editable ? (_) => setState(() => _status[r.studentId] = s) : null,
                  ),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}

// ================================================================== overview tab
class _OverviewTab extends StatefulWidget {
  const _OverviewTab();
  @override
  State<_OverviewTab> createState() => _OverviewTabState();
}

class _OverviewTabState extends State<_OverviewTab> {
  DateTime _date = dateOnly(DateTime.now());

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      FilterBar(children: [
        DateField(label: 'Date', value: _date, lastDate: dateOnly(DateTime.now()), onChanged: (d) => setState(() => _date = d ?? _date)),
      ]),
      Expanded(
        child: AsyncView<Map<String, dynamic>>(
          loadKey: isoDate(_date),
          loader: () async => asMap(await api.get('/attendance/overview', query: {'date': isoDate(_date)})),
          builder: (context, data, reload) {
            final sections = asMapList(data['sections']);
            final schoolDay = asBool(data['school_day'], true);
            final unmarked = asInt(data['unmarked_sections']);
            return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (!schoolDay)
                const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('Sunday — not a school day.', style: TextStyle(color: Brand.muted)))
              else
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(unmarked == 0 ? 'All sections have marked attendance.' : '$unmarked section(s) have not marked attendance yet.',
                      style: TextStyle(fontWeight: FontWeight.w600, color: unmarked == 0 ? Brand.success : Brand.warning)),
                ),
              Expanded(
                child: sections.isEmpty
                    ? const EmptyState(icon: Icons.meeting_room_outlined, title: 'No sections')
                    : ListView.separated(
                        itemCount: sections.length,
                        separatorBuilder: (context, i) => const SizedBox(height: 8),
                        itemBuilder: (context, i) {
                          final s = sections[i];
                          final marked = asBool(s['is_marked']);
                          return AppCard(
                            child: Row(children: [
                              Expanded(
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text(asStr(s['section_label']), style: const TextStyle(fontWeight: FontWeight.w700)),
                                  Text('${asStr(s['students'])} students', style: const TextStyle(color: Brand.muted)),
                                ]),
                              ),
                              if (marked)
                                Wrap(spacing: 10, children: [
                                  Text('P ${asStr(s['present'])}', style: const TextStyle(color: Brand.success, fontWeight: FontWeight.w700)),
                                  Text('A ${asStr(s['absent'])}', style: const TextStyle(color: Brand.danger, fontWeight: FontWeight.w700)),
                                  Text('L ${asStr(s['late'])}', style: const TextStyle(color: Brand.warning, fontWeight: FontWeight.w700)),
                                  Text('Lv ${asStr(s['leave'])}', style: const TextStyle(color: Brand.info, fontWeight: FontWeight.w700)),
                                ])
                              else
                                StatusChip(asInt(s['students']) == 0 ? 'no students' : 'not marked', color: asInt(s['students']) == 0 ? Brand.muted : Brand.warning),
                            ]),
                          );
                        },
                      ),
              ),
            ]);
          },
        ),
      ),
    ]);
  }
}

// ================================================================== summary tab
class _SummaryTab extends StatefulWidget {
  const _SummaryTab();
  @override
  State<_SummaryTab> createState() => _SummaryTabState();
}

class _SummaryTabState extends State<_SummaryTab> {
  late Future<List<SectionRef>> _sections;
  String? _sectionId;
  DateTime? _from;
  DateTime? _to;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections();
  }

  Map<String, dynamic> get _range => {'from_date': _from, 'to_date': _to};

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return FutureBuilder<List<SectionRef>>(
      future: _sections,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: () => setState(() { _sections = context.read<Lookups>().sections(); }));
        final sections = snap.data ?? <SectionRef>[];
        if (sections.isEmpty) return const EmptyState(icon: Icons.meeting_room_outlined, title: 'No classes assigned to you');
        _sectionId ??= sections.first.id;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          FilterBar(children: [
            _SectionPicker(sections: sections, value: _sectionId, onChanged: (v) => setState(() => _sectionId = v)),
            DateField(label: 'From (optional)', value: _from, clearable: true, onChanged: (d) => setState(() => _from = d)),
            DateField(label: 'To (optional)', value: _to, clearable: true, lastDate: DateTime.now(), onChanged: (d) => setState(() => _to = d)),
          ]),
          Expanded(
            child: AsyncView<Map<String, dynamic>>(
              loadKey: '$_sectionId|$_from|$_to',
              loader: () async => asMap(await api.get('/attendance/sections/$_sectionId/summary', query: {
                if (_from != null) 'from_date': isoDate(_from!),
                if (_to != null) 'to_date': isoDate(_to!),
              })),
              builder: (context, data, reload) {
                final students = asMapList(data['students']);
                final avg = data['average_percentage'];
                return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Wrap(spacing: 10, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
                    Text('${formatDate(asDateN(data['from_date']))} – ${formatDate(asDateN(data['to_date']))}', style: const TextStyle(color: Brand.muted)),
                    Text('Average: ${avg == null ? '—' : formatPercent(asDouble(avg))}', style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text('${asInt(data['low_attendance_count'])} below ${formatNumber(asDouble(data['threshold']), decimals: 0)}%',
                        style: const TextStyle(color: Brand.danger, fontWeight: FontWeight.w600)),
                    ReportButton(label: 'PDF', path: '/reports/attendance/sections/$_sectionId', query: {..._range, 'format': 'pdf'}, fallbackName: 'attendance.pdf'),
                    ReportButton(label: 'CSV', icon: Icons.table_chart_outlined, path: '/reports/attendance/sections/$_sectionId', query: {..._range, 'format': 'csv'}, fallbackName: 'attendance.csv'),
                  ]),
                  const SizedBox(height: 8),
                  Expanded(
                    child: students.isEmpty
                        ? const EmptyState(icon: Icons.people_outline, title: 'No students in this section')
                        : ListView.separated(
                            itemCount: students.length,
                            separatorBuilder: (context, i) => const SizedBox(height: 6),
                            itemBuilder: (context, i) {
                              final st = students[i];
                              final sm = AttendanceSummary.fromJson(st['summary']);
                              final low = asBool(st['low_attendance']);
                              return AppCard(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                child: Row(children: [
                                  Expanded(
                                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Text(asStr(st['full_name']), style: const TextStyle(fontWeight: FontWeight.w600)),
                                      Text('Roll ${asStr(st['roll_no'])} · P ${sm.present}  L ${sm.late}  A ${sm.absent}  Lv ${sm.leave}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                                    ]),
                                  ),
                                  Text(formatPercent(sm.percentage), style: TextStyle(fontWeight: FontWeight.w800, color: low ? Brand.danger : Brand.success)),
                                  if (low) const Padding(padding: EdgeInsets.only(left: 8), child: StatusChip('low', color: Brand.danger)),
                                ]),
                              );
                            },
                          ),
                  ),
                ]);
              },
            ),
          ),
        ]);
      },
    );
  }
}
