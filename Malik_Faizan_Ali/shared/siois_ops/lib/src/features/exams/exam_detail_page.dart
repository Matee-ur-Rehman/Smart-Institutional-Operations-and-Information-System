import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/quick_form.dart';
import '../common/report_download.dart';
import '../timetable/timetable_models.dart' show parseTimeOfDay;
import 'exams_models.dart';
import 'marks_page.dart';

/// One exam: its papers (schedule), mark entry and per-class results.
class ExamDetailPage extends StatefulWidget {
  const ExamDetailPage({super.key, required this.exam, required this.isAdmin});
  final Exam exam;
  final bool isAdmin;
  @override
  State<ExamDetailPage> createState() => _ExamDetailPageState();
}

class _ExamDetailPageState extends State<ExamDetailPage> {
  late Exam _exam = widget.exam;
  int _version = 0; // bump to reload papers and results

  Future<void> _refreshExam() async {
    try {
      final e = Exam.fromJson(asMap(await context.read<ApiClient>().get('/exams/${_exam.id}')));
      if (mounted) setState(() => _exam = e);
    } catch (_) {
      // keep the old header
    }
  }

  Future<void> _publish() async {
    final ok = await confirmDialog(context,
        title: 'Publish results?',
        message: 'Students and parents will see the results of "${_exam.name}" and be notified. Marks can no longer be changed afterwards.',
        confirmLabel: 'Publish');
    if (!ok || !mounted) return;
    try {
      final res = asMap(await context.read<ApiClient>().post('/exams/${_exam.id}/publish-results'));
      if (!mounted) return;
      showSnack(context, 'Results published. ${asInt(res['notified'])} notification(s) sent.');
      await _refreshExam();
      setState(() => _version++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppBar(
          title: Text(_exam.name),
          actions: [
            if (widget.isAdmin && !_exam.published && _exam.status != 'draft')
              Padding(padding: const EdgeInsets.only(right: 8), child: TextButton.icon(onPressed: _publish, icon: const Icon(Icons.campaign_outlined), label: const Text('Publish results'))),
          ],
          bottom: const TabBar(tabs: [Tab(text: 'Papers'), Tab(text: 'Class results')]),
        ),
        body: Padding(
          padding: const EdgeInsets.all(16),
          child: ContentWidth(
            maxWidth: 1100,
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Row(children: [
                Expanded(child: Text('${humanize(_exam.examType)} · ${formatDate(_exam.start)} – ${formatDate(_exam.end)}', style: const TextStyle(color: Brand.muted))),
                StatusChip(_exam.status, color: examStatusColor(_exam.status)),
              ]),
              const SizedBox(height: 10),
              Expanded(
                child: TabBarView(children: [
                  _PapersTab(exam: _exam, isAdmin: widget.isAdmin, version: _version, onChanged: () => setState(() => _version++)),
                  _ResultsTab(exam: _exam, isAdmin: widget.isAdmin, version: _version),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

// ================================================================== papers
class _PapersTab extends StatelessWidget {
  const _PapersTab({required this.exam, required this.isAdmin, required this.version, required this.onChanged});
  final Exam exam;
  final bool isAdmin;
  final int version;
  final VoidCallback onChanged;

  Future<void> _form(BuildContext context, {ExamPaper? paper}) async {
    final api = context.read<ApiClient>();
    final l = context.read<Lookups>();
    final List<SectionRef> sections;
    final List<SubjectRef> subjects;
    try {
      sections = await l.sections(all: true);
      subjects = await l.subjects();
    } catch (e) {
      if (context.mounted) showError(context, e);
      return;
    }
    if (!context.mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: paper == null ? 'Add paper' : 'Edit paper',
      builder: (_) => QuickForm(
        intro: paper == null ? null : '${paper.subjectName} · ${paper.sectionLabel} (class and subject cannot be changed; delete and re-add instead)',
        fields: [
          if (paper == null) ...[
            QField('section_id', 'Class / section', QType.dropdown, required: true, options: sections.map((s) => MapEntry(s.id, s.label)).toList()),
            QField('subject_id', 'Subject', QType.dropdown, required: true, options: subjects.map((s) => MapEntry(s.id, s.name)).toList()),
          ],
          QField('exam_date', 'Date', QType.date, required: true, initial: paper?.date ?? exam.start),
          QField('start_time', 'Starts', QType.time, required: true, initial: parseTimeOfDay(paper?.start) ?? const TimeOfDay(hour: 9, minute: 0)),
          QField('end_time', 'Ends', QType.time, required: true, initial: parseTimeOfDay(paper?.end) ?? const TimeOfDay(hour: 11, minute: 0)),
          QField('room', 'Room (optional)', QType.text, initial: paper?.room),
          QField('total_marks', 'Total marks', QType.number, required: true, initial: paper?.total ?? 100),
          QField('passing_marks', 'Passing marks', QType.number, required: true, initial: paper?.passing ?? 40),
        ],
        onSubmit: (v) {
          final room = v['room'] as String;
          final body = <String, dynamic>{
            'exam_date': isoDate(v['exam_date'] as DateTime),
            'start_time': hhmm(v['start_time'] as TimeOfDay),
            'end_time': hhmm(v['end_time'] as TimeOfDay),
            'room': room.isEmpty ? null : room,
            'total_marks': v['total_marks'],
            'passing_marks': v['passing_marks'],
          };
          if (paper == null) {
            body['section_id'] = v['section_id'];
            body['subject_id'] = v['subject_id'];
            return api.post('/exams/${exam.id}/schedules', body: body);
          }
          return api.patch('/exam-schedules/${paper.id}', body: body);
        },
      ),
    );
    if (ok == true) onChanged();
  }

  Future<void> _delete(BuildContext context, ExamPaper p) async {
    final ok = await confirmDialog(context, title: 'Delete this paper?', message: '${p.subjectName} · ${p.sectionLabel}. Marks already entered for it are deleted too.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !context.mounted) return;
    try {
      await context.read<ApiClient>().delete('/exam-schedules/${p.id}');
      onChanged();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<ExamPaper>>(
      loadKey: version,
      loader: () async => asMapList(await api.get('/exams/${exam.id}/schedules')).map(ExamPaper.fromJson).toList(),
      builder: (context, papers, reload) => Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (isAdmin && !exam.published)
          Align(alignment: Alignment.centerRight, child: Padding(padding: const EdgeInsets.only(bottom: 10), child: FilledButton.icon(onPressed: () => _form(context), icon: const Icon(Icons.add), label: const Text('Add paper')))),
        Expanded(
          child: papers.isEmpty
              ? EmptyState(icon: Icons.event_note_outlined, title: 'No papers', message: isAdmin ? 'Add the papers (class, subject, date and marks).' : 'You have no papers in this exam.')
              : ListView.separated(
                  itemCount: papers.length,
                  separatorBuilder: (context, i) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final p = papers[i];
                    return AppCard(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(children: [
                          Expanded(child: Text('${p.subjectName} · ${p.sectionLabel}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                          if (p.studentCount != null) StatusChip('${p.marksEntered ?? 0}/${p.studentCount} marked', color: (p.marksEntered ?? 0) >= (p.studentCount ?? 0) && (p.studentCount ?? 0) > 0 ? Brand.success : Brand.warning),
                        ]),
                        Text('${formatWeekday(p.date)}, ${formatDate(p.date)} · ${formatTimeRange(p.start, p.end)}${(p.room ?? '').isNotEmpty ? ' · Room ${p.room}' : ''}', style: const TextStyle(color: Brand.muted)),
                        Text('Total ${formatNumber(p.total)} · Passing ${formatNumber(p.passing)}', style: const TextStyle(color: Brand.muted)),
                        if (!exam.published || isAdmin)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Wrap(spacing: 8, runSpacing: 4, children: [
                              if (p.studentCount != null)
                                FilledButton.tonalIcon(
                                  onPressed: () async {
                                    await Navigator.of(context).push<void>(MaterialPageRoute<void>(builder: (_) => MarksPage(paper: p)));
                                    onChanged();
                                  },
                                  icon: const Icon(Icons.edit_note, size: 18),
                                  label: Text(exam.published ? 'View marks' : 'Enter marks'),
                                ),
                              if (isAdmin && !exam.published) ...[
                                TextButton.icon(onPressed: () => _form(context, paper: p), icon: const Icon(Icons.edit_outlined, size: 18), label: const Text('Edit')),
                                TextButton.icon(onPressed: () => _delete(context, p), icon: const Icon(Icons.delete_outline, size: 18), label: const Text('Delete'), style: TextButton.styleFrom(foregroundColor: Brand.danger)),
                              ],
                            ]),
                          ),
                      ]),
                    );
                  },
                ),
        ),
      ]),
    );
  }
}

// ================================================================== class results
class _ResultsTab extends StatefulWidget {
  const _ResultsTab({required this.exam, required this.isAdmin, required this.version});
  final Exam exam;
  final bool isAdmin;
  final int version;
  @override
  State<_ResultsTab> createState() => _ResultsTabState();
}

class _ResultsTabState extends State<_ResultsTab> {
  late Future<List<SectionRef>> _sections;
  String? _sectionId;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections(all: widget.isAdmin);
  }

  Color _resultColor(String r) => r == 'pass' ? Brand.success : (r == 'fail' ? Brand.danger : Brand.muted);

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return FutureBuilder<List<SectionRef>>(
      future: _sections,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: () => setState(() { _sections = context.read<Lookups>().sections(all: widget.isAdmin); }));
        final sections = snap.data ?? <SectionRef>[];
        if (sections.isEmpty) return const EmptyState(icon: Icons.meeting_room_outlined, title: 'No classes available');
        _sectionId ??= sections.first.id;
        final sid = _sectionId;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Wrap(spacing: 12, runSpacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: [
            SizedBox(
              width: 260,
              child: AppDropdown<String>(
                label: 'Class / section',
                value: sid,
                items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(),
                onChanged: (v) => setState(() => _sectionId = v),
              ),
            ),
            ReportButton(label: 'PDF', path: '/reports/results/sections/$sid', query: {'exam_id': widget.exam.id, 'format': 'pdf'}, fallbackName: 'results.pdf'),
            ReportButton(label: 'CSV', icon: Icons.table_chart_outlined, path: '/reports/results/sections/$sid', query: {'exam_id': widget.exam.id, 'format': 'csv'}, fallbackName: 'results.csv'),
          ]),
          const SizedBox(height: 10),
          Expanded(
            child: AsyncView<Map<String, dynamic>>(
              loadKey: '$sid|${widget.version}',
              loader: () async => asMap(await api.get('/results/sections/$sid', query: {'exam_id': widget.exam.id})),
              builder: (context, data, reload) {
                final sum = asMap(data['summary']);
                final students = asMapList(data['students']);
                return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Wrap(spacing: 10, runSpacing: 10, children: [
                    for (final k in [
                      ('Students', '${asInt(sum['students'])}', Icons.people_outline, Brand.primary),
                      ('Passed', '${asInt(sum['passed'])}', Icons.check_circle_outline, Brand.success),
                      ('Failed', '${asInt(sum['failed'])}', Icons.cancel_outlined, Brand.danger),
                      ('Incomplete', '${asInt(sum['incomplete'])}', Icons.hourglass_empty, Brand.warning),
                      ('Average', formatPercent(asDoubleN(sum['average_percentage'])), Icons.percent, Brand.info),
                    ])
                      SizedBox(width: 190, child: KpiCard(label: k.$1, value: k.$2, icon: k.$3, color: k.$4)),
                  ]),
                  const SizedBox(height: 10),
                  Expanded(
                    child: students.isEmpty
                        ? const EmptyState(icon: Icons.people_outline, title: 'No students in this class')
                        : ListView.separated(
                            itemCount: students.length,
                            separatorBuilder: (context, i) => const SizedBox(height: 6),
                            itemBuilder: (context, i) {
                              final s = students[i];
                              final result = asStr(s['result'], 'incomplete');
                              final pos = s['position'];
                              return AppCard(
                                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                                child: Row(children: [
                                  SizedBox(width: 34, child: Text(pos == null ? '–' : '#${asStr(pos)}', style: const TextStyle(fontWeight: FontWeight.w800, color: Brand.primary))),
                                  Expanded(
                                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Text(asStr(s['full_name']), style: const TextStyle(fontWeight: FontWeight.w600)),
                                      Text('Roll ${asStr(s['roll_no'])} · ${formatNumber(asDouble(s['total_obtained']))}/${formatNumber(asDouble(s['total_marks']))}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                                    ]),
                                  ),
                                  Text(formatPercent(asDoubleN(s['percentage'])), style: const TextStyle(fontWeight: FontWeight.w700)),
                                  const SizedBox(width: 10),
                                  SizedBox(width: 30, child: Text(asStr(s['grade'], '–'), style: const TextStyle(fontWeight: FontWeight.w800))),
                                  StatusChip(result, color: _resultColor(result)),
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
