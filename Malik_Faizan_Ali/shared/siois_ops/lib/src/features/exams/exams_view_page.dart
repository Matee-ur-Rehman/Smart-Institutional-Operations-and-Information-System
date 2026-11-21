import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/report_download.dart';
import '../dashboard/role_scope.dart';
import 'exams_models.dart';

/// Student / parent: exam date sheet and published results (with result-card PDF).
class ExamsViewPage extends StatelessWidget {
  const ExamsViewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Exams & results',
      subtitle: 'Date sheet and published results',
      child: StudentScope(builder: (context, child) => _Body(child: child)),
    );
  }
}

class _Body extends StatelessWidget {
  const _Body({required this.child});
  final ChildRef child;

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 2,
      child: Column(children: [
        const Align(alignment: Alignment.centerLeft, child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [Tab(text: 'Date sheet'), Tab(text: 'Results')])),
        const SizedBox(height: 12),
        Expanded(child: TabBarView(children: [_DateSheet(child: child), _Results(child: child)])),
      ]),
    );
  }
}

class _DateSheet extends StatefulWidget {
  const _DateSheet({required this.child});
  final ChildRef child;
  @override
  State<_DateSheet> createState() => _DateSheetState();
}

class _DateSheetState extends State<_DateSheet> with AutomaticKeepAliveClientMixin {
  String? _examId;

  @override
  bool get wantKeepAlive => true;

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final api = context.read<ApiClient>();
    return AsyncView<List<Exam>>(
      loader: () async => asMapList(asMap(await api.get('/exams', query: {'page_size': 50}))['items']).map(Exam.fromJson).toList(),
      builder: (context, exams, reload) {
        if (exams.isEmpty) return const EmptyState(icon: Icons.assignment_outlined, title: 'No exams scheduled yet');
        // default: the nearest upcoming / ongoing exam, otherwise the latest one
        _examId ??= (exams.where((e) => e.status == 'ongoing' || e.status == 'scheduled').toList()..sort((a, b) => a.start.compareTo(b.start))).map((e) => e.id).firstOrNull ?? exams.first.id;
        final id = _examId;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Align(
            alignment: Alignment.centerLeft,
            child: SizedBox(
              width: 320,
              child: AppDropdown<String>(
                label: 'Exam',
                value: id,
                items: exams.map((e) => DropdownMenuItem<String>(value: e.id, child: Text(e.name, overflow: TextOverflow.ellipsis))).toList(),
                onChanged: (v) => setState(() => _examId = v),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: AsyncView<List<ExamPaper>>(
              loadKey: id,
              loader: () async => asMapList(await api.get('/exams/$id/schedules', query: {'student_id': widget.child.studentId})).map(ExamPaper.fromJson).toList(),
              builder: (context, papers, reload) => papers.isEmpty
                  ? const EmptyState(icon: Icons.event_note_outlined, title: 'No papers scheduled for this exam yet')
                  : ListView.separated(
                      itemCount: papers.length,
                      separatorBuilder: (context, i) => const SizedBox(height: 8),
                      itemBuilder: (context, i) {
                        final p = papers[i];
                        return AppCard(
                          child: Row(children: [
                            Container(
                              width: 56,
                              padding: const EdgeInsets.symmetric(vertical: 6),
                              decoration: BoxDecoration(color: Brand.primary.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
                              child: Column(children: [
                                Text(p.date.day.toString().padLeft(2, '0'), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 20, color: Brand.primary)),
                                Text(formatDayMonth(p.date).substring(3), style: const TextStyle(color: Brand.primary, fontSize: 12)),
                              ]),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Text(p.subjectName, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                                Text('${formatWeekday(p.date)} · ${formatTimeRange(p.start, p.end)}${(p.room ?? '').isNotEmpty ? ' · Room ${p.room}' : ''}', style: const TextStyle(color: Brand.muted)),
                                Text('Total ${formatNumber(p.total)} marks', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                              ]),
                            ),
                          ]),
                        );
                      },
                    ),
            ),
          ),
        ]);
      },
    );
  }
}

class _Results extends StatelessWidget {
  const _Results({required this.child});
  final ChildRef child;

  Color _resultColor(String r) => r == 'pass' ? Brand.success : (r == 'fail' ? Brand.danger : Brand.muted);

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<Map<String, dynamic>>>(
      loader: () async => asMapList(asMap(await api.get('/results/students/${child.studentId}'))['results']),
      builder: (context, results, reload) {
        if (results.isEmpty) return const EmptyState(icon: Icons.emoji_events_outlined, title: 'No results published yet', message: 'Results appear here after the school publishes them.');
        return ListView.separated(
          itemCount: results.length,
          separatorBuilder: (context, i) => const SizedBox(height: 10),
          itemBuilder: (context, i) {
            final r = results[i];
            final exam = asMap(r['exam']);
            final subjects = asMapList(r['subjects']);
            final result = asStr(r['result'], 'incomplete');
            final pos = r['position'];
            return AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(asStr(exam['name']), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17))),
                  StatusChip(result, color: _resultColor(result)),
                ]),
                const SizedBox(height: 4),
                Wrap(spacing: 16, runSpacing: 4, children: [
                  Text('${formatNumber(asDouble(r['total_obtained']))} / ${formatNumber(asDouble(r['total_marks']))}', style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text(formatPercent(asDoubleN(r['percentage'])), style: const TextStyle(fontWeight: FontWeight.w600)),
                  Text('Grade ${asStr(r['grade'], '–')}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  if (pos != null) Text('Position ${asStr(pos)} of ${asStr(r['section_size'])}', style: const TextStyle(color: Brand.muted)),
                ]),
                const Divider(height: 20),
                for (final s in subjects)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(children: [
                      Expanded(child: Text(asStr(s['subject_name']))),
                      Text(
                        asStr(s['state']) == 'absent'
                            ? 'Absent'
                            : asStr(s['state']) == 'pending'
                                ? 'Pending'
                                : '${formatNumber(asDouble(s['marks_obtained']))} / ${formatNumber(asDouble(s['total_marks']))}',
                        style: TextStyle(fontWeight: FontWeight.w600, color: s['passed'] == false ? Brand.danger : null),
                      ),
                      SizedBox(width: 36, child: Text(asStr(s['grade'], ''), textAlign: TextAlign.right, style: const TextStyle(fontWeight: FontWeight.w700))),
                    ]),
                  ),
                const SizedBox(height: 8),
                ReportButton(label: 'Download result card', path: '/reports/result-card/${child.studentId}', query: {'exam_id': asStr(exam['id'])}, fallbackName: 'result_card.pdf'),
              ]),
            );
          },
        );
      },
    );
  }
}
