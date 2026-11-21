import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/report_download.dart';

/// Report centre for admin / teachers: attendance (class and student), timetable and the student list.
/// Result cards, fee receipts and fee statements are downloaded from the Exams and Fees screens.
class ReportsPage extends StatefulWidget {
  const ReportsPage({super.key, required this.isAdmin});
  final bool isAdmin;
  @override
  State<ReportsPage> createState() => _ReportsPageState();
}

class _ReportsPageState extends State<ReportsPage> {
  late Future<List<SectionRef>> _sections;
  String? _sectionId;
  String? _studentId;
  DateTime? _from;
  DateTime? _to;

  @override
  void initState() {
    super.initState();
    _sections = context.read<Lookups>().sections();
  }

  Widget _card(String title, String help, List<Widget> body, List<Widget> buttons) => AppCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 2),
          Text(help, style: const TextStyle(color: Brand.muted)),
          if (body.isNotEmpty) ...[const SizedBox(height: 12), ...body],
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: buttons),
        ]),
      );

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Reports',
      subtitle: 'Download PDF and CSV reports',
      child: FutureBuilder<List<SectionRef>>(
        future: _sections,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const LoadingView();
          if (snap.hasError) return ErrorView(error: snap.error!, onRetry: () => setState(() { _sections = context.read<Lookups>().sections(); }));
          final sections = snap.data ?? <SectionRef>[];
          if (sections.isEmpty) {
            return const EmptyState(icon: Icons.summarize_outlined, title: 'No classes available', message: 'Ask the administrator to assign you to a class.');
          }
          final sid = sections.any((s) => s.id == _sectionId) ? _sectionId : null;
          final section = AppDropdown<String>(
            label: 'Class / section',
            value: sid,
            items: sections.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.label))).toList(),
            onChanged: (v) => setState(() {
              _sectionId = v;
              _studentId = null;
            }),
          );
          final range = <String, dynamic>{'from_date': _from, 'to_date': _to};
          final dates = Wrap(spacing: 12, runSpacing: 12, children: [
            SizedBox(width: 220, child: DateField(label: 'From (optional)', value: _from, clearable: true, onChanged: (d) => setState(() => _from = d))),
            SizedBox(width: 220, child: DateField(label: 'To (optional)', value: _to, clearable: true, lastDate: DateTime.now(), onChanged: (d) => setState(() => _to = d))),
          ]);
          return ListView(children: [
            _card(
              'Class attendance',
              'Present / late / absent / leave counts and percentage for every student in a section. Low attendance is flagged.',
              [SizedBox(width: 360, child: section), const SizedBox(height: 12), dates],
              sid == null
                  ? [const Text('Select a class first', style: TextStyle(color: Brand.muted))]
                  : [
                      ReportButton(label: 'PDF', path: '/reports/attendance/sections/$sid', query: {...range, 'format': 'pdf'}, fallbackName: 'class_attendance.pdf'),
                      ReportButton(label: 'CSV', icon: Icons.table_chart_outlined, path: '/reports/attendance/sections/$sid', query: {...range, 'format': 'csv'}, fallbackName: 'class_attendance.csv'),
                    ],
            ),
            const SizedBox(height: 12),
            _card(
              'Student attendance',
              'Day-by-day attendance of one student, with a summary.',
              [
                SizedBox(width: 360, child: section),
                const SizedBox(height: 12),
                if (sid != null)
                  FutureBuilder<List<StudentRef>>(
                    future: context.read<Lookups>().students(sid),
                    builder: (context, ss) {
                      final students = ss.data ?? <StudentRef>[];
                      return SizedBox(
                        width: 360,
                        child: AppDropdown<String>(
                          label: ss.connectionState != ConnectionState.done ? 'Student (loading…)' : 'Student',
                          value: _studentId,
                          items: students.map((s) => DropdownMenuItem<String>(value: s.id, child: Text(s.display, overflow: TextOverflow.ellipsis))).toList(),
                          onChanged: (v) => setState(() => _studentId = v),
                        ),
                      );
                    },
                  ),
                const SizedBox(height: 12),
                dates,
              ],
              _studentId == null
                  ? [const Text('Select a class and a student', style: TextStyle(color: Brand.muted))]
                  : [ReportButton(label: 'PDF', path: '/reports/attendance/students/$_studentId', query: {...range, 'format': 'pdf'}, fallbackName: 'student_attendance.pdf')],
            ),
            const SizedBox(height: 12),
            _card(
              'Class timetable',
              'The weekly timetable of a section as a printable PDF.',
              [SizedBox(width: 360, child: section)],
              sid == null
                  ? [const Text('Select a class first', style: TextStyle(color: Brand.muted))]
                  : [ReportButton(label: 'PDF', path: '/reports/timetable/$sid', fallbackName: 'timetable.pdf')],
            ),
            if (widget.isAdmin) ...[
              const SizedBox(height: 12),
              _card(
                'Student list',
                'All active students with section and parent contacts (CSV). Select a class to limit it, or leave empty for the whole school.',
                [SizedBox(width: 360, child: section)],
                [ReportButton(label: 'CSV', icon: Icons.table_chart_outlined, path: '/reports/students', query: {'section_id': sid}, fallbackName: 'students.csv')],
              ),
            ],
          ]);
        },
      ),
    );
  }
}
