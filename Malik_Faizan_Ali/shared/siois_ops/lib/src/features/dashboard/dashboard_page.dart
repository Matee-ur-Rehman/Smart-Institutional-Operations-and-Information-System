import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/auth.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../timetable/timetable_models.dart';
import 'role_scope.dart';

/// Runs one dashboard query; a failed card must not break the whole dashboard, so errors become null.
Future<T?> _safe<T>(Future<T> Function() f) async {
  try {
    return await f();
  } catch (_) {
    return null;
  }
}

int _total(dynamic page) => asInt(asMap(page)['total']);
List<Map<String, dynamic>> _items(dynamic page) => asMapList(asMap(page)['items']);

/// Role-specific landing page. Every card loads independently.
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key, required this.role});
  final Role role;

  @override
  Widget build(BuildContext context) {
    final name = context.watch<AuthController>().user?.fullName ?? '';
    final first = name.trim().isEmpty ? '' : ', ${name.trim().split(RegExp(r'\s+')).first}';
    final subtitle = formatDate(DateTime.now());
    switch (role) {
      case Role.admin:
        return PageFrame(title: 'Welcome$first', subtitle: subtitle, child: const _AdminDash());
      case Role.teacher:
        return PageFrame(title: 'Welcome$first', subtitle: subtitle, child: const _TeacherDash());
      case Role.student:
        return PageFrame(title: 'Welcome$first', subtitle: subtitle, child: StudentScope(builder: (context, c) => _StudentDash(child: c, isParent: false)));
      case Role.parent:
        return PageFrame(title: 'Welcome$first', subtitle: subtitle, child: StudentScope(builder: (context, c) => _StudentDash(child: c, isParent: true)));
    }
  }
}

// ------------------------------------------------------------------ shared pieces
Widget _kpiWrap(BuildContext context, List<Widget> cards) {
  final cols = isWide(context) ? 4 : (isMedium(context) ? 3 : 2);
  final w = (MediaQuery.sizeOf(context).width - (isWide(context) ? 300 : 32) - 12 * (cols - 1)) / cols;
  final width = w.clamp(150.0, 260.0).toDouble();
  return Wrap(spacing: 12, runSpacing: 12, children: [for (final c in cards) SizedBox(width: width, child: c)]);
}

class _Block extends StatelessWidget {
  const _Block({required this.title, required this.child});
  final String title;
  final Widget child;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 16),
        child: AppCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
            const SizedBox(height: 8),
            child,
          ]),
        ),
      );
}

Widget _muted(String text) => Text(text, style: const TextStyle(color: Brand.muted));

/// Three latest announcements + next events, shown on every dashboard.
class _NewsBlocks extends StatelessWidget {
  const _NewsBlocks();
  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    final today = isoDate(DateTime.now());
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _Block(
        title: 'Latest announcements',
        child: AsyncView<List<Map<String, dynamic>>>(
          loader: () async => _items(await api.get('/announcements', query: {'page_size': 3})),
          builder: (context, rows, reload) => rows.isEmpty
              ? _muted('No announcements.')
              : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  for (final a in rows)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text(asStr(a['title']), style: const TextStyle(fontWeight: FontWeight.w600)),
                        Text(asStr(a['body']), maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Brand.muted)),
                      ]),
                    ),
                ]),
        ),
      ),
      _Block(
        title: 'Coming up',
        child: AsyncView<List<Map<String, dynamic>>>(
          loader: () async => _items(await api.get('/events', query: {'from_date': today, 'page_size': 4})),
          builder: (context, rows, reload) => rows.isEmpty
              ? _muted('No upcoming events.')
              : Column(children: [
                  for (final e in rows)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(Icons.event_outlined, color: Brand.primary.withValues(alpha: 0.9)),
                      title: Text(asStr(e['title'])),
                      subtitle: Text('${formatDate(asDateN(e['start_date']))} · ${humanize(asStr(e['event_type']))}'),
                    ),
                ]),
        ),
      ),
    ]);
  }
}

/// Today's lessons from a `/timetable/...` payload (no lessons on Sunday).
class _TodayLessons extends StatelessWidget {
  const _TodayLessons({required this.data, required this.showTeacher});
  final TimetableData data;
  final bool showTeacher;
  @override
  Widget build(BuildContext context) {
    final day = DateTime.now().weekday;
    if (day > 6) return _muted('Sunday — no lessons today.');
    final byPeriod = {for (final p in data.periods) p.id: p};
    final slots = data.slots.where((s) => s.day == day).toList()
      ..sort((a, b) => (byPeriod[a.periodId]?.periodNo ?? 0).compareTo(byPeriod[b.periodId]?.periodNo ?? 0));
    if (slots.isEmpty) return _muted('No lessons scheduled today.');
    return Column(children: [
      for (final s in slots)
        ListTile(
          dense: true,
          contentPadding: EdgeInsets.zero,
          leading: CircleAvatar(radius: 14, backgroundColor: Brand.primary, child: Text('${byPeriod[s.periodId]?.periodNo ?? ''}', style: const TextStyle(color: Colors.white, fontSize: 12))),
          title: Text(s.subjectName),
          subtitle: Text('${formatTimeRange(byPeriod[s.periodId]?.start, byPeriod[s.periodId]?.end)} · ${showTeacher ? s.teacherName : s.sectionLabel}'),
        ),
    ]);
  }
}

// ------------------------------------------------------------------ admin
class _AdminDash extends StatelessWidget {
  const _AdminDash();
  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<Map<String, dynamic>>(
      loader: () async {
        final r = await Future.wait<dynamic>([
          _safe(() => api.get('/students', query: {'page_size': 1})),
          _safe(() => api.get('/teachers', query: {'page_size': 1})),
          _safe(() => api.get('/fee-summary')),
          _safe(() => api.get('/attendance/overview')),
          _safe(() => api.get('/leave-requests', query: {'status': 'pending', 'page_size': 1})),
          _safe(() => api.get('/complaints/summary')),
        ]);
        return {'students': r[0], 'teachers': r[1], 'fees': r[2], 'attendance': r[3], 'leave': r[4], 'complaints': r[5]};
      },
      builder: (context, d, reload) {
        final fees = asMap(d['fees']);
        final att = asMap(d['attendance']);
        final cmp = asMap(d['complaints']);
        final by = asMap(cmp['by_status']);
        String n(dynamic v) => v == null ? '—' : '$v';
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(children: [
            _kpiWrap(context, [
              KpiCard(label: 'Students', value: d['students'] == null ? '—' : '${_total(d['students'])}', icon: Icons.school_outlined),
              KpiCard(label: 'Teachers', value: d['teachers'] == null ? '—' : '${_total(d['teachers'])}', icon: Icons.badge_outlined, color: Brand.info),
              KpiCard(label: 'Sections not marked today', value: att.isEmpty ? '—' : n(att['unmarked_sections']), icon: Icons.fact_check_outlined, color: asInt(att['unmarked_sections']) > 0 ? Brand.warning : Brand.success),
              KpiCard(label: 'Pending leave requests', value: d['leave'] == null ? '—' : '${_total(d['leave'])}', icon: Icons.event_available_outlined, color: Brand.warning),
              KpiCard(label: 'Fees collected', value: fees.isEmpty ? '—' : formatMoney(asDouble(fees['collected'])), icon: Icons.account_balance_wallet_outlined, color: Brand.success),
              KpiCard(label: 'Fees outstanding', value: fees.isEmpty ? '—' : formatMoney(asDouble(fees['outstanding'])), icon: Icons.hourglass_bottom, color: Brand.warning),
              KpiCard(label: 'Overdue fees', value: fees.isEmpty ? '—' : formatMoney(asDouble(fees['overdue'])), icon: Icons.warning_amber, color: Brand.danger),
              KpiCard(label: 'Open complaints', value: cmp.isEmpty ? '—' : '${asInt(by['open']) + asInt(by['in_review'])}', icon: Icons.support_agent_outlined, color: Brand.danger),
            ]),
            if (asInt(att['unmarked_sections']) > 0)
              _Block(
                title: 'Attendance not yet marked today',
                child: Wrap(spacing: 8, runSpacing: 6, children: [
                  for (final s in asMapList(att['sections']).where((s) => !asBool(s['is_marked']) && asInt(s['students']) > 0)) Chip(label: Text(asStr(s['section_label']))),
                ]),
              ),
            const _NewsBlocks(),
          ]),
        );
      },
    );
  }
}

// ------------------------------------------------------------------ teacher
class _TeacherDash extends StatelessWidget {
  const _TeacherDash();
  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return AsyncView<Map<String, dynamic>>(
      loader: () async {
        final r = await Future.wait<dynamic>([
          _safe(() => api.get('/attendance/overview')),
          _safe(() => api.get('/timetable/me')),
          _safe(() => api.get('/leave-requests', query: {'status': 'pending', 'page_size': 1})),
          _safe(() => api.get('/notifications/unread-count')),
        ]);
        return {'attendance': r[0], 'timetable': r[1], 'leave': r[2], 'unread': r[3]};
      },
      builder: (context, d, reload) {
        final att = asMap(d['attendance']);
        final sections = asMapList(att['sections']);
        final tt = d['timetable'] == null ? null : TimetableData.fromJson(d['timetable']);
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(children: [
            _kpiWrap(context, [
              KpiCard(label: 'My classes not marked today', value: att.isEmpty ? '—' : '${asInt(att['unmarked_sections'])}', icon: Icons.fact_check_outlined, color: asInt(att['unmarked_sections']) > 0 ? Brand.warning : Brand.success),
              KpiCard(label: 'Pending leave requests', value: d['leave'] == null ? '—' : '${_total(d['leave'])}', icon: Icons.event_available_outlined, color: Brand.warning),
              KpiCard(label: 'Unread notifications', value: d['unread'] == null ? '—' : '${asInt(asMap(d['unread'])['count'])}', icon: Icons.notifications_outlined, color: Brand.info),
            ]),
            _Block(title: 'Today\'s lessons', child: tt == null ? _muted('Timetable unavailable.') : _TodayLessons(data: tt, showTeacher: false)),
            if (sections.isNotEmpty)
              _Block(
                title: 'Attendance today',
                child: Column(children: [
                  for (final s in sections)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(asStr(s['section_label'])),
                      trailing: asBool(s['is_marked']) ? StatusChip('P ${asStr(s['present'])} · A ${asStr(s['absent'])}', color: Brand.success) : const StatusChip('not marked', color: Brand.warning),
                    ),
                ]),
              ),
            const _NewsBlocks(),
          ]),
        );
      },
    );
  }
}

// ------------------------------------------------------------------ student / parent
class _StudentDash extends StatelessWidget {
  const _StudentDash({required this.child, required this.isParent});
  final ChildRef child;
  final bool isParent;
  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    final today = isoDate(DateTime.now());
    final sid = child.studentId;
    return AsyncView<Map<String, dynamic>>(
      loader: () async {
        final r = await Future.wait<dynamic>([
          _safe(() => api.get('/attendance/students/$sid')),
          _safe(() => api.get(isParent ? '/timetable/students/$sid' : '/timetable/me')),
          _safe(() => api.get('/assignments', query: {'student_id': sid, 'status': 'published', 'due_from': today, 'sort': 'due_asc', 'page_size': 4})),
          isParent ? _safe(() => api.get('/students/$sid/fee-statement')) : Future<dynamic>.value(null),
          isParent ? _safe(() => api.get('/leave-requests', query: {'status': 'pending', 'student_id': sid, 'page_size': 1})) : Future<dynamic>.value(null),
          _safe(() => api.get('/notifications/unread-count')),
        ]);
        return {'attendance': r[0], 'timetable': r[1], 'homework': r[2], 'fees': r[3], 'leave': r[4], 'unread': r[5]};
      },
      builder: (context, d, reload) {
        final sm = asMap(asMap(d['attendance'])['summary']);
        final pct = sm['percentage'] == null ? null : asDouble(sm['percentage']);
        final tt = d['timetable'] == null ? null : TimetableData.fromJson(d['timetable']);
        final hw = _items(d['homework']);
        final totals = asMap(asMap(d['fees'])['totals']);
        return RefreshIndicator(
          onRefresh: reload,
          child: ListView(children: [
            _kpiWrap(context, [
              KpiCard(label: 'Attendance', value: d['attendance'] == null ? '—' : formatPercent(pct), icon: Icons.fact_check_outlined, color: pct != null && pct < 75 ? Brand.danger : Brand.success),
              KpiCard(label: 'Homework due soon', value: d['homework'] == null ? '—' : '${_total(d['homework'])}', icon: Icons.menu_book_outlined, color: Brand.warning),
              if (isParent) KpiCard(label: 'Fee balance due', value: totals.isEmpty ? '—' : formatMoney(asDouble(totals['balance'])), icon: Icons.payments_outlined, color: asDouble(totals['balance']) > 0 ? Brand.warning : Brand.success),
              if (isParent) KpiCard(label: 'Pending leave', value: d['leave'] == null ? '—' : '${_total(d['leave'])}', icon: Icons.event_available_outlined, color: Brand.info),
              KpiCard(label: 'Unread notifications', value: d['unread'] == null ? '—' : '${asInt(asMap(d['unread'])['count'])}', icon: Icons.notifications_outlined, color: Brand.info),
            ]),
            _Block(title: 'Today\'s timetable', child: tt == null ? _muted('Timetable unavailable.') : _TodayLessons(data: tt, showTeacher: true)),
            _Block(
              title: 'Homework due soon',
              child: hw.isEmpty
                  ? _muted('No homework due.')
                  : Column(children: [
                      for (final a in hw)
                        ListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          title: Text(asStr(a['title'])),
                          subtitle: Text('${asStr(a['subject_name'])} · due ${formatDate(asDateN(a['due_date']))}'),
                        ),
                    ]),
            ),
            const _NewsBlocks(),
          ]),
        );
      },
    );
  }
}
