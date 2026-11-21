import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/paged_list.dart';
import '../common/quick_form.dart';

const List<MapEntry<String, String>> _kAudiences = <MapEntry<String, String>>[
  MapEntry('all', 'Everyone'),
  MapEntry('teachers', 'Teachers'),
  MapEntry('students', 'Students'),
  MapEntry('parents', 'Parents'),
  MapEntry('class', 'A specific class / section'),
];
const List<MapEntry<String, String>> _kPriorities = <MapEntry<String, String>>[
  MapEntry('normal', 'Normal'),
  MapEntry('important', 'Important'),
  MapEntry('urgent', 'Urgent'),
];

class _Ann {
  _Ann(this.json);
  final Map<String, dynamic> json;
  String get id => asStr(json['id']);
  String get title => asStr(json['title']);
  String get body => asStr(json['body']);
  String get audience => asStr(json['audience']);
  String get target => asStr(json['target_label']);
  String get priority => asStr(json['priority'], 'normal');
  String get status => asStr(json['status']);
  String? get sectionId => asStrN(json['section_id']);
  DateTime? get publishAt => asDateN(json['publish_at']);
  DateTime? get expiresAt => asDateN(json['expires_at']);
  String get by => asStr(json['created_by_name']);
}

class AnnouncementsPage extends StatefulWidget {
  const AnnouncementsPage({super.key, required this.isAdmin});
  final bool isAdmin;
  @override
  State<AnnouncementsPage> createState() => _AnnouncementsPageState();
}

class _AnnouncementsPageState extends State<AnnouncementsPage> {
  String? _status; // admin only: null = live (published and not expired)
  int _key = 0;

  Future<void> _form({_Ann? ann}) async {
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
      title: ann == null ? 'New announcement' : 'Edit announcement',
      width: 600,
      builder: (_) => QuickForm(
        fields: [
          QField('title', 'Title', QType.text, required: true, initial: ann?.title),
          QField('body', 'Message', QType.multiline, required: true, initial: ann?.body),
          QField('audience', 'Audience', QType.dropdown, required: true, initial: ann?.audience ?? 'all', options: _kAudiences),
          QField('section_id', 'Section (only for "specific class")', QType.dropdown, clearable: true, initial: ann?.sectionId, options: sections.map((s) => MapEntry(s.id, s.label)).toList()),
          QField('priority', 'Priority', QType.dropdown, required: true, initial: ann?.priority ?? 'normal', options: _kPriorities),
          QField('expires_on', 'Expires on (optional)', QType.date, clearable: true, initial: ann?.expiresAt == null ? null : dateOnly(ann!.expiresAt!.toLocal())),
          if (ann == null || ann.status != 'archived')
            QField('status', 'Status', QType.dropdown, required: true, initial: ann?.status ?? 'published', options: const [MapEntry('published', 'Publish now (users are notified)'), MapEntry('draft', 'Save as draft')]),
        ],
        onSubmit: (v) {
          final audience = v['audience'] as String;
          final sectionId = audience == 'class' ? v['section_id'] : null;
          if (audience == 'class' && sectionId == null) {
            throw ApiException(422, 'validation_error', 'Please choose a section', fieldErrors: const [FieldError('section_id', 'Choose the section for a class announcement')]);
          }
          final exp = v['expires_on'] as DateTime?;
          final body = <String, dynamic>{
            'title': v['title'],
            'body': v['body'],
            'audience': audience,
            'section_id': sectionId,
            'priority': v['priority'],
            'expires_at': exp == null ? null : DateTime(exp.year, exp.month, exp.day, 23, 59).toUtc().toIso8601String(),
            if (v.containsKey('status')) 'status': v['status'],
          };
          return ann == null ? api.post('/announcements', body: body) : api.patch('/announcements/${ann.id}', body: body);
        },
      ),
    );
    if (ok == true) setState(() => _key++);
  }

  Future<void> _archive(_Ann a) async {
    try {
      await context.read<ApiClient>().post('/announcements/${a.id}/archive');
      if (mounted) setState(() => _key++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _delete(_Ann a) async {
    final ok = await confirmDialog(context, title: 'Delete "${a.title}"?', message: 'It disappears for everyone. Consider archiving instead.', confirmLabel: 'Delete', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/announcements/${a.id}');
      if (mounted) setState(() => _key++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Color _prio(String p) => p == 'urgent' ? Brand.danger : (p == 'important' ? Brand.warning : Brand.muted);

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Announcements',
      subtitle: widget.isAdmin ? 'Write and manage school announcements' : 'News and notices from the school',
      actions: [if (widget.isAdmin) FilledButton.icon(onPressed: () => _form(), icon: const Icon(Icons.add), label: const Text('New announcement'))],
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (widget.isAdmin)
          FilterBar(children: [
            AppDropdown<String>(
              label: 'Show',
              value: _status,
              allowClear: true,
              hint: 'Live (published)',
              items: const [DropdownMenuItem(value: 'published', child: Text('Published')), DropdownMenuItem(value: 'draft', child: Text('Drafts')), DropdownMenuItem(value: 'archived', child: Text('Archived'))],
              onChanged: (v) => setState(() => _status = v),
            ),
          ]),
        Expanded(
          child: PagedList<_Ann>(
            path: '/announcements',
            reloadKey: _key,
            query: {'status': widget.isAdmin ? _status : null},
            parse: _Ann.new,
            emptyTitle: 'No announcements',
            emptyIcon: Icons.campaign_outlined,
            itemBuilder: (context, a, reload) => AppCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(a.title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                  if (a.priority != 'normal') Padding(padding: const EdgeInsets.only(right: 6), child: StatusChip(a.priority, color: _prio(a.priority))),
                  if (widget.isAdmin && a.status != 'published') Padding(padding: const EdgeInsets.only(right: 6), child: StatusChip(a.status, color: Brand.muted)),
                  if (widget.isAdmin)
                    PopupMenuButton<String>(
                      onSelected: (v) {
                        if (v == 'edit') _form(ann: a);
                        if (v == 'archive') _archive(a);
                        if (v == 'delete') _delete(a);
                      },
                      itemBuilder: (_) => [
                        const PopupMenuItem(value: 'edit', child: Text('Edit')),
                        if (a.status != 'archived') const PopupMenuItem(value: 'archive', child: Text('Archive')),
                        const PopupMenuItem(value: 'delete', child: Text('Delete')),
                      ],
                    ),
                ]),
                Text('${formatDateTime(a.publishAt)} · ${a.target}${a.by.isNotEmpty ? ' · ${a.by}' : ''}${a.expiresAt != null ? ' · expires ${formatDate(a.expiresAt!.toLocal())}' : ''}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                const SizedBox(height: 8),
                Text(a.body),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
