import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

const List<MapEntry<String, String>> _categories = <MapEntry<String, String>>[
  MapEntry('academic', 'Academic'),
  MapEntry('fee', 'Fees'),
  MapEntry('teacher', 'Teacher'),
  MapEntry('facility', 'Facilities'),
  MapEntry('transport', 'Transport'),
  MapEntry('other', 'Other'),
];

/// Complaints and feedback. Parents submit and follow their own tickets; the admin manages all of them.
class ComplaintsScreen extends StatefulWidget {
  const ComplaintsScreen({super.key, required this.isAdmin});

  final bool isAdmin;

  @override
  State<ComplaintsScreen> createState() => _ComplaintsScreenState();
}

class _ComplaintsScreenState extends State<ComplaintsScreen> {
  late Future<Paged<Complaint>> _future;
  Future<Map<String, dynamic>>? _summary;
  String? _status;

  @override
  void initState() {
    super.initState();
    _future = _load();
    if (widget.isAdmin) _summary = context.read<OpsApi>().complaintSummary();
  }

  Future<Paged<Complaint>> _load() => context.read<OpsApi>().complaints(status: _status);

  void _reload() {
    setState(() {
      _future = _load();
      if (widget.isAdmin) _summary = context.read<OpsApi>().complaintSummary();
    });
  }

  Future<void> _create() async {
    final api = context.read<OpsApi>();
    List<StudentItem> children;
    try {
      children = await api.myChildren();
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.message, error: true);
      return;
    }
    if (!mounted) return;
    var kind = 'complaint';
    var category = 'academic';
    var subject = '';
    var description = '';
    String? studentId;
    final saved = await showFormDialog(
      context,
      title: 'New ticket',
      submitLabel: 'Submit',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          pickString('Type', kind, const [
            MapEntry('complaint', 'Complaint'),
            MapEntry('feedback', 'Feedback'),
            MapEntry('suggestion', 'Suggestion'),
          ], (v) => set(() => kind = v ?? kind)),
          pickString('Category', category, _categories, (v) => set(() => category = v ?? category)),
          if (children.isNotEmpty)
            pickString('About which child? (optional)', studentId,
                [for (final c in children) MapEntry(c.id, '${c.fullName} (${c.sectionName})')], (v) => set(() => studentId = v)),
          formText('Subject', subject, (v) => subject = v),
          formText('Describe the issue', description, (v) => description = v, maxLines: 5),
        ]),
      ),
      validate: () =>
          Validators.minLength(subject, 3, 'Subject') ??
          Validators.maxLength(subject, 200, 'Subject') ??
          Validators.minLength(description, 10, 'Description'),
      onSubmit: () => api.createComplaint(<String, dynamic>{
        'kind': kind,
        'category': category,
        if (studentId != null) 'student_id': studentId,
        'subject': subject.trim(),
        'description': description.trim(),
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, 'Your ticket was submitted');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.isAdmin ? 'Complaints & feedback' : 'My tickets'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      floatingActionButton: widget.isAdmin
          ? null
          : FloatingActionButton.extended(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New ticket')),
      body: ContentWidth(
        child: Column(
          children: [
            if (widget.isAdmin && _summary != null)
              FutureBuilder<Map<String, dynamic>>(
                future: _summary,
                builder: (ctx, snap) {
                  if (!snap.hasData) return const SizedBox.shrink();
                  final byStatus = jMap(snap.data!['by_status']);
                  return Padding(
                    padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                    child: Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        SizedBox(width: 130, child: StatCard(label: 'Total', value: '${jInt(snap.data!['total'])}')),
                        SizedBox(width: 130, child: StatCard(label: 'Open', value: '${jInt(byStatus['open'])}', color: Colors.blue.shade700)),
                        SizedBox(width: 130, child: StatCard(label: 'In review', value: '${jInt(byStatus['in_review'])}', color: Colors.orange.shade800)),
                        SizedBox(width: 130, child: StatCard(label: 'Resolved', value: '${jInt(byStatus['resolved'])}', color: Colors.green.shade700)),
                      ],
                    ),
                  );
                },
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
              child: Wrap(
                spacing: 8,
                children: [
                  for (final s in const <String?>[null, 'open', 'in_review', 'resolved', 'closed'])
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
              child: FutureView<Paged<Complaint>>(
                future: _future,
                onRetry: _reload,
                builder: (ctx, page) {
                  if (page.items.isEmpty) return const EmptyView('No tickets', icon: Icons.support_agent_outlined);
                  return ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 8, 12, 88),
                    itemCount: page.items.length,
                    itemBuilder: (ctx, i) {
                      final c = page.items[i];
                      return Card(
                        child: ListTile(
                          onTap: () async {
                            await Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) => ComplaintDetailScreen(complaintId: c.id, isAdmin: widget.isAdmin),
                            ));
                            if (mounted) _reload();
                          },
                          title: Text(c.subject, style: const TextStyle(fontWeight: FontWeight.w600)),
                          subtitle: Text([
                            '${c.ticketNo}  -  ${titleCase(c.kind)}  -  ${titleCase(c.category)}',
                            if (widget.isAdmin) 'From ${c.submitterName}${c.studentName.isNotEmpty ? ' (about ${c.studentName})' : ''}',
                            fmtDateTime(c.createdAt),
                          ].join('\n')),
                          isThreeLine: true,
                          trailing: StatusChip(c.status),
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

class ComplaintDetailScreen extends StatefulWidget {
  const ComplaintDetailScreen({super.key, required this.complaintId, required this.isAdmin});

  final String complaintId;
  final bool isAdmin;

  @override
  State<ComplaintDetailScreen> createState() => _ComplaintDetailScreenState();
}

class _ComplaintDetailScreenState extends State<ComplaintDetailScreen> {
  late Future<Complaint> _future;
  var _message = '';
  var _internal = false;
  final TextEditingController _messageController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().complaint(widget.complaintId);
  }

  @override
  void dispose() {
    _messageController.dispose();
    super.dispose();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().complaint(widget.complaintId));

  Future<void> _update(Map<String, dynamic> changes, String done) async {
    final ok = await runAction(context, () => context.read<OpsApi>().updateComplaint(widget.complaintId, changes), success: done);
    if (ok && mounted) _reload();
  }

  Future<void> _send() async {
    final problem = Validators.required(_message, 'Message');
    if (problem != null) {
      showMessage(context, problem, error: true);
      return;
    }
    final ok = await runAction(
      context,
      () => context.read<OpsApi>().addComment(widget.complaintId, _message.trim(), internal: widget.isAdmin && _internal),
      success: 'Reply sent',
    );
    if (ok && mounted) {
      _messageController.clear();
      _message = '';
      _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final myId = context.read<AuthState>().user?.id;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ticket'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      body: ContentWidth(
        maxWidth: 800,
        child: FutureView<Complaint>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, c) => ListView(
            padding: const EdgeInsets.all(12),
            children: [
              Row(
                children: [
                  Expanded(child: Text(c.subject, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700))),
                  StatusChip(c.status),
                ],
              ),
              const SizedBox(height: 8),
              InfoRow('Ticket', c.ticketNo),
              InfoRow('Type', '${titleCase(c.kind)} - ${titleCase(c.category)}'),
              if (widget.isAdmin) InfoRow('From', c.submitterName),
              if (c.studentName.isNotEmpty) InfoRow('About', c.studentName),
              InfoRow('Priority', titleCase(c.priority)),
              InfoRow('Opened', fmtDateTime(c.createdAt)),
              const SizedBox(height: 8),
              Text(c.description),
              if (widget.isAdmin) ...[
                const Divider(height: 32),
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    SizedBox(
                      width: 200,
                      child: pickString('Status', c.status, const [
                        MapEntry('open', 'Open'),
                        MapEntry('in_review', 'In review'),
                        MapEntry('resolved', 'Resolved'),
                        MapEntry('closed', 'Closed'),
                      ], (v) {
                        if (v != null && v != c.status) _update(<String, dynamic>{'status': v}, 'Status updated');
                      }),
                    ),
                    SizedBox(
                      width: 200,
                      child: pickString('Priority', c.priority, const [
                        MapEntry('low', 'Low'),
                        MapEntry('normal', 'Normal'),
                        MapEntry('high', 'High'),
                      ], (v) {
                        if (v != null && v != c.priority) _update(<String, dynamic>{'priority': v}, 'Priority updated');
                      }),
                    ),
                    if (myId != null && c.assignedTo != myId)
                      OutlinedButton.icon(
                        onPressed: () => _update(<String, dynamic>{'assigned_to': myId}, 'Assigned to you'),
                        icon: const Icon(Icons.person_add_alt),
                        label: const Text('Assign to me'),
                      )
                    else if (c.assignedTo != null)
                      const Text('Assigned to you'),
                  ],
                ),
              ],
              const Divider(height: 32),
              Text('Conversation', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              if (c.comments.isEmpty) const Text('No replies yet.'),
              for (final m in c.comments)
                Card(
                  color: m.isInternal ? Colors.amber.withAlpha(40) : null,
                  child: ListTile(
                    title: Text('${m.authorName}  (${m.authorRole})${m.isInternal ? '  - internal note' : ''}',
                        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                    subtitle: Text('${m.message}\n${fmtDateTime(m.createdAt)}'),
                    isThreeLine: true,
                  ),
                ),
              const SizedBox(height: 12),
              if (c.status == 'closed' && !widget.isAdmin)
                const Text('This ticket is closed.')
              else ...[
                TextField(
                  controller: _messageController,
                  onChanged: (v) => _message = v,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Write a reply', border: OutlineInputBorder()),
                ),
                if (widget.isAdmin)
                  StatefulBuilder(
                    builder: (ctx, set) => SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Internal note (hidden from the parent)'),
                      value: _internal,
                      onChanged: (v) => set(() => _internal = v),
                    ),
                  ),
                Align(
                  alignment: Alignment.centerRight,
                  child: FilledButton.icon(onPressed: _send, icon: const Icon(Icons.send), label: const Text('Send')),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
