import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

const List<MapEntry<String, String>> _examTypes = <MapEntry<String, String>>[
  MapEntry('monthly', 'Monthly test'),
  MapEntry('midterm', 'Mid-term'),
  MapEntry('final', 'Final'),
  MapEntry('other', 'Other'),
];

// ====================================================================== admin: exams

/// Admin: create exams, open one to schedule papers, publish results.
class ExamsAdminScreen extends StatefulWidget {
  const ExamsAdminScreen({super.key});

  @override
  State<ExamsAdminScreen> createState() => _ExamsAdminScreenState();
}

class _ExamsAdminScreenState extends State<ExamsAdminScreen> {
  late Future<Paged<Exam>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().exams();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().exams());

  Future<void> _create() async {
    final api = context.read<OpsApi>();
    var name = '';
    var type = 'monthly';
    var status = 'draft';
    DateTime? start;
    DateTime? end;
    final saved = await showFormDialog(
      context,
      title: 'New exam',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Exam name (e.g. Mid-term 2026)', name, (v) => name = v),
          pickString('Type', type, _examTypes, (v) => set(() => type = v ?? type)),
          DateField(label: 'Starts', value: start, onChanged: (d) => set(() => start = d)),
          DateField(label: 'Ends', value: end, onChanged: (d) => set(() => end = d)),
          pickString('Status', status, const [
            MapEntry('draft', 'Draft (hidden from teachers, students and parents)'),
            MapEntry('scheduled', 'Scheduled (visible)'),
          ], (v) => set(() => status = v ?? status)),
        ]),
      ),
      validate: () =>
          Validators.minLength(name, 3, 'Exam name') ??
          Validators.requiredDate(start, 'Start date') ??
          Validators.requiredDate(end, 'End date') ??
          Validators.dateOrder(start, end),
      onSubmit: () => api.createExam(<String, dynamic>{
        'name': name.trim(),
        'exam_type': type,
        'start_date': ymd(start!),
        'end_date': ymd(end!),
        'status': status,
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Exam created');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Exams'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      floatingActionButton: FloatingActionButton.extended(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New exam')),
      body: ContentWidth(
        child: FutureView<Paged<Exam>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, page) {
            if (page.items.isEmpty) return const EmptyView('No exams yet', icon: Icons.edit_note);
            return ListView.builder(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 88),
              itemCount: page.items.length,
              itemBuilder: (ctx, i) {
                final e = page.items[i];
                return Card(
                  child: ListTile(
                    title: Text(e.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text('${titleCase(e.examType)}  -  ${fmtDate(e.startDate)} to ${fmtDate(e.endDate)}'),
                    trailing: StatusChip(e.status),
                    onTap: () async {
                      await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => ExamDetailScreen(exam: e)));
                      if (mounted) _reload();
                    },
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

/// Admin: the papers of one exam, status changes, publishing.
class ExamDetailScreen extends StatefulWidget {
  const ExamDetailScreen({super.key, required this.exam});

  final Exam exam;

  @override
  State<ExamDetailScreen> createState() => _ExamDetailScreenState();
}

class _ExamDetailScreenState extends State<ExamDetailScreen> {
  late Future<List<ExamSchedule>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().schedules(widget.exam.id);
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().schedules(widget.exam.id));

  Future<void> _addPaper() async {
    final api = context.read<OpsApi>();
    List<SectionItem> sections;
    List<SubjectItem> subjects;
    try {
      sections = await api.sections();
      subjects = await api.subjects();
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.message, error: true);
      return;
    }
    if (!mounted) return;
    String? sectionId;
    String? subjectId;
    DateTime? date;
    String? start;
    String? end;
    var room = '';
    var total = '100';
    var passing = '40';
    final exam = widget.exam;
    final saved = await showFormDialog(
      context,
      title: 'Add paper',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          pickString('Section', sectionId, [for (final s in sections) MapEntry(s.id, s.display)], (v) => set(() => sectionId = v)),
          pickString('Subject', subjectId, [for (final s in subjects) MapEntry(s.id, s.name)], (v) => set(() => subjectId = v)),
          DateField(label: 'Exam date', value: date, firstDate: exam.startDate, lastDate: exam.endDate, onChanged: (d) => set(() => date = d)),
          TimeField(label: 'Starts', value: start, onChanged: (t) => set(() => start = t)),
          TimeField(label: 'Ends', value: end, onChanged: (t) => set(() => end = t)),
          formText('Room (optional)', room, (v) => room = v),
          formText('Total marks', total, (v) => total = v, number: true),
          formText('Passing marks', passing, (v) => passing = v, number: true),
        ]),
      ),
      validate: () {
        if (sectionId == null || subjectId == null) return 'Choose a section and a subject';
        final t = Validators.parseNumber(total);
        final p = Validators.parseNumber(passing);
        return Validators.requiredDate(date, 'Exam date') ??
            (start == null || end == null ? 'Choose the start and end time' : null) ??
            Validators.timeOrder(start, end) ??
            Validators.positiveAmount(total, label: 'Total marks') ??
            (p == null || p < 0 ? 'Passing marks must be 0 or more' : null) ??
            (t != null && p != null && p > t ? 'Passing marks cannot exceed total marks' : null);
      },
      onSubmit: () => api.createSchedule(exam.id, <String, dynamic>{
        'section_id': sectionId,
        'subject_id': subjectId,
        'exam_date': ymd(date!),
        'start_time': start,
        'end_time': end,
        if (room.trim().isNotEmpty) 'room': room.trim(),
        'total_marks': Validators.parseNumber(total),
        'passing_marks': Validators.parseNumber(passing),
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Paper added');
    }
  }

  Future<void> _menu(String value) async {
    final api = context.read<OpsApi>();
    final exam = widget.exam;
    if (value == 'publish') {
      if (!await confirmDialog(
        context,
        'Publish results?',
        'Students and parents will be able to see the results of "${exam.name}" and will be notified. Marks can no longer be changed.',
        yes: 'Publish',
      )) {
        return;
      }
      if (!mounted) return;
      final ok = await runAction(context, () => api.publishResults(exam.id), success: 'Results published');
      if (ok && mounted) Navigator.of(context).pop();
    } else if (value == 'delete') {
      if (!await confirmDialog(context, 'Delete exam?', '"${exam.name}" will be deleted (only possible while it is a draft).', yes: 'Delete')) return;
      if (!mounted) return;
      final ok = await runAction(context, () => api.deleteExam(exam.id), success: 'Exam deleted');
      if (ok && mounted) Navigator.of(context).pop();
    } else {
      final ok = await runAction(context, () => api.updateExam(exam.id, <String, dynamic>{'status': value}), success: 'Status updated');
      if (ok && mounted) Navigator.of(context).pop();
    }
  }

  Future<void> _deletePaper(ExamSchedule s) async {
    if (!await confirmDialog(context, 'Delete paper?', '${s.subjectName} - ${s.sectionName} and its marks will be removed.', yes: 'Delete')) return;
    if (!mounted) return;
    final ok = await runAction(context, () => context.read<OpsApi>().deleteSchedule(s.id), success: 'Paper deleted');
    if (ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final exam = widget.exam;
    return Scaffold(
      appBar: AppBar(
        title: Text(exam.name),
        actions: [
          if (!exam.resultsPublished)
            PopupMenuButton<String>(
              onSelected: _menu,
              itemBuilder: (_) => [
                const PopupMenuItem(value: 'scheduled', child: Text('Mark as scheduled')),
                const PopupMenuItem(value: 'ongoing', child: Text('Mark as ongoing')),
                const PopupMenuItem(value: 'completed', child: Text('Mark as completed')),
                const PopupMenuItem(value: 'publish', child: Text('Publish results')),
                if (exam.status == 'draft') const PopupMenuItem(value: 'delete', child: Text('Delete exam')),
              ],
            ),
          IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload),
        ],
      ),
      floatingActionButton: exam.resultsPublished
          ? null
          : FloatingActionButton.extended(onPressed: _addPaper, icon: const Icon(Icons.add), label: const Text('Add paper')),
      body: ContentWidth(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(child: Text('${titleCase(exam.examType)}  -  ${fmtDate(exam.startDate)} to ${fmtDate(exam.endDate)}')),
                  StatusChip(exam.status),
                ],
              ),
            ),
            Expanded(
              child: FutureView<List<ExamSchedule>>(
                future: _future,
                onRetry: _reload,
                builder: (ctx, papers) {
                  if (papers.isEmpty) return const EmptyView('No papers scheduled yet. Use "Add paper".');
                  return ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 88),
                    itemCount: papers.length,
                    itemBuilder: (ctx, i) => _PaperTile(
                      paper: papers[i],
                      trailing: [
                        IconButton(
                          tooltip: 'Enter or view marks',
                          icon: const Icon(Icons.edit_note),
                          onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => MarksEntryScreen(schedule: papers[i]))),
                        ),
                        if (!exam.resultsPublished)
                          IconButton(tooltip: 'Delete paper', icon: const Icon(Icons.delete_outline), onPressed: () => _deletePaper(papers[i])),
                      ],
                    ),
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

class _PaperTile extends StatelessWidget {
  const _PaperTile({required this.paper, this.trailing = const <Widget>[], this.onTap});

  final ExamSchedule paper;
  final List<Widget> trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onTap,
        title: Text('${paper.subjectName}  -  ${paper.sectionName}', style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          '${fmtDate(paper.examDate)}, ${hhmm(paper.startTime)} - ${hhmm(paper.endTime)}'
          '${paper.room.isEmpty ? '' : '  (room ${paper.room})'}\n'
          'Total ${fmtNum(paper.totalMarks)}, passing ${fmtNum(paper.passingMarks)}',
        ),
        isThreeLine: true,
        trailing: trailing.isEmpty ? null : Row(mainAxisSize: MainAxisSize.min, children: trailing),
      ),
    );
  }
}

// ====================================================================== teachers, students, parents: browse exams

/// Lists the visible exams. Teachers use it to enter marks ([canEnterMarks], [onlyMine]);
/// students and parents use it to see the datesheet for their section ([sectionId]).
class ExamBrowserScreen extends StatefulWidget {
  const ExamBrowserScreen({super.key, required this.title, this.canEnterMarks = false, this.onlyMine = false, this.sectionId});

  final String title;
  final bool canEnterMarks;
  final bool onlyMine;
  final String? sectionId;

  @override
  State<ExamBrowserScreen> createState() => _ExamBrowserScreenState();
}

class _ExamBrowserScreenState extends State<ExamBrowserScreen> {
  late Future<Paged<Exam>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().exams();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().exams());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        child: FutureView<Paged<Exam>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, page) {
            if (page.items.isEmpty) return const EmptyView('No exams have been announced yet', icon: Icons.edit_note);
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: page.items.length,
              itemBuilder: (ctx, i) {
                final e = page.items[i];
                return Card(
                  child: ListTile(
                    title: Text(e.name, style: const TextStyle(fontWeight: FontWeight.w600)),
                    subtitle: Text('${titleCase(e.examType)}  -  ${fmtDate(e.startDate)} to ${fmtDate(e.endDate)}'),
                    trailing: StatusChip(e.status),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
                      builder: (_) => ExamPapersScreen(
                        exam: e,
                        canEnterMarks: widget.canEnterMarks,
                        onlyMine: widget.onlyMine,
                        sectionId: widget.sectionId,
                      ),
                    )),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class ExamPapersScreen extends StatefulWidget {
  const ExamPapersScreen({super.key, required this.exam, this.canEnterMarks = false, this.onlyMine = false, this.sectionId});

  final Exam exam;
  final bool canEnterMarks;
  final bool onlyMine;
  final String? sectionId;

  @override
  State<ExamPapersScreen> createState() => _ExamPapersScreenState();
}

class _ExamPapersScreenState extends State<ExamPapersScreen> {
  late Future<List<ExamSchedule>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<ExamSchedule>> _load() async {
    final api = context.read<OpsApi>();
    final all = await api.schedules(widget.exam.id, sectionId: widget.sectionId);
    if (!widget.onlyMine) return all;
    final mine = (await api.myTeaching()).map((t) => t.key).toSet();
    return all.where((s) => mine.contains(s.teachingKey)).toList();
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.exam.name),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        child: FutureView<List<ExamSchedule>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, papers) {
            if (papers.isEmpty) return const EmptyView('No papers to show');
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: papers.length,
              itemBuilder: (ctx, i) => _PaperTile(
                paper: papers[i],
                trailing: widget.canEnterMarks ? const [Icon(Icons.edit_note)] : const <Widget>[],
                onTap: widget.canEnterMarks
                    ? () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => MarksEntryScreen(schedule: papers[i])))
                    : null,
              ),
            );
          },
        ),
      ),
    );
  }
}

// ====================================================================== marks entry

/// Marks sheet for one paper: type a mark or tick "Abs" for each student, then Save.
/// Students without a mark yet are skipped when saving, so a sheet can be filled in several sittings.
class MarksEntryScreen extends StatefulWidget {
  const MarksEntryScreen({super.key, required this.schedule});

  final ExamSchedule schedule;

  @override
  State<MarksEntryScreen> createState() => _MarksEntryScreenState();
}

class _MarksEntryScreenState extends State<MarksEntryScreen> {
  late Future<MarkSheet> _future;
  final Map<String, TextEditingController> _marks = <String, TextEditingController>{};
  final Map<String, bool> _absent = <String, bool>{};
  MarkSheet? _initFor;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().markSheet(widget.schedule.id);
  }

  @override
  void dispose() {
    for (final c in _marks.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().markSheet(widget.schedule.id));

  void _init(MarkSheet sheet) {
    if (identical(_initFor, sheet)) return;
    _initFor = sheet;
    for (final c in _marks.values) {
      c.dispose();
    }
    _marks.clear();
    _absent.clear();
    for (final r in sheet.rows) {
      _marks[r.studentId] = TextEditingController(text: r.marksObtained == null ? '' : fmtNum(r.marksObtained));
      _absent[r.studentId] = r.isAbsent;
    }
  }

  Future<void> _save(MarkSheet sheet) async {
    final total = sheet.schedule.totalMarks;
    final entries = <Map<String, dynamic>>[];
    for (final r in sheet.rows) {
      final absent = _absent[r.studentId] ?? false;
      final text = _marks[r.studentId]?.text.trim() ?? '';
      if (absent) {
        entries.add(<String, dynamic>{'student_id': r.studentId, 'is_absent': true});
        continue;
      }
      if (text.isEmpty) continue;
      final problem = Validators.marks(text, total);
      if (problem != null) {
        showMessage(context, '${r.studentName}: $problem', error: true);
        return;
      }
      entries.add(<String, dynamic>{'student_id': r.studentId, 'marks_obtained': double.parse(text), 'is_absent': false});
    }
    if (entries.isEmpty) {
      showMessage(context, 'Enter at least one mark first', error: true);
      return;
    }
    setState(() => _saving = true);
    final ok = await runAction(context, () => context.read<OpsApi>().saveMarks(sheet.schedule.id, entries), success: '${entries.length} marks saved');
    if (!mounted) return;
    setState(() => _saving = false);
    if (ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.schedule;
    return Scaffold(
      appBar: AppBar(
        title: Text('${p.subjectName} - ${p.sectionName}'),
        actions: [IconButton(tooltip: 'Reload', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 760,
        child: FutureView<MarkSheet>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, sheet) {
            _init(sheet);
            if (sheet.rows.isEmpty) return const EmptyView('There are no students in this section');
            final locked = sheet.locked;
            return Column(
              children: [
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    locked
                        ? 'Results are published, so marks can no longer be changed.'
                        : 'Total marks: ${fmtNum(sheet.schedule.totalMarks)}   Passing: ${fmtNum(sheet.schedule.passingMarks)}',
                    style: TextStyle(color: locked ? Colors.red.shade700 : null, fontWeight: FontWeight.w600),
                  ),
                ),
                Expanded(
                  child: ListView.separated(
                    itemCount: sheet.rows.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (ctx, i) {
                      final r = sheet.rows[i];
                      final absent = _absent[r.studentId] ?? false;
                      return Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        child: Row(
                          children: [
                            SizedBox(width: 56, child: Text(r.rollNo, style: TextStyle(color: Theme.of(ctx).hintColor))),
                            Expanded(child: Text(r.studentName)),
                            SizedBox(
                              width: 92,
                              child: TextField(
                                controller: _marks[r.studentId],
                                enabled: !locked && !absent,
                                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                textAlign: TextAlign.center,
                                decoration: InputDecoration(
                                  isDense: true,
                                  border: const OutlineInputBorder(),
                                  hintText: '/ ${fmtNum(sheet.schedule.totalMarks)}',
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Checkbox(
                                  value: absent,
                                  onChanged: locked
                                      ? null
                                      : (v) => setState(() {
                                            _absent[r.studentId] = v ?? false;
                                            if (v == true) _marks[r.studentId]?.clear();
                                          }),
                                ),
                                const Text('Abs', style: TextStyle(fontSize: 11)),
                              ],
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
                if (!locked)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _saving ? null : () => _save(sheet),
                        icon: const Icon(Icons.save),
                        label: Text(_saving ? 'Saving...' : 'Save marks'),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ),
    );
  }
}

// ====================================================================== results

/// Published results for a student (own results, or a child's). Marks are shown per subject with the
/// grade; the overall position is calculated by the server.
class ResultsScreen extends StatefulWidget {
  const ResultsScreen({super.key, required this.studentId});

  final String studentId;

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  late Future<List<ExamResultEntry>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().studentResults(widget.studentId);
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().studentResults(widget.studentId));

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Results'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 760,
        child: FutureView<List<ExamResultEntry>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, entries) {
            if (entries.isEmpty) return const EmptyView('No results have been published yet', icon: Icons.grading_outlined);
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: entries.length,
              itemBuilder: (ctx, i) => _ResultCard(entry: entries[i]),
            );
          },
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  const _ResultCard({required this.entry});

  final ExamResultEntry entry;

  @override
  Widget build(BuildContext context) {
    final r = entry.result;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(child: Text(entry.examName, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700))),
                if (r.passed != null) StatusChip(r.passed! ? 'pass' : 'fail', label: r.passed! ? 'Pass' : 'Fail'),
              ],
            ),
            const SizedBox(height: 8),
            for (final s in r.subjects)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    Expanded(child: Text(s.subjectName)),
                    Text(
                      s.status == 'absent'
                          ? 'Absent'
                          : (s.status == 'pending' ? 'Not entered' : '${fmtNum(s.marksObtained)} / ${fmtNum(s.totalMarks)}'),
                      style: TextStyle(color: s.passed == false ? Colors.red.shade700 : null),
                    ),
                    SizedBox(width: 44, child: Text(s.grade ?? '', textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))),
                  ],
                ),
              ),
            const Divider(height: 24),
            Wrap(
              spacing: 24,
              runSpacing: 6,
              children: [
                Text('Total: ${fmtNum(r.totalObtained)} / ${fmtNum(r.totalMarks)}', style: const TextStyle(fontWeight: FontWeight.w600)),
                if (r.percentage != null) Text('Percentage: ${fmtNum(r.percentage)}%'),
                if (r.grade != null) Text('Grade: ${r.grade}${r.remark == null || r.remark!.isEmpty ? '' : ' (${r.remark})'}'),
                if (r.position != null && r.complete) Text('Position: ${r.position}'),
              ],
            ),
            if (!r.complete)
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Text('Some subjects have no marks yet, so the result is not final.', style: TextStyle(color: Theme.of(context).hintColor)),
              ),
          ],
        ),
      ),
    );
  }
}

/// Staff: results of a whole section for one exam, ranked.
class SectionResultsScreen extends StatefulWidget {
  const SectionResultsScreen({super.key});

  @override
  State<SectionResultsScreen> createState() => _SectionResultsScreenState();
}

class _SectionResultsScreenState extends State<SectionResultsScreen> {
  late Future<List<Object>> _setup;
  String? _sectionId;
  String? _examId;
  Future<List<ExamResult>>? _results;

  @override
  void initState() {
    super.initState();
    final api = context.read<OpsApi>();
    _setup = Future.wait<Object>(<Future<Object>>[api.sections(), api.exams().then((p) => p.items)]);
  }

  void _load() {
    if (_sectionId == null || _examId == null) return;
    setState(() => _results = context.read<OpsApi>().sectionResults(_sectionId!, _examId!));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Class results')),
      body: FutureView<List<Object>>(
        future: _setup,
        onRetry: () {
          final api = context.read<OpsApi>();
          setState(() => _setup = Future.wait<Object>(<Future<Object>>[api.sections(), api.exams().then((p) => p.items)]));
        },
        builder: (ctx, data) {
          final sections = data[0] as List<SectionItem>;
          final exams = data[1] as List<Exam>;
          return Column(
            children: [
              Padding(
                padding: const EdgeInsets.all(12),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: [
                    SizedBox(
                      width: 260,
                      child: pickString('Section', _sectionId, [for (final s in sections) MapEntry(s.id, s.display)], (v) {
                        _sectionId = v;
                        _load();
                      }),
                    ),
                    SizedBox(
                      width: 320,
                      child: pickString('Exam', _examId, [for (final e in exams) MapEntry(e.id, '${e.name} (${titleCase(e.status)})')], (v) {
                        _examId = v;
                        _load();
                      }),
                    ),
                  ],
                ),
              ),
              Expanded(
                child: _results == null
                    ? const EmptyView('Choose a section and an exam', icon: Icons.leaderboard_outlined)
                    : FutureView<List<ExamResult>>(
                        future: _results!,
                        onRetry: _load,
                        builder: (ctx, rows) {
                          if (rows.isEmpty) return const EmptyView('No students or papers found');
                          final ranked = [...rows]..sort((a, b) => (a.position ?? 9999).compareTo(b.position ?? 9999));
                          return SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: SingleChildScrollView(
                              padding: const EdgeInsets.all(12),
                              child: DataTable(
                                columns: const [
                                  DataColumn(label: Text('Pos')),
                                  DataColumn(label: Text('Roll no')),
                                  DataColumn(label: Text('Student')),
                                  DataColumn(label: Text('Total')),
                                  DataColumn(label: Text('%')),
                                  DataColumn(label: Text('Grade')),
                                  DataColumn(label: Text('Result')),
                                ],
                                rows: [
                                  for (final r in ranked)
                                    DataRow(cells: [
                                      DataCell(Text(r.position == null ? '-' : '${r.position}')),
                                      DataCell(Text(r.rollNo)),
                                      DataCell(Text(r.studentName)),
                                      DataCell(Text('${fmtNum(r.totalObtained)} / ${fmtNum(r.totalMarks)}')),
                                      DataCell(Text(fmtNum(r.percentage))),
                                      DataCell(Text(r.grade ?? '-')),
                                      DataCell(r.passed == null
                                          ? const Text('Incomplete')
                                          : StatusChip(r.passed! ? 'pass' : 'fail', label: r.passed! ? 'Pass' : 'Fail')),
                                    ]),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ====================================================================== grade scale

/// Admin: the grade bands used to turn percentages into grades. Saving replaces the whole scale.
class GradeScaleScreen extends StatefulWidget {
  const GradeScaleScreen({super.key});

  @override
  State<GradeScaleScreen> createState() => _GradeScaleScreenState();
}

class _GradeScaleScreenState extends State<GradeScaleScreen> {
  late Future<List<GradeBand>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().gradeScale();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().gradeScale());

  Future<void> _edit(List<GradeBand> bands, {GradeBand? existing}) async {
    final api = context.read<OpsApi>();
    var grade = existing?.grade ?? '';
    var min = existing == null ? '' : fmtNum(existing.minPercentage);
    var max = existing == null ? '' : fmtNum(existing.maxPercentage);
    var gpa = existing?.gpaPoints == null ? '' : fmtNum(existing!.gpaPoints);
    var remark = existing?.remark ?? '';
    var isPass = existing?.isPass ?? true;
    final saved = await showFormDialog(
      context,
      title: existing == null ? 'Add grade' : 'Edit grade ${existing.grade}',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Grade (e.g. A+)', grade, (v) => grade = v),
          formText('From %', min, (v) => min = v, number: true),
          formText('To %', max, (v) => max = v, number: true),
          formText('GPA points (optional)', gpa, (v) => gpa = v, number: true),
          formText('Remark (e.g. Excellent)', remark, (v) => remark = v),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Counts as a pass'),
            value: isPass,
            onChanged: (v) => set(() => isPass = v),
          ),
        ]),
      ),
      validate: () {
        final lo = Validators.parseNumber(min);
        final hi = Validators.parseNumber(max);
        if (lo == null || hi == null || lo < 0 || hi > 100) return 'Percentages must be between 0 and 100';
        if (hi < lo) return '"To %" cannot be below "From %"';
        return Validators.required(grade, 'Grade') ?? Validators.maxLength(grade, 3, 'Grade');
      },
      onSubmit: () {
        final band = GradeBand(
          grade: grade.trim(),
          minPercentage: Validators.parseNumber(min)!,
          maxPercentage: Validators.parseNumber(max)!,
          gpaPoints: Validators.parseNumber(gpa),
          remark: remark.trim(),
          isPass: isPass,
        );
        final updated = <GradeBand>[
          for (final b in bands)
            if (!identical(b, existing)) b,
          band,
        ]..sort((a, b) => b.minPercentage.compareTo(a.minPercentage));
        return api.saveGradeScale(updated);
      },
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Grade scale saved');
    }
  }

  Future<void> _remove(List<GradeBand> bands, GradeBand band) async {
    if (bands.length <= 1) {
      showMessage(context, 'The scale needs at least one grade', error: true);
      return;
    }
    if (!await confirmDialog(context, 'Remove grade ${band.grade}?', 'Results are calculated from the scale, so this changes how marks turn into grades.', yes: 'Remove')) return;
    if (!mounted) return;
    final updated = [
      for (final b in bands)
        if (!identical(b, band)) b,
    ];
    final ok = await runAction(context, () => context.read<OpsApi>().saveGradeScale(updated), success: 'Grade removed');
    if (ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Grade scale'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 760,
        child: FutureView<List<GradeBand>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, bands) => Column(
            children: [
              Expanded(
                child: bands.isEmpty
                    ? const EmptyView('No grades defined')
                    : ListView(
                        children: [
                          for (final b in bands)
                            ListTile(
                              leading: CircleAvatar(child: Text(b.grade)),
                              title: Text('${fmtNum(b.minPercentage)}% to ${fmtNum(b.maxPercentage)}%${b.remark.isEmpty ? '' : '  -  ${b.remark}'}'),
                              subtitle: Text('${b.isPass ? 'Pass' : 'Fail'}${b.gpaPoints == null ? '' : '  -  GPA ${fmtNum(b.gpaPoints)}'}'),
                              onTap: () => _edit(bands, existing: b),
                              trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _remove(bands, b)),
                            ),
                        ],
                      ),
              ),
              Padding(
                padding: const EdgeInsets.all(12),
                child: FilledButton.icon(onPressed: () => _edit(bands), icon: const Icon(Icons.add), label: const Text('Add grade')),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
