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

Color leaveColor(String status) {
  switch (status) {
    case 'approved':
      return Brand.success;
    case 'rejected':
      return Brand.danger;
    case 'pending':
      return Brand.warning;
    default:
      return Brand.muted; // cancelled
  }
}

class _Leave {
  _Leave(this.json);
  final Map<String, dynamic> json;
  String get id => asStr(json['id']);
  String get status => asStr(json['status']);
  String get studentName => asStr(json['student_name']);
  String get section => asStr(json['section_label']);
  String get type => asStr(json['leave_type']);
  String get reason => asStr(json['reason']);
  int get days => asInt(json['days']);
  DateTime get from => asDate(json['from_date']);
  DateTime get to => asDate(json['to_date']);
  String? get decisionNote => asStrN(json['decision_note']);
  String? get decidedBy => asStrN(json['decided_by_name']);
}

class _LeaveCard extends StatelessWidget {
  const _LeaveCard({required this.leave, this.actions = const <Widget>[]});
  final _Leave leave;
  final List<Widget> actions;
  final bool showStudent = true;

  @override
  Widget build(BuildContext context) {
    final l = leave;
    final same = l.from == l.to;
    return AppCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(
            child: Text(showStudent ? '${l.studentName} · ${l.section}' : (same ? formatDate(l.from) : '${formatDate(l.from)} – ${formatDate(l.to)}'),
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
          ),
          StatusChip(l.status, color: leaveColor(l.status)),
        ]),
        const SizedBox(height: 2),
        Text('${showStudent ? '${same ? formatDate(l.from) : '${formatDate(l.from)} – ${formatDate(l.to)}'} · ' : ''}${l.days} day(s) · ${humanize(l.type)}',
            style: const TextStyle(color: Brand.muted)),
        const SizedBox(height: 6),
        Text(l.reason),
        if (l.status == 'approved' || l.status == 'rejected')
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text('${humanize(l.status)}${l.decidedBy != null ? ' by ${l.decidedBy}' : ''}${(l.decisionNote ?? '').isNotEmpty ? ': ${l.decisionNote}' : ''}',
                style: const TextStyle(color: Brand.muted, fontStyle: FontStyle.italic)),
          ),
        if (actions.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Wrap(spacing: 8, children: actions)),
      ]),
    );
  }
}

// ================================================================== admin / teacher
class LeaveStaffPage extends StatefulWidget {
  const LeaveStaffPage({super.key});
  @override
  State<LeaveStaffPage> createState() => _LeaveStaffPageState();
}

class _LeaveStaffPageState extends State<LeaveStaffPage> {
  String? _status = 'pending';
  String? _sectionId;
  final int _key = 0;
  late Future<List<SectionRef>> _sections;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections();
  }

  Future<void> _approve(_Leave l, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: 'Approve leave',
      builder: (_) => QuickForm(
        intro: '${l.studentName}: ${formatDate(l.from)} – ${formatDate(l.to)} (${l.days} day(s)). The parent will be notified.',
        fields: const [QField('note', 'Note (optional)', QType.multiline)],
        submitLabel: 'Approve',
        onSubmit: (v) => api.post('/leave-requests/${l.id}/approve', body: {'note': (v['note'] as String).isEmpty ? null : v['note']}),
      ),
    );
    if (ok == true) await reload();
  }

  Future<void> _reject(_Leave l, Future<void> Function() reload) async {
    final api = context.read<ApiClient>();
    final ok = await showAppDialog<bool>(
      context,
      title: 'Reject leave',
      builder: (_) => QuickForm(
        intro: '${l.studentName}: ${formatDate(l.from)} – ${formatDate(l.to)}. Please tell the parent why.',
        fields: const [QField('note', 'Reason for rejecting', QType.multiline, required: true)],
        submitLabel: 'Reject',
        destructive: true,
        onSubmit: (v) => api.post('/leave-requests/${l.id}/reject', body: {'note': v['note']}),
      ),
    );
    if (ok == true) await reload();
  }
  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Leave requests',
      subtitle: 'Requests from parents for their children',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        FutureBuilder<List<SectionRef>>(
          future: _sections,
          builder: (context, snap) {
            final sections = snap.data ?? <SectionRef>[];
            return FilterBar(children: [
              AppDropdown<String>(
                label: 'Status',
                value: _status,
                allowClear: true,
                items: const [
                  DropdownMenuItem(value: 'pending', child: Text('Pending')),
                  DropdownMenuItem(value: 'approved', child: Text('Approved')),
                  DropdownMenuItem(value: 'rejected', child: Text('Rejected')),
                  DropdownMenuItem(value: 'cancelled', child: Text('Cancelled')),
                ],
                onChanged: (v) => setState(() => _status = v),
              ),
              AppDropdown<String>(
                label: 'Class / section',
                value: _sectionId,
                allowClear: true,
                items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(),
                onChanged: (v) => setState(() => _sectionId = v),
              ),
            ]);
          },
        ),
        Expanded(
          child: PagedList<_Leave>(
            path: '/leave-requests',
            reloadKey: _key,
            query: {'status': _status, 'section_id': _sectionId},
            parse: _Leave.new,
            emptyTitle: 'No leave requests',
            emptyMessage: _status == 'pending' ? 'Nothing is waiting for a decision.' : null,
            emptyIcon: Icons.event_available_outlined,
            itemBuilder: (context, l, reload) => _LeaveCard(
              leave: l,
              actions: l.status != 'pending'
                  ? const <Widget>[]
                  : [
                      FilledButton.icon(onPressed: () => _approve(l, reload), icon: const Icon(Icons.check, size: 18), label: const Text('Approve')),
                      OutlinedButton.icon(
                        onPressed: () => _reject(l, reload),
                        icon: const Icon(Icons.close, size: 18),
                        label: const Text('Reject'),
                        style: OutlinedButton.styleFrom(foregroundColor: Brand.danger),
                      ),
                    ],
            ),
          ),
        ),
      ]),
    );
  }
}

// ================================================================== parent
class LeaveParentPage extends StatefulWidget {
  const LeaveParentPage({super.key});
  @override
  State<LeaveParentPage> createState() => _LeaveParentPageState();
}

class _LeaveParentPageState extends State<LeaveParentPage> {
  int _key = 0;

  Future<void> _apply() async {
    final api = context.read<ApiClient>();
    final List<ChildRef> children;
    try {
      children = await context.read<Lookups>().myChildren();
    } catch (e) {
      if (mounted) showError(context, e);
      return;
    }
    if (!mounted) return;
    if (children.isEmpty) {
      showSnack(context, 'No child is linked to your account. Please contact the school office.', error: true);
      return;
    }
    final today = dateOnly(DateTime.now());
    final ok = await showAppDialog<bool>(
      context,
      title: 'Apply for leave',
      builder: (_) => QuickForm(
        fields: [
          QField('student_id', 'Child', QType.dropdown, required: true, initial: children.length == 1 ? children.first.studentId : null, options: children.map((c) => MapEntry(c.studentId, '${c.fullName} · ${c.sectionLabel ?? ''}')).toList()),
          QField('leave_type', 'Type', QType.dropdown, required: true, initial: 'sick', options: const [MapEntry('sick', 'Sick'), MapEntry('family', 'Family'), MapEntry('other', 'Other')]),
          QField('from_date', 'From', QType.date, required: true, initial: today),
          QField('to_date', 'To', QType.date, required: true, initial: today),
          const QField('reason', 'Reason', QType.multiline, required: true, helper: 'At least 5 characters'),
        ],
        submitLabel: 'Submit request',
        onSubmit: (v) {
          final from = v['from_date'] as DateTime;
          final to = v['to_date'] as DateTime;
          if (to.isBefore(from)) {
            throw ApiException(422, 'validation_error', 'Please correct the highlighted field', fieldErrors: const [FieldError('to_date', 'The end date cannot be before the start date')]);
          }
          return api.post('/leave-requests', body: {
            'student_id': v['student_id'],
            'leave_type': v['leave_type'],
            'from_date': isoDate(from),
            'to_date': isoDate(to),
            'reason': v['reason'],
          });
        },
      ),
    );
    if (ok == true && mounted) {
      showSnack(context, 'Leave request sent');
      setState(() => _key++);
    }
  }

  Future<void> _cancel(_Leave l, Future<void> Function() reload) async {
    final ok = await confirmDialog(context, title: 'Cancel this request?', message: 'The leave request for ${formatDate(l.from)} will be cancelled.', confirmLabel: 'Cancel request', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().post('/leave-requests/${l.id}/cancel');
      await reload();
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Leave',
      subtitle: 'Apply for your child\'s leave and track the decision',
      actions: [FilledButton.icon(onPressed: _apply, icon: const Icon(Icons.add), label: const Text('Apply for leave'))],
      child: PagedList<_Leave>(
        path: '/leave-requests',
        reloadKey: _key,
        parse: _Leave.new,
        emptyTitle: 'No leave requests yet',
        emptyMessage: 'Tap "Apply for leave" when your child will be absent.',
        emptyIcon: Icons.event_available_outlined,
        itemBuilder: (context, l, reload) => _LeaveCard(
          leave: l,
          actions: l.status == 'pending'
              ? [TextButton.icon(onPressed: () => _cancel(l, reload), icon: const Icon(Icons.close, size: 18), label: const Text('Cancel request'), style: TextButton.styleFrom(foregroundColor: Brand.danger))]
              : const <Widget>[],
        ),
      ),
    );
  }
}
