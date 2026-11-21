import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/quick_form.dart';

/// Admin: the school-wide grade scale (percentage bands). The whole scale is saved at once.
class GradeScaleTab extends StatefulWidget {
  const GradeScaleTab({super.key});
  @override
  State<GradeScaleTab> createState() => _GradeScaleTabState();
}

class _GradeScaleTabState extends State<GradeScaleTab> {
  List<Map<String, dynamic>>? _bands;
  Object? _error;
  bool _dirty = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _error = null;
      _bands = null;
    });
    try {
      final res = asMap(await context.read<ApiClient>().get('/grade-scales'));
      final bands = asMapList(res['bands']);
      bands.sort((a, b) => asDouble(a['min_percentage']).compareTo(asDouble(b['min_percentage'])));
      if (mounted) {
        setState(() {
          _bands = bands;
          _dirty = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e);
    }
  }

  Future<void> _edit({int? index}) async {
    final b = index == null ? null : _bands![index];
    await showAppDialog<bool>(
      context,
      title: b == null ? 'Add grade band' : 'Edit grade ${asStr(b['grade'])}',
      builder: (dialogContext) => QuickForm(
        fields: [
          QField('grade', 'Grade', QType.text, required: true, initial: b?['grade'], helper: 'e.g. A+'),
          QField('min_percentage', 'From %', QType.number, required: true, initial: b?['min_percentage']),
          QField('max_percentage', 'To %', QType.number, required: true, initial: b?['max_percentage']),
          QField('gpa_points', 'GPA points (optional)', QType.number, initial: b?['gpa_points']),
          QField('remark', 'Remark', QType.text, initial: b?['remark'], helper: 'e.g. Excellent'),
          QField('is_pass', 'Counts as a pass', QType.toggle, initial: b == null ? true : asBool(b['is_pass'], true)),
        ],
        submitLabel: 'Apply',
        onSubmit: (v) async {
          final band = <String, dynamic>{
            'grade': v['grade'],
            'min_percentage': v['min_percentage'],
            'max_percentage': v['max_percentage'],
            'gpa_points': (v['gpa_points'] as String).isEmpty ? null : v['gpa_points'],
            'remark': v['remark'],
            'is_pass': v['is_pass'],
          };
          setState(() {
            if (index == null) {
              _bands!.add(band);
            } else {
              _bands![index] = band;
            }
            _bands!.sort((a, b) => asDouble(a['min_percentage']).compareTo(asDouble(b['min_percentage'])));
            _dirty = true;
          });
        },
      ),
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    try {
      await context.read<ApiClient>().put('/grade-scales', body: {'bands': _bands});
      if (mounted) showSnack(context, 'Grade scale saved');
      await _load();
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) return ErrorView(error: _error!, onRetry: _load);
    final bands = _bands;
    if (bands == null) return const LoadingView();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Wrap(spacing: 8, runSpacing: 8, alignment: WrapAlignment.end, children: [
        OutlinedButton.icon(onPressed: () => _edit(), icon: const Icon(Icons.add), label: const Text('Add band')),
        FilledButton.icon(onPressed: _dirty && !_saving ? _save : null, icon: const Icon(Icons.save_outlined), label: const Text('Save scale')),
      ]),
      const Padding(
        padding: EdgeInsets.symmetric(vertical: 8),
        child: Text('Bands must start at 0%, end at 100% and not overlap. Changes apply to all results (including published ones).', style: TextStyle(color: Brand.muted)),
      ),
      Expanded(
        child: ListView.separated(
          itemCount: bands.length,
          separatorBuilder: (context, i) => const SizedBox(height: 6),
          itemBuilder: (context, i) {
            final b = bands[i];
            final pass = asBool(b['is_pass'], true);
            return AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              child: Row(children: [
                SizedBox(width: 48, child: Text(asStr(b['grade']), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18))),
                Expanded(
                  child: Text('${formatNumber(asDouble(b['min_percentage']), decimals: 0)}% – ${formatNumber(asDouble(b['max_percentage']), decimals: 0)}%'
                      '${b['gpa_points'] != null ? ' · GPA ${asStr(b['gpa_points'])}' : ''}'
                      '${asStr(b['remark']).isNotEmpty ? ' · ${asStr(b['remark'])}' : ''}'),
                ),
                StatusChip(pass ? 'pass' : 'fail', color: pass ? Brand.success : Brand.danger),
                IconButton(tooltip: 'Edit', icon: const Icon(Icons.edit_outlined), onPressed: () => _edit(index: i)),
                IconButton(
                  tooltip: 'Remove',
                  icon: const Icon(Icons.delete_outline, color: Brand.danger),
                  onPressed: () => setState(() {
                    bands.removeAt(i);
                    _dirty = true;
                  }),
                ),
              ]),
            );
          },
        ),
      ),
    ]);
  }
}
