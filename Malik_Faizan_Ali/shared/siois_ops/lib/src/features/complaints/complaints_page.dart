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

const List<MapEntry<String, String>> _kCategories = <MapEntry<String, String>>[
  MapEntry('academic', 'Academic'),
  MapEntry('fee', 'Fees'),
  MapEntry('teacher', 'Teacher'),
  MapEntry('facility', 'Facilities'),
  MapEntry('transport', 'Transport'),
  MapEntry('other', 'Other'),
];
const List<MapEntry<String, String>> _kKinds = <MapEntry<String, String>>[
  MapEntry('complaint', 'Complaint'),
  MapEntry('feedback', 'Feedback'),
  MapEntry('suggestion', 'Suggestion'),
];
const List<MapEntry<String, String>> _kStatuses = <MapEntry<String, String>>[
  MapEntry('open', 'Open'),
  MapEntry('in_review', 'In review'),
  MapEntry('resolved', 'Resolved'),
  MapEntry('closed', 'Closed'),
];
const List<MapEntry<String, String>> _kPriorities = <MapEntry<String, String>>[
  MapEntry('low', 'Low'),
  MapEntry('normal', 'Normal'),
  MapEntry('high', 'High'),
];

class _Ticket {
  _Ticket(this.json);
  final Map<String, dynamic> json;
  String get id => asStr(json['id']);
  String get ticketNo => asStr(json['ticket_no']);
  String get subject => asStr(json['subject']);
  String get description => asStr(json['description']);
  String get status => asStr(json['status'], 'open');
  String get priority => asStr(json['priority'], 'normal');
  String get category => asStr(json['category']);
  String get kind => asStr(json['kind']);
  String get by => asStr(json['submitted_by_name']);
  String? get studentName => asStrN(json['student_name']);
  String? get studentSection => asStrN(json['student_section']);
  String? get assignedTo => asStrN(json['assigned_to']);
  String? get assignedName => asStrN(json['assigned_to_name']);
  int get comments => asInt(json['comment_count']);
  DateTime? get createdAt => asDateN(json['created_at']);
}

Color _statusColor(String s) {
  switch (s) {
    case 'open':
      return Brand.warning;
    case 'in_review':
      return Brand.info;
    case 'resolved':
      return Brand.success;
    default:
      return Brand.muted;
  }
}

/// Parent: file and follow own tickets. Admin: triage, assign, answer and close them.
class ComplaintsPage extends StatefulWidget {
  const ComplaintsPage({super.key, required this.isAdmin});
  final bool isAdmin;
  @override
  State<ComplaintsPage> createState() => _ComplaintsPageState();
}

class _ComplaintsPageState extends State<ComplaintsPage> {
  String? _status;
  String? _category;
  String? _kind;
  int _key = 0;

  Future<void> _create() async {
    final api = context.read<ApiClient>();
    final List<ChildRef> children;
    try {
      children = await context.read<Lookups>().myChildren();
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    final ok = await showAppDialog<bool>(
      context,
      title: 'New complaint or feedback',
      width: 600,
      builder: (_) => QuickForm(
        fields: [
          QField('kind', 'Type', QType.dropdown, required: true, initial: 'complaint', options: _kKinds),
          QField('category', 'Category', QType.dropdown, required: true, options: _kCategories),
          QField('student_id', 'About which child (optional)', QType.dropdown, clearable: true, options: children.map((c) => MapEntry(c.studentId, '${c.fullName} · ${c.sectionLabel ?? ''}')).toList()),
          const QField('subject', 'Subject', QType.text, required: true),
          const QField('description', 'Details', QType.multiline, required: true, helper: 'At least 10 characters'),
        ],
        submitLabel: 'Submit',
        onSubmit: (v) => api.post('/complaints', body: {
          'kind': v['kind'],
          'category': v['category'],
          'student_id': v['student_id'],
          'subject': v['subject'],
          'description': v['description'],
        }),
      ),
    );
    if (ok == true && mounted) {
      showSnack(context, 'Submitted. The school will reply here.');
      setState(() => _key++);
    }
  }

  Future<void> _open(_Ticket t) async {
    await showAppDialog<void>(context, title: 'Ticket ${t.ticketNo}', width: 700, builder: (_) => _TicketDetail(id: t.id, isAdmin: widget.isAdmin));
    if (mounted) setState(() => _key++);
  }

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return PageFrame(
      title: 'Complaints & feedback',
      subtitle: widget.isAdmin ? 'Tickets from parents' : 'Tell the school about a problem or an idea, and follow the reply',
      actions: [if (!widget.isAdmin) FilledButton.icon(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New'))],
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (widget.isAdmin)
          AsyncView<Map<String, dynamic>>(
            loadKey: _key,
            loader: () async => asMap(await api.get('/complaints/summary')),
            builder: (context, s, reload) {
              final by = asMap(s['by_status']);
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Wrap(spacing: 8, runSpacing: 6, children: [
                  Chip(label: Text('Total: ${asInt(s['total'])}')),
                  for (final e in _kStatuses) Chip(label: Text('${e.value}: ${asInt(by[e.key])}')),
                  Chip(avatar: const Icon(Icons.person_off_outlined, size: 16), label: Text('Unassigned open: ${asInt(s['unassigned_open'])}')),
                ]),
              );
            },
          ),
        FilterBar(children: [
          AppDropdown<String>(label: 'Status', value: _status, allowClear: true, items: _kStatuses.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(), onChanged: (v) => setState(() => _status = v)),
          AppDropdown<String>(label: 'Category', value: _category, allowClear: true, items: _kCategories.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(), onChanged: (v) => setState(() => _category = v)),
          AppDropdown<String>(label: 'Type', value: _kind, allowClear: true, items: _kKinds.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(), onChanged: (v) => setState(() => _kind = v)),
        ]),
        Expanded(
          child: PagedList<_Ticket>(
            path: '/complaints',
            reloadKey: _key,
            query: {'status': _status, 'category': _category, 'kind': _kind},
            parse: _Ticket.new,
            emptyTitle: 'No tickets',
            emptyMessage: widget.isAdmin ? null : 'Use "New" to send a complaint, feedback or suggestion.',
            emptyIcon: Icons.support_agent_outlined,
            itemBuilder: (context, t, reload) => AppCard(
              onTap: () => _open(t),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(t.subject, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16))),
                  StatusChip(t.status, color: _statusColor(t.status)),
                ]),
                Text(
                  [
                    t.ticketNo,
                    humanize(t.kind),
                    humanize(t.category),
                    if (widget.isAdmin && t.by.isNotEmpty) t.by,
                    if (t.studentName != null) '${t.studentName}${t.studentSection != null ? ' (${t.studentSection})' : ''}',
                    formatDate(t.createdAt),
                  ].join(' · '),
                  style: const TextStyle(color: Brand.muted, fontSize: 12.5),
                ),
                const SizedBox(height: 6),
                Text(t.description, maxLines: 2, overflow: TextOverflow.ellipsis),
                if (t.comments > 0 || (widget.isAdmin && t.assignedName != null))
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('${t.comments} repl${t.comments == 1 ? 'y' : 'ies'}${widget.isAdmin && t.assignedName != null ? ' · assigned to ${t.assignedName}' : ''}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                  ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

class _TicketDetail extends StatefulWidget {
  const _TicketDetail({required this.id, required this.isAdmin});
  final String id;
  final bool isAdmin;
  @override
  State<_TicketDetail> createState() => _TicketDetailState();
}

class _TicketDetailState extends State<_TicketDetail> with BusyMixin {
  late Future<Map<String, dynamic>> _future;
  late final Future<List<AdminRef>> _admins;
  final _reply = TextEditingController();
  bool _internal = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
    _admins = widget.isAdmin ? context.read<Lookups>().admins() : Future<List<AdminRef>>.value(<AdminRef>[]);
  }

  @override
  void dispose() {
    _reply.dispose();
    super.dispose();
  }

  Future<Map<String, dynamic>> _load() async => asMap(await context.read<ApiClient>().get('/complaints/${widget.id}'));

  void _refresh() => setState(() { _future = _load(); });

  Future<void> _patch(Map<String, dynamic> body) async {
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.patch('/complaints/${widget.id}', body: body);
    });
    if (ok && mounted) _refresh();
  }

  Future<void> _send() async {
    final text = _reply.text.trim();
    if (text.isEmpty) return;
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/complaints/${widget.id}/comments', body: {'message': text, 'is_internal': widget.isAdmin && _internal});
    });
    if (ok && mounted) {
      _reply.clear();
      _refresh();
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const SizedBox(height: 160, child: LoadingView());
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _refresh);
        final t = _Ticket(snap.data!);
        final comments = asMapList(snap.data!['comments']);
        final closed = t.status == 'closed';
        return Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
          Row(children: [
            Expanded(child: Text(t.subject, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 17))),
            StatusChip(t.status, color: _statusColor(t.status)),
          ]),
          const SizedBox(height: 4),
          Text(
            [humanize(t.kind), humanize(t.category), if (widget.isAdmin && t.by.isNotEmpty) 'from ${t.by}', if (t.studentName != null) 'about ${t.studentName}', formatDateTime(t.createdAt)].join(' · '),
            style: const TextStyle(color: Brand.muted, fontSize: 12.5),
          ),
          const SizedBox(height: 10),
          Text(t.description),
          if (widget.isAdmin) ...[
            const Divider(height: 24),
            FutureBuilder<List<AdminRef>>(
              future: _admins,
              builder: (context, adm) => Wrap(spacing: 12, runSpacing: 12, children: [
                SizedBox(width: 180, child: AppDropdown<String>(label: 'Status', value: t.status, items: _kStatuses.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(), onChanged: busy ? null : (v) => v == null || v == t.status ? null : _patch({'status': v}))),
                SizedBox(width: 160, child: AppDropdown<String>(label: 'Priority', value: t.priority, items: _kPriorities.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(), onChanged: busy ? null : (v) => v == null || v == t.priority ? null : _patch({'priority': v}))),
                SizedBox(
                  width: 220,
                  child: AppDropdown<String>(
                    label: 'Assigned to',
                    value: t.assignedTo,
                    allowClear: true,
                    hint: 'Unassigned',
                    items: (adm.data ?? <AdminRef>[]).map((a) => DropdownMenuItem(value: a.id, child: Text(a.fullName))).toList(),
                    onChanged: busy ? null : (v) => v == t.assignedTo ? null : _patch({'assigned_to': v}),
                  ),
                ),
              ]),
            ),
          ],
          const Divider(height: 24),
          Text('Conversation', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          if (comments.isEmpty) const Text('No replies yet.', style: TextStyle(color: Brand.muted)),
          for (final c in comments)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: asBool(c['is_internal']) ? Brand.warning.withValues(alpha: 0.1) : (asStr(c['author_role']) == 'admin' ? Brand.primary.withValues(alpha: 0.08) : Brand.surfaceTint),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text('${asStr(c['author_name'])}${asStr(c['author_role']).isEmpty ? '' : ' (${humanize(asStr(c['author_role']))})'}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5))),
                  if (asBool(c['is_internal'])) const StatusChip('internal note', color: Brand.warning),
                ]),
                Text(asStr(c['message'])),
                Text(formatDateTime(asDateN(c['created_at'])), style: const TextStyle(color: Brand.muted, fontSize: 11.5)),
              ]),
            ),
          if (closed)
            const Padding(padding: EdgeInsets.only(top: 4), child: Text('This ticket is closed.', style: TextStyle(color: Brand.muted)))
          else ...[
            TextField(controller: _reply, minLines: 2, maxLines: 4, maxLength: 2000, decoration: const InputDecoration(labelText: 'Write a reply')),
            Row(children: [
              if (widget.isAdmin) ...[Switch(value: _internal, onChanged: (v) => setState(() => _internal = v)), const Expanded(child: Text('Internal note (parent cannot see it)'))] else const Spacer(),
              FilledButton.icon(onPressed: busy ? null : _send, icon: const Icon(Icons.send, size: 18), label: const Text('Send')),
            ]),
          ],
        ]);
      },
    );
  }
}
