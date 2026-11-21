import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/quick_form.dart';

/// Admin: academic years, classes & sections, subjects and teaching assignments (who teaches what, where).
class AcademicsPage extends StatelessWidget {
  const AcademicsPage({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: PageFrame(
        title: 'Classes & Subjects',
        subtitle: 'Academic years, classes, sections, subjects and teaching assignments',
        child: Column(children: const [
          Align(
            alignment: Alignment.centerLeft,
            child: TabBar(isScrollable: true, tabAlignment: TabAlignment.start, tabs: [
              Tab(text: 'Academic years'),
              Tab(text: 'Classes & sections'),
              Tab(text: 'Subjects'),
              Tab(text: 'Teaching'),
            ]),
          ),
          SizedBox(height: 12),
          Expanded(child: TabBarView(children: [_YearsTab(), _ClassesTab(), _SubjectsTab(), _TeachingTab()])),
        ]),
      ),
    );
  }
}

Widget _addButton(String label, VoidCallback onPressed) => Align(
      alignment: Alignment.centerRight,
      child: Padding(padding: const EdgeInsets.only(bottom: 10), child: FilledButton.icon(onPressed: onPressed, icon: const Icon(Icons.add), label: Text(label))),
    );

void _afterChange(BuildContext context) => context.read<Lookups>().clear();

// ================================================================== academic years
class _YearsTab extends StatelessWidget {
  const _YearsTab();

  Future<void> _form(BuildContext context, Future<void> Function() reload, {Map<String, dynamic>? year}) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: year == null ? 'New academic year' : 'Edit academic year',
      builder: (_) => QuickForm(
        fields: [
          QField('name', 'Name', QType.text, required: true, initial: year?['name'], helper: 'e.g. 2027-2028'),
          QField('start_date', 'Start date', QType.date, required: true, initial: asDateN(year?['start_date'])),
          QField('end_date', 'End date', QType.date, required: true, initial: asDateN(year?['end_date'])),
        ],
        onSubmit: (v) async {
          final body = {'name': v['name'], 'start_date': isoDate(v['start_date'] as DateTime), 'end_date': isoDate(v['end_date'] as DateTime)};
          if (year == null) {
            await api.post('/academic-years', body: body);
          } else {
            await api.patch('/academic-years/${asStr(year['id'])}', body: body);
          }
        },
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  Future<void> _setCurrent(BuildContext context, Map<String, dynamic> y, Future<void> Function() reload) async {
    final ok = await confirmDialog(context,
        title: 'Make ${asStr(y['name'])} the current year?',
        message: 'New homework, exams, timetables and fees will belong to this year. Only one year can be current.',
        confirmLabel: 'Make current');
    if (!ok || !context.mounted) return;
    try {
      await context.read<ApiClient>().post('/academic-years/${asStr(y['id'])}/set-current');
      if (!context.mounted) return;
      if (context.mounted) _afterChange(context);
      showSnack(context, 'Current academic year updated');
      await reload();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<Map<String, dynamic>>>(
      loader: () async => asMapList(await api.get('/academic-years')),
      builder: (context, years, reload) => Column(children: [
        _addButton('New academic year', () => _form(context, reload)),
        Expanded(
          child: ListView.separated(
            itemCount: years.length,
            separatorBuilder: (context, i) => const SizedBox(height: 8),
            itemBuilder: (context, i) {
              final y = years[i];
              final current = asBool(y['is_current']);
              return AppCard(
                child: Row(children: [
                  Icon(Icons.event_note_outlined, color: current ? Brand.success : Brand.muted),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Text(asStr(y['name']), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                        const SizedBox(width: 8),
                        if (current) const StatusChip('current', color: Brand.success),
                      ]),
                      Text('${formatDate(asDateN(y['start_date']))} – ${formatDate(asDateN(y['end_date']))}', style: const TextStyle(color: Brand.muted)),
                    ]),
                  ),
                  if (!current) TextButton(onPressed: () => _setCurrent(context, y, reload), child: const Text('Make current')),
                  IconButton(tooltip: 'Edit', icon: const Icon(Icons.edit_outlined), onPressed: () => _form(context, reload, year: y)),
                ]),
              );
            },
          ),
        ),
      ]),
    );
  }
}

// ================================================================== classes & sections
class _ClassData {
  _ClassData(this.classes, this.sections);
  final List<Map<String, dynamic>> classes;
  final List<Map<String, dynamic>> sections;
}

class _ClassesTab extends StatelessWidget {
  const _ClassesTab();

  Future<void> _classForm(BuildContext context, Future<void> Function() reload, {Map<String, dynamic>? c}) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: c == null ? 'New class' : 'Edit class',
      builder: (_) => QuickForm(
        fields: [
          QField('name', 'Class name', QType.text, required: true, initial: c?['name'], helper: 'e.g. Class 8'),
          QField('grade_level', 'Grade level (0-12)', QType.number, required: true, initial: c?['grade_level']),
          if (c != null) QField('is_active', 'Active class', QType.toggle, initial: asBool(c['is_active'], true)),
        ],
        onSubmit: (v) async {
          final body = <String, dynamic>{'name': v['name'], 'grade_level': int.parse(v['grade_level'] as String)};
          if (c == null) {
            await api.post('/classes', body: body);
          } else {
            body['is_active'] = v['is_active'];
            await api.patch('/classes/${asStr(c['id'])}', body: body);
          }
        },
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  Future<void> _sectionForm(BuildContext context, Future<void> Function() reload, {required Map<String, dynamic> cls, Map<String, dynamic>? section}) async {
    final api = context.read<ApiClient>();
    final List<TeacherRef> teachers;
    try {
      teachers = await context.read<Lookups>().teachers();
    } catch (e) {
      if (context.mounted) showError(context, e);
      return;
    }
    if (!context.mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: section == null ? 'New section in ${asStr(cls['name'])}' : 'Edit section ${asStr(section['label'])}',
      builder: (_) => QuickForm(
        fields: [
          QField('name', 'Section name', QType.text, required: true, initial: section?['name'], helper: 'e.g. A'),
          QField('class_teacher_id', 'Class teacher', QType.dropdown,
              clearable: true, initial: asStrN(section?['class_teacher_id']), options: teachers.map((t) => MapEntry(t.id, '${t.fullName} (${t.employeeNo})')).toList()),
          if (section != null) QField('is_active', 'Active section', QType.toggle, initial: asBool(section['is_active'], true)),
        ],
        onSubmit: (v) async {
          final body = <String, dynamic>{'name': v['name'], 'class_teacher_id': v['class_teacher_id']};
          if (section == null) {
            body['class_id'] = asStr(cls['id']);
            await api.post('/sections', body: body);
          } else {
            body['is_active'] = v['is_active'];
            await api.patch('/sections/${asStr(section['id'])}', body: body);
          }
        },
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<_ClassData>(
      loader: () async => _ClassData(
        asMapList(await api.get('/classes', query: {'include_inactive': true})),
        asMapList(await api.get('/sections', query: {'include_inactive': true})),
      ),
      builder: (context, data, reload) => Column(children: [
        _addButton('New class', () => _classForm(context, reload)),
        Expanded(
          child: data.classes.isEmpty
              ? const EmptyState(icon: Icons.account_tree_outlined, title: 'No classes yet')
              : ListView.separated(
                  itemCount: data.classes.length,
                  separatorBuilder: (context, i) => const SizedBox(height: 10),
                  itemBuilder: (context, i) {
                    final c = data.classes[i];
                    final secs = data.sections.where((s) => asStr(s['class_id']) == asStr(c['id'])).toList();
                    return AppCard(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Row(children: [
                          Expanded(
                            child: Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 8, children: [
                              Text(asStr(c['name']), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                              Text('Grade ${asStr(c['grade_level'])}', style: const TextStyle(color: Brand.muted)),
                              if (!asBool(c['is_active'], true)) const StatusChip('inactive', color: Brand.danger),
                            ]),
                          ),
                          IconButton(tooltip: 'Edit class', icon: const Icon(Icons.edit_outlined), onPressed: () => _classForm(context, reload, c: c)),
                          TextButton.icon(onPressed: () => _sectionForm(context, reload, cls: c), icon: const Icon(Icons.add, size: 18), label: const Text('Section')),
                        ]),
                        if (secs.isEmpty) const Padding(padding: EdgeInsets.only(top: 4), child: Text('No sections yet.', style: TextStyle(color: Brand.muted))),
                        for (final s in secs)
                          ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            leading: const Icon(Icons.meeting_room_outlined),
                            title: Row(children: [
                              Text(asStr(s['label'])),
                              const SizedBox(width: 8),
                              if (!asBool(s['is_active'], true)) const StatusChip('inactive', color: Brand.danger),
                            ]),
                            subtitle: Text('${asStr(s['student_count'], '0')} students · Class teacher: ${asStr(s['class_teacher_name'], 'not set')}'),
                            trailing: IconButton(tooltip: 'Edit section', icon: const Icon(Icons.edit_outlined, size: 20), onPressed: () => _sectionForm(context, reload, cls: c, section: s)),
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

// ================================================================== subjects
class _SubjectsTab extends StatelessWidget {
  const _SubjectsTab();

  Future<void> _form(BuildContext context, Future<void> Function() reload, {Map<String, dynamic>? s}) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: s == null ? 'New subject' : 'Edit subject',
      builder: (_) => QuickForm(
        fields: [
          QField('name', 'Subject name', QType.text, required: true, initial: s?['name']),
          QField('code', 'Code', QType.text, required: true, initial: s?['code'], helper: 'Letters, digits, - or _ (e.g. MATH)'),
          if (s != null) QField('is_active', 'Active subject', QType.toggle, initial: asBool(s['is_active'], true)),
        ],
        onSubmit: (v) async {
          final body = <String, dynamic>{'name': v['name'], 'code': v['code']};
          if (s == null) {
            await api.post('/subjects', body: body);
          } else {
            body['is_active'] = v['is_active'];
            await api.patch('/subjects/${asStr(s['id'])}', body: body);
          }
        },
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<Map<String, dynamic>>>(
      loader: () async => asMapList(await api.get('/subjects', query: {'include_inactive': true})),
      builder: (context, subjects, reload) => Column(children: [
        _addButton('New subject', () => _form(context, reload)),
        Expanded(
          child: subjects.isEmpty
              ? const EmptyState(icon: Icons.menu_book_outlined, title: 'No subjects yet')
              : ListView.separated(
                  itemCount: subjects.length,
                  separatorBuilder: (context, i) => const SizedBox(height: 8),
                  itemBuilder: (context, i) {
                    final s = subjects[i];
                    return AppCard(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      child: Row(children: [
                        const Icon(Icons.menu_book_outlined, color: Brand.primary),
                        const SizedBox(width: 12),
                        Expanded(child: Text('${asStr(s['name'])}  ·  ${asStr(s['code'])}', style: const TextStyle(fontWeight: FontWeight.w600))),
                        if (!asBool(s['is_active'], true)) const StatusChip('inactive', color: Brand.danger),
                        IconButton(tooltip: 'Edit', icon: const Icon(Icons.edit_outlined), onPressed: () => _form(context, reload, s: s)),
                      ]),
                    );
                  },
                ),
        ),
      ]),
    );
  }
}

// ================================================================== teaching assignments
class _TeachingTab extends StatelessWidget {
  const _TeachingTab();

  Future<void> _assign(BuildContext context, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final lookups = context.read<Lookups>();
    final List<TeacherRef> teachers;
    final List<SectionRef> sections;
    final List<SubjectRef> subjects;
    try {
      teachers = await lookups.teachers();
      sections = await lookups.sections(all: true);
      subjects = await lookups.subjects();
    } catch (e) {
      if (context.mounted) showError(context, e);
      return;
    }
    if (!context.mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: 'Assign a teacher',
      builder: (_) => QuickForm(
        intro: 'One teacher teaches each subject in each section. To replace a teacher, use "Change teacher" on the existing line.',
        fields: [
          QField('section_id', 'Class / section', QType.dropdown, required: true, options: sections.map((s) => MapEntry(s.id, s.label)).toList()),
          QField('subject_id', 'Subject', QType.dropdown, required: true, options: subjects.map((s) => MapEntry(s.id, s.name)).toList()),
          QField('teacher_id', 'Teacher', QType.dropdown, required: true, options: teachers.map((t) => MapEntry(t.id, '${t.fullName} (${t.employeeNo})')).toList()),
        ],
        submitLabel: 'Assign',
        onSubmit: (v) => api.post('/teacher-assignments', body: {'section_id': v['section_id'], 'subject_id': v['subject_id'], 'teacher_id': v['teacher_id']}),
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  Future<void> _change(BuildContext context, Map<String, dynamic> a, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final List<TeacherRef> teachers;
    try {
      teachers = await context.read<Lookups>().teachers();
    } catch (e) {
      if (context.mounted) showError(context, e);
      return;
    }
    if (!context.mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: 'Change teacher',
      builder: (_) => QuickForm(
        intro: '${asStr(a['subject_name'])} in ${asStr(a['section_label'])}',
        fields: [QField('teacher_id', 'New teacher', QType.dropdown, required: true, initial: asStrN(a['teacher_id']), options: teachers.map((t) => MapEntry(t.id, '${t.fullName} (${t.employeeNo})')).toList())],
        onSubmit: (v) => api.patch('/teacher-assignments/${asStr(a['id'])}', body: {'teacher_id': v['teacher_id']}),
      ),
    );
    if (ok == true) {
      if (context.mounted) _afterChange(context);
      await reload();
    }
  }

  Future<void> _remove(BuildContext context, Map<String, dynamic> a, Future<void> Function() reload) async {
    final ok = await confirmDialog(context,
        title: 'Remove assignment?',
        message: '${asStr(a['teacher_name'])} will no longer teach ${asStr(a['subject_name'])} in ${asStr(a['section_label'])}. Existing homework and marks stay, but they can no longer add new ones.',
        confirmLabel: 'Remove',
        destructive: true);
    if (!ok || !context.mounted) return;
    try {
      await context.read<ApiClient>().delete('/teacher-assignments/${asStr(a['id'])}');
      if (!context.mounted) return;
      if (context.mounted) _afterChange(context);
      await reload();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<List<Map<String, dynamic>>>(
      loader: () async => asMapList(await api.get('/teacher-assignments')),
      builder: (context, rows, reload) {
        final groups = <String, List<Map<String, dynamic>>>{};
        for (final r in rows) {
          groups.putIfAbsent(asStr(r['section_label'], '—'), () => <Map<String, dynamic>>[]).add(r);
        }
        final keys = groups.keys.toList()..sort();
        return Column(children: [
          _addButton('Assign teacher', () => _assign(context, reload)),
          Expanded(
            child: keys.isEmpty
                ? const EmptyState(icon: Icons.assignment_ind_outlined, title: 'No teaching assignments yet', message: 'Assign teachers to subjects in each section for the current year.')
                : ListView.separated(
                    itemCount: keys.length,
                    separatorBuilder: (context, i) => const SizedBox(height: 10),
                    itemBuilder: (context, i) => AppCard(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(keys[i], style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                        for (final a in groups[keys[i]]!)
                          ListTile(
                            dense: true,
                            contentPadding: EdgeInsets.zero,
                            title: Text(asStr(a['subject_name'])),
                            subtitle: Text(asStr(a['teacher_name'])),
                            trailing: Wrap(children: [
                              IconButton(tooltip: 'Change teacher', icon: const Icon(Icons.swap_horiz), onPressed: () => _change(context, a, reload)),
                              IconButton(tooltip: 'Remove', icon: const Icon(Icons.delete_outline, color: Brand.danger), onPressed: () => _remove(context, a, reload)),
                            ]),
                          ),
                      ]),
                    ),
                  ),
          ),
        ]);
      },
    );
  }
}
