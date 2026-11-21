import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/auth.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/paged_list.dart';
import '../common/quick_form.dart';
import '../dashboard/role_scope.dart';
import 'homework_files.dart';
import 'homework_models.dart';

Color _hwColor(Assignment a) {
  if (a.status == 'draft') return Brand.muted;
  if (a.status == 'closed') return Brand.muted;
  return a.isOverdue ? Brand.danger : (a.daysLeft <= 1 ? Brand.warning : Brand.success);
}

String _dueText(Assignment a) {
  if (a.status != 'published') return humanize(a.status);
  if (a.isOverdue) return 'Overdue';
  if (a.daysLeft == 0) return 'Due today';
  if (a.daysLeft == 1) return 'Due tomorrow';
  return 'Due in ${a.daysLeft} days';
}

/// Homework: teachers / admin manage it, students and parents read it (parents pick a child).
class HomeworkPage extends StatelessWidget {
  const HomeworkPage({super.key, required this.role});
  final Role role;

  @override
  Widget build(BuildContext context) {
    if (role == Role.student || role == Role.parent) {
      return PageFrame(
        title: 'Homework',
        subtitle: 'Assignments for your class',
        child: StudentScope(builder: (context, child) => _HomeworkList(studentId: child.studentId, staff: false)),
      );
    }
    return PageFrame(
      title: 'Homework',
      subtitle: role == Role.admin ? 'All homework in the school' : 'Homework you give to your classes',
      child: _StaffHomework(isAdmin: role == Role.admin),
    );
  }
}

// ================================================================== student / parent
class _HomeworkList extends StatefulWidget {
  const _HomeworkList({required this.studentId, required this.staff});
  final String studentId;
  final bool staff;
  @override
  State<_HomeworkList> createState() => _HomeworkListState();
}

class _HomeworkListState extends State<_HomeworkList> {
  bool _upcoming = true;

  @override
  Widget build(BuildContext context) {
    final today = isoDate(DateTime.now());
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: SegmentedButton<bool>(
          segments: const [ButtonSegment(value: true, label: Text('Upcoming')), ButtonSegment(value: false, label: Text('Past'))],
          selected: {_upcoming},
          onSelectionChanged: (s) => setState(() => _upcoming = s.first),
        ),
      ),
      Expanded(
        child: PagedList<Assignment>(
          path: '/assignments',
          query: {
            'student_id': widget.studentId,
            'status': 'published',
            if (_upcoming) 'due_from': today else 'due_to': isoDate(DateTime.now().subtract(const Duration(days: 1))),
            'sort': _upcoming ? 'due_asc' : 'due_desc',
          },
          parse: Assignment.fromJson,
          emptyTitle: _upcoming ? 'No upcoming homework' : 'No past homework',
          emptyIcon: Icons.menu_book_outlined,
          itemBuilder: (context, a, reload) => _HomeworkCard(a: a),
        ),
      ),
    ]);
  }
}

class _HomeworkCard extends StatelessWidget {
  const _HomeworkCard({required this.a, this.trailing});
  final Assignment a;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(a.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
          StatusChip(_dueText(a), color: _hwColor(a)),
          if (trailing != null) trailing!,
        ]),
        const SizedBox(height: 2),
        Text('${a.subjectName} · ${a.sectionLabel} · ${a.teacherName}', style: const TextStyle(color: Brand.muted)),
        Text('Assigned ${formatDate(a.assignedDate)} · Due ${formatDate(a.dueDate)}${a.maxMarks != null ? ' · ${formatNumber(a.maxMarks)} marks' : ''}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
        if ((a.description ?? '').isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(a.description!)),
        if (a.hasAttachment)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: OutlinedButton.icon(onPressed: () => downloadAssignmentAttachment(context, a.id), icon: const Icon(Icons.attach_file, size: 18), label: const Text('Download attachment')),
          ),
      ]),
    );
  }
}

// ================================================================== teacher / admin
class _StaffHomework extends StatefulWidget {
  const _StaffHomework({required this.isAdmin});
  final bool isAdmin;
  @override
  State<_StaffHomework> createState() => _StaffHomeworkState();
}

class _StaffHomeworkState extends State<_StaffHomework> {
  String? _sectionId;
  String? _subjectId;
  String? _status;
  int _key = 0;
  late Future<List<SectionRef>> _sections;
  late Future<List<SubjectRef>> _subjects;

  @override
  void initState() {
    super.initState();
    final l = context.read<Lookups>();
    _sections = l.sections();
    _subjects = l.subjects();
  }

  /// (section, subject) pairs the user may create homework for.
  Future<List<MapEntry<String, String>>> _pairs() async {
    final l = context.read<Lookups>();
    if (widget.isAdmin) return <MapEntry<String, String>>[];
    final mine = await l.myAssignments();
    return mine.map((t) => MapEntry('${t.sectionId}|${t.subjectId}', '${t.sectionLabel} — ${t.subjectName}')).toList();
  }

  Future<void> _create() async {
    final api = context.read<ApiClient>();
    final l = context.read<Lookups>();
    List<MapEntry<String, String>> pairs = <MapEntry<String, String>>[];
    List<SectionRef> sections = <SectionRef>[];
    List<SubjectRef> subjects = <SubjectRef>[];
    try {
      if (widget.isAdmin) {
        sections = await l.sections(all: true);
        subjects = await l.subjects();
      } else {
        pairs = await _pairs();
      }
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    if (!widget.isAdmin && pairs.isEmpty) {
      showSnack(context, 'You have no class/subject assigned yet. Ask the administrator.', error: true);
      return;
    }
    final ok = await showAppDialog<bool>(
      context,
      title: 'New homework',
      builder: (_) => QuickForm(
        fields: [
          if (widget.isAdmin) ...[
            QField('section_id', 'Class / section', QType.dropdown, required: true, options: sections.map((s) => MapEntry(s.id, s.label)).toList()),
            QField('subject_id', 'Subject', QType.dropdown, required: true, options: subjects.map((s) => MapEntry(s.id, s.name)).toList()),
          ] else
            QField('pair', 'Class — subject', QType.dropdown, required: true, initial: pairs.length == 1 ? pairs.first.key : null, options: pairs),
          const QField('title', 'Title', QType.text, required: true),
          const QField('description', 'Instructions', QType.multiline),
          QField('due_date', 'Due date', QType.date, required: true, initial: dateOnly(DateTime.now()).add(const Duration(days: 1))),
          const QField('max_marks', 'Max marks (optional)', QType.number),
          const QField('publish', 'Publish now (students and parents are notified)', QType.toggle, initial: true),
        ],
        submitLabel: 'Create',
        onSubmit: (v) async {
          String sectionId, subjectId;
          if (widget.isAdmin) {
            sectionId = v['section_id'] as String;
            subjectId = v['subject_id'] as String;
          } else {
            final parts = (v['pair'] as String).split('|');
            sectionId = parts[0];
            subjectId = parts[1];
          }
          final marks = (v['max_marks'] as String);
          await api.post('/assignments', body: {
            'section_id': sectionId,
            'subject_id': subjectId,
            'title': v['title'],
            'description': (v['description'] as String).isEmpty ? null : v['description'],
            'due_date': isoDate(v['due_date'] as DateTime),
            'max_marks': marks.isEmpty ? null : marks,
            'status': (v['publish'] as bool) ? 'published' : 'draft',
          });
        },
      ),
    );
    if (ok == true) setState(() => _key++);
  }

  Future<void> _edit(Assignment a, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: 'Edit homework',
      builder: (_) => QuickForm(
        intro: '${a.subjectName} · ${a.sectionLabel}',
        fields: [
          QField('title', 'Title', QType.text, required: true, initial: a.title),
          QField('description', 'Instructions', QType.multiline, initial: a.description),
          QField('due_date', 'Due date', QType.date, required: true, initial: a.dueDate),
          QField('max_marks', 'Max marks (optional)', QType.number, initial: a.maxMarks?.toString()),
          QField('status', 'Status', QType.dropdown, required: true, initial: a.status, options: const [MapEntry('draft', 'Draft'), MapEntry('published', 'Published'), MapEntry('closed', 'Closed')]),
        ],
        onSubmit: (v) {
          final marks = v['max_marks'] as String;
          final body = <String, dynamic>{
            'title': v['title'],
            'description': v['description'],
            'status': v['status'],
            if (marks.isNotEmpty) 'max_marks': marks,
          };
          final due = v['due_date'] as DateTime;
          if (due != a.dueDate) body['due_date'] = isoDate(due); // unchanged dates are not re-validated as "past"
          return api.patch('/assignments/${a.id}', body: body);
        },
      ),
    );
    if (ok == true) await reload();
  }

  Future<void> _attach(Assignment a, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final res = await FilePicker.platform.pickFiles(withData: true, type: FileType.custom, allowedExtensions: const ['pdf', 'png', 'jpg', 'jpeg', 'docx']);
    final f = res?.files.single;
    if (f == null) return;
    if (f.bytes == null) {
      if (mounted) showSnack(context, 'Could not read the selected file', error: true);
      return;
    }
    try {
      await api.upload('/assignments/${a.id}/attachment', field: 'file', bytes: f.bytes!, filename: f.name);
      if (mounted) showSnack(context, 'Attachment uploaded');
      await reload();
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _delete(Assignment a, Future<void> Function() reload) async {
    final ok = await confirmDialog(context, title: 'Delete "${a.title}"?', message: 'This removes the homework and its attachment for everyone.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/assignments/${a.id}');
      await reload();
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Align(
        alignment: Alignment.centerRight,
        child: FilledButton.icon(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New homework')),
      ),
      const SizedBox(height: 10),
      FutureBuilder<List<Object>>(
        future: Future.wait<Object>([_sections, _subjects]),
        builder: (context, snap) {
          final sections = snap.hasData ? snap.data![0] as List<SectionRef> : <SectionRef>[];
          final subjects = snap.hasData ? snap.data![1] as List<SubjectRef> : <SubjectRef>[];
          return FilterBar(children: [
            AppDropdown<String>(label: 'Class / section', value: _sectionId, allowClear: true, items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(), onChanged: (v) => setState(() => _sectionId = v)),
            AppDropdown<String>(label: 'Subject', value: _subjectId, allowClear: true, items: subjects.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.name))).toList(), onChanged: (v) => setState(() => _subjectId = v)),
            AppDropdown<String>(
              label: 'Status',
              value: _status,
              allowClear: true,
              items: const [DropdownMenuItem(value: 'draft', child: Text('Draft')), DropdownMenuItem(value: 'published', child: Text('Published')), DropdownMenuItem(value: 'closed', child: Text('Closed'))],
              onChanged: (v) => setState(() => _status = v),
            ),
          ]);
        },
      ),
      Expanded(
        child: PagedList<Assignment>(
          path: '/assignments',
          reloadKey: _key,
          query: {'section_id': _sectionId, 'subject_id': _subjectId, 'status': _status},
          parse: Assignment.fromJson,
          emptyTitle: 'No homework found',
          emptyMessage: 'Use "New homework" to create one.',
          emptyIcon: Icons.menu_book_outlined,
          itemBuilder: (context, a, reload) => _HomeworkCard(
            a: a,
            trailing: PopupMenuButton<String>(
              onSelected: (v) {
                if (v == 'edit') _edit(a, reload);
                if (v == 'attach') _attach(a, reload);
                if (v == 'delete') _delete(a, reload);
              },
              itemBuilder: (_) => [
                const PopupMenuItem(value: 'edit', child: Text('Edit')),
                PopupMenuItem(value: 'attach', child: Text(a.hasAttachment ? 'Replace attachment' : 'Add attachment')),
                const PopupMenuItem(value: 'delete', child: Text('Delete')),
              ],
            ),
          ),
        ),
      ),
    ]);
  }
}
