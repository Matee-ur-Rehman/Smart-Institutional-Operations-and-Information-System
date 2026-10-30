import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

/// Homework list for every role.
///  * students: their own section; parents: pass the selected child's [studentId]
///  * teachers/admin ([canManage]): create, edit, close and delete
/// Student submission of homework is disabled by project decision (docs/INTEGRATION_GUIDE.md section 12).
class HomeworkScreen extends StatefulWidget {
  const HomeworkScreen({super.key, this.studentId, this.canManage = false});

  final String? studentId;
  final bool canManage;

  @override
  State<HomeworkScreen> createState() => _HomeworkScreenState();
}

class _HomeworkScreenState extends State<HomeworkScreen> {
  late Future<Paged<Assignment>> _future;
  String? _status;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Paged<Assignment>> _load() =>
      context.read<OpsApi>().assignments(studentId: widget.studentId, status: _status);

  void _reload() => setState(() => _future = _load());

  Future<void> _openForm({Assignment? existing}) async {
    final api = context.read<OpsApi>();
    final role = context.read<AuthState>().user?.role ?? '';
    var teaching = <TeachingItem>[];
    var sections = <SectionItem>[];
    var subjects = <SubjectItem>[];
    if (existing == null) {
      try {
        if (role == 'teacher') {
          teaching = await api.myTeaching();
        } else {
          sections = await api.sections();
          subjects = await api.subjects();
        }
      } on ApiException catch (e) {
        if (mounted) showMessage(context, e.message, error: true);
        return;
      }
    }
    if (!mounted) return;
    if (existing == null && role == 'teacher' && teaching.isEmpty) {
      showMessage(context, 'You are not assigned to any class and subject yet. Ask the admin to assign you.', error: true);
      return;
    }

    var title = existing?.title ?? '';
    var description = existing?.description ?? '';
    var maxMarks = existing?.maxMarks == null ? '' : fmtNum(existing!.maxMarks);
    DateTime? due = existing?.dueDate;
    var publishNow = true;
    var status = existing?.status ?? 'published';
    int? pair;
    String? sectionId;
    String? subjectId;

    final saved = await showFormDialog(
      context,
      title: existing == null ? 'New homework' : 'Edit homework',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          if (existing == null && role == 'teacher')
            PickerField<int>(
              label: 'Class and subject',
              value: pair,
              items: [
                for (var i = 0; i < teaching.length; i++)
                  DropdownMenuItem<int>(value: i, child: Text('${teaching[i].sectionName} - ${teaching[i].subjectName}')),
              ],
              onChanged: (v) => set(() => pair = v),
            ),
          if (existing == null && role != 'teacher')
            pickString('Section', sectionId, [for (final s in sections) MapEntry(s.id, s.display)],
                (v) => set(() => sectionId = v)),
          if (existing == null && role != 'teacher')
            pickString('Subject', subjectId, [for (final s in subjects) MapEntry(s.id, s.name)],
                (v) => set(() => subjectId = v)),
          formText('Title', title, (v) => title = v),
          formText('Description (optional)', description, (v) => description = v, maxLines: 4),
          DateField(
            label: 'Due date',
            value: due,
            firstDate: existing == null ? DateTime.now() : null,
            onChanged: (d) => set(() => due = d),
          ),
          formText('Maximum marks (optional)', maxMarks, (v) => maxMarks = v, number: true),
          if (existing == null)
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Publish now'),
              subtitle: const Text('Students and parents are notified when published'),
              value: publishNow,
              onChanged: (v) => set(() => publishNow = v),
            )
          else
            pickString('Status', status, const [
              MapEntry('draft', 'Draft'),
              MapEntry('published', 'Published'),
              MapEntry('closed', 'Closed'),
            ], (v) => set(() => status = v ?? status)),
        ]),
      ),
      validate: () {
        if (existing == null) {
          if (role == 'teacher' && pair == null) return 'Choose a class and subject';
          if (role != 'teacher' && (sectionId == null || subjectId == null)) return 'Choose a section and subject';
        }
        return Validators.minLength(title, 3, 'Title') ??
            Validators.maxLength(title, 200, 'Title') ??
            Validators.optionalPositive(maxMarks, label: 'Maximum marks') ??
            (existing == null
                ? Validators.notPastDate(due, label: 'Due date')
                : Validators.requiredDate(due, 'Due date'));
      },
      onSubmit: () {
        final marks = Validators.parseNumber(maxMarks);
        final body = <String, dynamic>{
          'title': title.trim(),
          'description': description.trim().isEmpty ? null : description.trim(),
          'due_date': ymd(due!),
          'max_marks': marks,
        };
        if (existing == null) {
          if (role == 'teacher') {
            body['section_id'] = teaching[pair!].sectionId;
            body['subject_id'] = teaching[pair!].subjectId;
          } else {
            body['section_id'] = sectionId;
            body['subject_id'] = subjectId;
          }
          body['status'] = publishNow ? 'published' : 'draft';
          return api.createAssignment(body);
        }
        body['status'] = status;
        return api.updateAssignment(existing.id, body);
      },
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, existing == null ? 'Homework saved' : 'Homework updated');
    }
  }

  Future<void> _delete(Assignment a) async {
    if (!await confirmDialog(context, 'Delete homework?', '"${a.title}" will be removed for everyone.', yes: 'Delete')) return;
    if (!mounted) return;
    final ok = await runAction(context, () => context.read<OpsApi>().deleteAssignment(a.id), success: 'Homework deleted');
    if (ok) _reload();
  }

  void _details(Assignment a) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(a.title),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              InfoRow('Subject', a.subjectName),
              InfoRow('Class', a.sectionName),
              InfoRow('Teacher', a.teacherName),
              InfoRow('Given on', fmtDate(a.assignedDate)),
              InfoRow('Due on', fmtDate(a.dueDate)),
              if (a.maxMarks != null) InfoRow('Marks', fmtNum(a.maxMarks)),
              const SizedBox(height: 8),
              Text(a.description.isEmpty ? 'No description.' : a.description),
              if (a.hasAttachment)
                const Padding(
                  padding: EdgeInsets.only(top: 12),
                  child: Text('This homework has an attachment (viewing attachments is not available in the app yet).',
                      style: TextStyle(fontStyle: FontStyle.italic)),
                ),
            ],
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Homework'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      floatingActionButton: widget.canManage
          ? FloatingActionButton.extended(onPressed: () => _openForm(), icon: const Icon(Icons.add), label: const Text('New homework'))
          : null,
      body: ContentWidth(
        child: Column(
          children: [
            if (widget.canManage)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                child: Wrap(
                  spacing: 8,
                  children: [
                    for (final s in const <String?>[null, 'draft', 'published', 'closed'])
                      ChoiceChip(
                        label: Text(s == null ? 'All' : titleCase(s)),
                        selected: _status == s,
                        onSelected: (_) {
                          _status = s;
                          _reload();
                        },
                      ),
                  ],
                ),
              ),
            Expanded(
              child: FutureView<Paged<Assignment>>(
                future: _future,
                onRetry: _reload,
                builder: (ctx, page) {
                  if (page.items.isEmpty) return const EmptyView('No homework yet', icon: Icons.menu_book_outlined);
                  return ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 8, 12, 88),
                    itemCount: page.items.length,
                    itemBuilder: (ctx, i) {
                      final a = page.items[i];
                      return Card(
                        child: ListTile(
                          onTap: () => _details(a),
                          title: Text(a.title, style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('${a.subjectName} - ${a.sectionName}'),
                                Text(
                                  'Due ${fmtDate(a.dueDate)}${a.isOverdue ? '  (overdue)' : ''}',
                                  style: TextStyle(color: a.isOverdue ? Colors.red.shade700 : null),
                                ),
                              ],
                            ),
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (widget.canManage || a.status != 'published') StatusChip(a.status),
                              if (widget.canManage)
                                PopupMenuButton<String>(
                                  onSelected: (v) => v == 'edit' ? _openForm(existing: a) : _delete(a),
                                  itemBuilder: (_) => const [
                                    PopupMenuItem(value: 'edit', child: Text('Edit')),
                                    PopupMenuItem(value: 'delete', child: Text('Delete')),
                                  ],
                                ),
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
