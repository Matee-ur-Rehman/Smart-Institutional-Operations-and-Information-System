import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/report_download.dart';
import '../dashboard/role_scope.dart';
import 'attendance_models.dart';

/// Student (own) and parent (each child): attendance percentage, counts and the day-by-day record.
class AttendanceViewPage extends StatelessWidget {
  const AttendanceViewPage({super.key});

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Attendance',
      subtitle: 'Attendance record and percentage',
      child: StudentScope(builder: (context, child) => _StudentAttendance(studentId: child.studentId)),
    );
  }
}

class _StudentAttendance extends StatefulWidget {
  const _StudentAttendance({required this.studentId});
  final String studentId;
  @override
  State<_StudentAttendance> createState() => _StudentAttendanceState();
}

class _StudentAttendanceState extends State<_StudentAttendance> {
  DateTime? _from;
  DateTime? _to;

  Map<String, dynamic> get _range => {'from_date': _from, 'to_date': _to};

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      FilterBar(children: [
        DateField(label: 'From (optional)', value: _from, clearable: true, onChanged: (d) => setState(() => _from = d)),
        DateField(label: 'To (optional)', value: _to, clearable: true, lastDate: DateTime.now(), onChanged: (d) => setState(() => _to = d)),
      ]),
      Expanded(
        child: AsyncView<Map<String, dynamic>>(
          loadKey: '${widget.studentId}|$_from|$_to',
          loader: () async => asMap(await api.get('/attendance/students/${widget.studentId}', query: {
            if (_from != null) 'from_date': isoDate(_from!),
            if (_to != null) 'to_date': isoDate(_to!),
          })),
          builder: (context, data, reload) {
            final sm = AttendanceSummary.fromJson(data['summary']);
            final records = asMapList(data['records']).map(AttendanceRecord.fromJson).toList();
            final pct = sm.percentage;
            final good = pct == null || pct >= 75;
            final wide = isMedium(context);
            final kpis = <Widget>[
              KpiCard(label: 'Attendance', value: formatPercent(pct), icon: Icons.percent, color: good ? Brand.success : Brand.danger),
              KpiCard(label: 'Present', value: '${sm.present}', icon: Icons.check_circle_outline, color: Brand.success),
              KpiCard(label: 'Late', value: '${sm.late}', icon: Icons.schedule, color: Brand.warning),
              KpiCard(label: 'Absent', value: '${sm.absent}', icon: Icons.cancel_outlined, color: Brand.danger),
              KpiCard(label: 'On leave', value: '${sm.leave}', icon: Icons.beach_access_outlined, color: Brand.info),
            ];
            return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Wrap(
                spacing: 10,
                runSpacing: 10,
                children: kpis.map((k) => SizedBox(width: wide ? 200 : (MediaQuery.sizeOf(context).width - 42) / 2, child: k)).toList(),
              ),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                  child: Text('${formatDate(asDateN(data['from_date']))} – ${formatDate(asDateN(data['to_date']))} · ${sm.totalDays} marked day(s)',
                      style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                ),
                ReportButton(label: 'PDF', path: '/reports/attendance/students/${widget.studentId}', query: {..._range, 'format': 'pdf'}, fallbackName: 'attendance.pdf'),
              ]),
              const SizedBox(height: 8),
              Expanded(
                child: records.isEmpty
                    ? const EmptyState(icon: Icons.event_busy_outlined, title: 'No attendance marked in this period')
                    : ListView.separated(
                        itemCount: records.length,
                        separatorBuilder: (context, i) => const SizedBox(height: 6),
                        itemBuilder: (context, i) {
                          final r = records[i];
                          return AppCard(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                            child: Row(children: [
                              Expanded(
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text('${formatWeekday(r.date)}, ${formatDate(r.date)}', style: const TextStyle(fontWeight: FontWeight.w600)),
                                  if (r.remarks != null && r.remarks!.isNotEmpty) Text(r.remarks!, style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                                ]),
                              ),
                              AttendanceChip(r.status),
                            ]),
                          );
                        },
                      ),
              ),
            ]);
          },
        ),
      ),
    ]);
  }
}
