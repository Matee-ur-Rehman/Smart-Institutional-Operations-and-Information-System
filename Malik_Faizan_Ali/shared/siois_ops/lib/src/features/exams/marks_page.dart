import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import 'exams_models.dart';

/// Mark entry for one paper (class + subject). Empty rows are left unmarked; "Absent" counts as 0.
class MarksPage extends StatelessWidget {
  const MarksPage({super.key, required this.paper});
  final ExamPaper paper;

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiClient>();
    return Scaffold(
      appBar: AppBar(title: Text('${paper.subjectName} · ${paper.sectionLabel}')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ContentWidth(
          maxWidth: 900,
          child: AsyncView<Map<String, dynamic>>(
            loader: () async => asMap(await api.get('/exam-schedules/${paper.id}/marks')),
            builder: (context, data, reload) => _MarksSheet(
              paper: paper,
              locked: asBool(data['locked']),
              examStatus: asStr(data['exam_status']),
              rows: asMapList(data['rows']),
              onSaved: reload,
            ),
          ),
        ),
      ),
    );
  }
}

class _MarksSheet extends StatefulWidget {
  const _MarksSheet({required this.paper, required this.locked, required this.examStatus, required this.rows, required this.onSaved});
  final ExamPaper paper;
  final bool locked;
  final String examStatus;
  final List<Map<String, dynamic>> rows;
  final Future<void> Function() onSaved;
  @override
  State<_MarksSheet> createState() => _MarksSheetState();
}

/// 45.0 -> "45", 45.5 -> "45.5" (no trailing zeros, no separators).
String _plain(double d) => d == d.roundToDouble() ? d.toInt().toString() : d.toString();

class _MarksSheetState extends State<_MarksSheet> with BusyMixin {
  final Map<String, TextEditingController> _marks = <String, TextEditingController>{};
  final Map<String, bool> _absent = <String, bool>{};
  final Map<String, String?> _errors = <String, String?>{};

  @override
  void initState() {
    super.initState();
    for (final r in widget.rows) {
      final id = asStr(r['student_id']);
      final m = r['marks_obtained'];
      _marks[id] = TextEditingController(text: m == null ? '' : _plain(asDouble(m)));
      _absent[id] = asBool(r['is_absent']);
    }
  }

  @override
  void dispose() {
    for (final c in _marks.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    _errors.clear();
    final entries = <Map<String, dynamic>>[];
    for (final r in widget.rows) {
      final id = asStr(r['student_id']);
      final text = _marks[id]!.text.trim();
      final absent = _absent[id] ?? false;
      double? value;
      if (!absent && text.isNotEmpty) {
        value = double.tryParse(text);
        if (value == null) {
          _errors[id] = 'Not a number';
        } else if (value < 0 || value > widget.paper.total) {
          _errors[id] = '0 – ${formatNumber(widget.paper.total)}';
        }
      }
      entries.add({'student_id': id, 'marks_obtained': absent || text.isEmpty ? null : text, 'is_absent': absent});
    }
    if (_errors.isNotEmpty) {
      setState(() {});
      showSnack(context, 'Please correct the marked rows', error: true);
      return;
    }
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.put('/exam-schedules/${widget.paper.id}/marks', body: {'entries': entries}, );
    });
    if (ok && mounted) {
      showSnack(context, 'Marks saved');
      await widget.onSaved();
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.paper;
    if (widget.rows.isEmpty) return const EmptyState(icon: Icons.people_outline, title: 'No students in this class');
    final locked = widget.locked;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Expanded(child: Text('Total ${formatNumber(p.total)} · Passing ${formatNumber(p.passing)}', style: const TextStyle(fontWeight: FontWeight.w600))),
        if (!locked) FilledButton.icon(onPressed: busy ? null : _save, icon: const Icon(Icons.save_outlined), label: const Text('Save marks')),
      ]),
      if (locked)
        Container(
          margin: const EdgeInsets.only(top: 8),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: Brand.warning.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
          child: Row(children: [
            const Icon(Icons.lock_outline, size: 18, color: Brand.warning),
            const SizedBox(width: 8),
            Expanded(child: Text(widget.examStatus == 'draft' ? 'The exam is still a draft; marks cannot be entered yet.' : 'Results are published; marks can no longer be changed.')),
          ]),
        ),
      const SizedBox(height: 8),
      Expanded(
        child: ListView.separated(
          itemCount: widget.rows.length,
          separatorBuilder: (context, i) => const SizedBox(height: 6),
          itemBuilder: (context, i) {
            final r = widget.rows[i];
            final id = asStr(r['student_id']);
            final absent = _absent[id] ?? false;
            final grade = asStrN(r['grade']);
            return AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(asStr(r['full_name']), style: const TextStyle(fontWeight: FontWeight.w600)),
                    Text('Roll ${asStr(r['roll_no'])}${grade != null ? ' · ${formatPercent(asDoubleN(r['percentage']))} · $grade' : ''}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                  ]),
                ),
                SizedBox(
                  width: 100,
                  child: TextField(
                    controller: _marks[id],
                    enabled: !locked && !absent,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    textAlign: TextAlign.center,
                    decoration: InputDecoration(isDense: true, hintText: absent ? 'Absent' : 'Marks', errorText: _errors[id]),
                  ),
                ),
                const SizedBox(width: 8),
                Column(mainAxisSize: MainAxisSize.min, children: [
                  const Text('Absent', style: TextStyle(fontSize: 11, color: Brand.muted)),
                  SizedBox(
                    height: 28,
                    child: Checkbox(
                      value: absent,
                      onChanged: locked
                          ? null
                          : (v) => setState(() {
                                _absent[id] = v ?? false;
                                if (v == true) _marks[id]!.clear();
                              }),
                    ),
                  ),
                ]),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}
