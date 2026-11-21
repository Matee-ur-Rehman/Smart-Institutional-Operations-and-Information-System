import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/paged_list.dart';
import '../common/quick_form.dart';
import 'exam_detail_page.dart';
import 'exams_models.dart';
import 'grade_scale_tab.dart';

/// Admin: create / schedule exams, enter or publish results, edit the grade scale. Teacher: see exams, enter marks.
class ExamsListPage extends StatelessWidget {
  const ExamsListPage({super.key, required this.isAdmin});
  final bool isAdmin;

  @override
  Widget build(BuildContext context) {
    if (!isAdmin) {
      return PageFrame(title: 'Exams & results', subtitle: 'Open an exam to enter marks for your papers', child: const _ExamsTab(isAdmin: false));
    }
    return PageFrame(
      title: 'Exams & results',
      subtitle: 'Exams, papers, marks, results and grading',
      child: DefaultTabController(
        length: 2,
        child: Column(children: const [
          Align(alignment: Alignment.centerLeft, child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [Tab(text: 'Exams'), Tab(text: 'Grade scale')])),
          SizedBox(height: 12),
          Expanded(child: TabBarView(children: [_ExamsTab(isAdmin: true), GradeScaleTab()])),
        ]),
      ),
    );
  }
}

class _ExamsTab extends StatefulWidget {
  const _ExamsTab({required this.isAdmin});
  final bool isAdmin;
  @override
  State<_ExamsTab> createState() => _ExamsTabState();
}

class _ExamsTabState extends State<_ExamsTab> {
  String? _status;
  int _key = 0;

  Future<void> _form({Exam? exam}) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: exam == null ? 'New exam' : 'Edit exam',
      builder: (_) => QuickForm(
        fields: [
          QField('name', 'Exam name', QType.text, required: true, initial: exam?.name, helper: 'e.g. Mid-term 2026'),
          QField('exam_type', 'Type', QType.dropdown, required: true, initial: exam?.examType ?? 'monthly', options: kExamTypes),
          QField('start_date', 'Starts', QType.date, required: true, initial: exam?.start),
          QField('end_date', 'Ends', QType.date, required: true, initial: exam?.end),
          if (exam == null)
            const QField('status', 'Status', QType.dropdown, required: true, initial: 'draft', options: [MapEntry('draft', 'Draft (hidden from teachers and parents)'), MapEntry('scheduled', 'Scheduled (visible)')])
          else if (!exam.published)
            QField('status', 'Status', QType.dropdown, required: true, initial: exam.status, options: const [
              MapEntry('draft', 'Draft'),
              MapEntry('scheduled', 'Scheduled'),
              MapEntry('ongoing', 'Ongoing'),
              MapEntry('completed', 'Completed'),
            ]),
        ],
        onSubmit: (v) {
          final body = <String, dynamic>{
            'name': v['name'],
            'exam_type': v['exam_type'],
            'start_date': isoDate(v['start_date'] as DateTime),
            'end_date': isoDate(v['end_date'] as DateTime),
            if (v.containsKey('status') && v['status'] != null) 'status': v['status'],
          };
          return exam == null ? api.post('/exams', body: body) : api.patch('/exams/${exam.id}', body: body);
        },
      ),
    );
    if (ok == true) setState(() => _key++);
  }

  Future<void> _delete(Exam e) async {
    final ok = await confirmDialog(context, title: 'Delete "${e.name}"?', message: 'Its papers and entered marks are deleted too. Only draft exams can be deleted.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/exams/${e.id}');
      if (mounted) setState(() => _key++);
    } catch (err) {
      if (mounted) showError(context, err);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (widget.isAdmin)
        Align(alignment: Alignment.centerRight, child: FilledButton.icon(onPressed: () => _form(), icon: const Icon(Icons.add), label: const Text('New exam'))),
      FilterBar(children: [
        AppDropdown<String>(
          label: 'Status',
          value: _status,
          allowClear: true,
          items: [
            if (widget.isAdmin) const DropdownMenuItem(value: 'draft', child: Text('Draft')),
            const DropdownMenuItem(value: 'scheduled', child: Text('Scheduled')),
            const DropdownMenuItem(value: 'ongoing', child: Text('Ongoing')),
            const DropdownMenuItem(value: 'completed', child: Text('Completed')),
            const DropdownMenuItem(value: 'results_published', child: Text('Results published')),
          ],
          onChanged: (v) => setState(() => _status = v),
        ),
      ]),
      Expanded(
        child: PagedList<Exam>(
          path: '/exams',
          reloadKey: _key,
          query: {'status': _status},
          parse: Exam.fromJson,
          emptyTitle: 'No exams yet',
          emptyMessage: widget.isAdmin ? 'Create the first exam with "New exam".' : 'Exams appear here once the school schedules them.',
          emptyIcon: Icons.assignment_outlined,
          itemBuilder: (context, e, reload) => AppCard(
            onTap: () async {
              await Navigator.of(context).push<void>(MaterialPageRoute<void>(builder: (_) => ExamDetailPage(exam: e, isAdmin: widget.isAdmin)));
              await reload();
            },
            child: Row(children: [
              const Icon(Icons.assignment_outlined, color: Brand.primary),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(e.name, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                  Text('${humanize(e.examType)} · ${formatDate(e.start)} – ${formatDate(e.end)} · ${e.scheduleCount} paper(s)', style: const TextStyle(color: Brand.muted)),
                ]),
              ),
              StatusChip(e.status, color: examStatusColor(e.status)),
              if (widget.isAdmin)
                PopupMenuButton<String>(
                  onSelected: (v) {
                    if (v == 'edit') _form(exam: e);
                    if (v == 'delete') _delete(e);
                  },
                  itemBuilder: (_) => [
                    const PopupMenuItem(value: 'edit', child: Text('Edit')),
                    if (e.status == 'draft') const PopupMenuItem(value: 'delete', child: Text('Delete')),
                  ],
                ),
            ]),
          ),
        ),
      ),
    ]);
  }
}
