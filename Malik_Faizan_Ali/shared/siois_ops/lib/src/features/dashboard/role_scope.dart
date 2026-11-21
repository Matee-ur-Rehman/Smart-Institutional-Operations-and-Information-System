import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/auth.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';

/// Resolves "which student am I looking at" for the two mobile-only roles:
///  * student -> their own record
///  * parent  -> one of their linked children (a drop-down appears when there are several)
///
/// The [builder] is rebuilt (with fresh state) whenever the selected child changes.
/// Must be placed where it receives a bounded height (e.g. as the child of `PageFrame`).
class StudentScope extends StatefulWidget {
  const StudentScope({super.key, required this.builder});

  final Widget Function(BuildContext context, ChildRef child) builder;

  @override
  State<StudentScope> createState() => _StudentScopeState();
}

class _StudentScopeState extends State<StudentScope> {
  late Future<List<ChildRef>> _future;
  String? _selectedId;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<ChildRef>> _load() async {
    final lookups = context.read<Lookups>();
    final role = context.read<AuthController>().user?.role;
    if (role == Role.student) {
      final me = await lookups.me();
      final s = me.student;
      return s == null ? <ChildRef>[] : <ChildRef>[s];
    }
    return lookups.myChildren();
  }

  @override
  Widget build(BuildContext context) {
    final role = context.read<AuthController>().user?.role;
    return FutureBuilder<List<ChildRef>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) {
          return ErrorView(error: snap.error!, onRetry: () => setState(() { _future = _load(); }));
        }
        final data = snap.data ?? <ChildRef>[];
        if (data.isEmpty) {
          return const EmptyState(
            icon: Icons.person_off_outlined,
            title: 'No student is linked to your account',
            message: 'Please contact the school office.',
          );
        }
        final selected = data.firstWhere((c) => c.studentId == _selectedId, orElse: () => data.first);
        Widget? header;
        if (data.length > 1) {
          header = Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: AppDropdown<String>(
              label: 'Child',
              value: selected.studentId,
              items: data
                  .map((c) => DropdownMenuItem<String>(
                      value: c.studentId, child: Text('${c.fullName} · ${c.sectionLabel ?? ''}', overflow: TextOverflow.ellipsis)))
                  .toList(),
              onChanged: (v) {
                if (v != null) setState(() => _selectedId = v);
              },
            ),
          );
        } else if (role == Role.parent) {
          header = Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Row(children: [
              const Icon(Icons.child_care, size: 18, color: Brand.muted),
              const SizedBox(width: 6),
              Expanded(
                child: Text('${selected.fullName} · ${selected.sectionLabel ?? ''}',
                    style: const TextStyle(color: Brand.muted, fontWeight: FontWeight.w600), overflow: TextOverflow.ellipsis),
              ),
            ]),
          );
        }
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (header != null) header,
          Expanded(child: KeyedSubtree(key: ValueKey<String>(selected.studentId), child: widget.builder(context, selected))),
        ]);
      },
    );
  }
}
