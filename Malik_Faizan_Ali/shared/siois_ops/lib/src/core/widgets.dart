import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'api_client.dart';
import 'format.dart';
import 'json.dart';
import 'lookups.dart';
import 'theme.dart';

// ------------------------------------------------------------------ responsive helpers
bool isWide(BuildContext context) => MediaQuery.sizeOf(context).width >= 900;
bool isMedium(BuildContext context) => MediaQuery.sizeOf(context).width >= 600;

/// Centres content and caps its width on large (web) screens; full width on phones.
class ContentWidth extends StatelessWidget {
  const ContentWidth({super.key, required this.child, this.maxWidth = 1100, this.padding});
  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    final pad = padding ?? EdgeInsets.all(isMedium(context) ? 24 : 12);
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(constraints: BoxConstraints(maxWidth: maxWidth), child: Padding(padding: pad, child: child)),
    );
  }
}

/// Standard page frame used by every screen: title row (with actions) above the body.
/// The body is laid out in the remaining space, so it may contain lists / scroll views.
class PageFrame extends StatelessWidget {
  const PageFrame({super.key, required this.title, this.subtitle, this.actions = const <Widget>[], required this.child, this.maxWidth = 1100});
  final String title;
  final String? subtitle;
  final List<Widget> actions;
  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    final narrow = !isMedium(context);
    final header = narrow
        ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: t.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
            if (subtitle != null) Text(subtitle!, style: t.bodyMedium?.copyWith(color: Brand.muted)),
            if (actions.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Wrap(spacing: 8, runSpacing: 8, children: actions)),
          ])
        : Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(title, style: t.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
                if (subtitle != null) Text(subtitle!, style: t.bodyMedium?.copyWith(color: Brand.muted)),
              ]),
            ),
            Wrap(spacing: 8, runSpacing: 8, children: actions),
          ]);
    return ContentWidth(
      maxWidth: maxWidth,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        header,
        const SizedBox(height: 16),
        Expanded(child: child),
      ]),
    );
  }
}

class AppCard extends StatelessWidget {
  const AppCard({super.key, required this.child, this.padding = const EdgeInsets.all(16), this.onTap});
  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final body = Padding(padding: padding, child: child);
    return Card(
      clipBehavior: Clip.antiAlias,
      child: onTap == null ? body : InkWell(onTap: onTap, child: body),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key, this.trailing});
  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 8, bottom: 8),
        child: Row(children: [
          Expanded(child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700))),
          if (trailing != null) trailing!,
        ]),
      );
}

class InfoRow extends StatelessWidget {
  const InfoRow(this.label, this.value, {super.key, this.bold = false});
  final String label;
  final String value;
  final bool bold;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 130, child: Text(label, style: const TextStyle(color: Brand.muted))),
          Expanded(child: Text(value, style: TextStyle(fontWeight: bold ? FontWeight.w700 : FontWeight.w500))),
        ]),
      );
}

class KpiCard extends StatelessWidget {
  const KpiCard({super.key, required this.label, required this.value, required this.icon, this.color = Brand.primary, this.onTap});
  final String label;
  final String value;
  final IconData icon;
  final Color color;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => AppCard(
        onTap: onTap,
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(value, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800), overflow: TextOverflow.ellipsis),
              Text(label, style: const TextStyle(color: Brand.muted, fontSize: 12.5), overflow: TextOverflow.ellipsis),
            ]),
          ),
        ]),
      );
}

/// Colour for the status words used across modules.
Color statusColor(String status) {
  switch (status.toLowerCase()) {
    case 'paid':
    case 'published':
    case 'resolved':
    case 'pass':
    case 'results_published':
    case 'completed':
    case 'present':
      return Brand.success;
    case 'partial':
    case 'in_review':
    case 'scheduled':
    case 'ongoing':
    case 'important':
    case 'incomplete':
    case 'normal':
      return Brand.info;
    case 'unpaid':
    case 'open':
    case 'draft':
    case 'pending':
      return Brand.warning;
    case 'overdue':
    case 'urgent':
    case 'fail':
    case 'high':
    case 'cancelled':
    case 'absent':
      return Brand.danger;
    default:
      return Brand.muted;
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.label, {super.key, this.color});
  final String label;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? statusColor(label);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(20)),
      child: Text(humanize(label), style: TextStyle(color: c, fontWeight: FontWeight.w700, fontSize: 12)),
    );
  }
}

// ------------------------------------------------------------------ states
class LoadingView extends StatelessWidget {
  const LoadingView({super.key});
  @override
  Widget build(BuildContext context) => const Center(child: Padding(padding: EdgeInsets.all(32), child: CircularProgressIndicator()));
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key, required this.icon, required this.title, this.message, this.action});
  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 48, color: Brand.muted),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleMedium, textAlign: TextAlign.center),
            if (message != null) ...[
              const SizedBox(height: 4),
              Text(message!, style: const TextStyle(color: Brand.muted), textAlign: TextAlign.center),
            ],
            if (action != null) ...[const SizedBox(height: 16), action!],
          ]),
        ),
      );
}

String errorMessage(Object e) => e is ApiException ? e.message : 'Something went wrong. Please try again.';

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, this.onRetry});
  final Object error;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => EmptyState(
        icon: Icons.error_outline,
        title: errorMessage(error),
        action: onRetry == null ? null : OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Try again')),
      );
}

/// Loads data once (and on [reload]); shows spinner / error with retry / the built content.
///
/// ```dart
/// AsyncView<List<Foo>>(
///   loader: () async => asMapList(await api.get('/foos')).map(Foo.fromJson).toList(),
///   builder: (context, data, reload) => ...,
/// )
/// ```
/// Change [loadKey] to force a reload when filters change.
class AsyncView<T> extends StatefulWidget {
  const AsyncView({super.key, required this.loader, required this.builder, this.loadKey});
  final Future<T> Function() loader;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;
  final Object? loadKey;

  @override
  State<AsyncView<T>> createState() => _AsyncViewState<T>();
}

class _AsyncViewState<T> extends State<AsyncView<T>> {
  late Future<T> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.loader();
  }

  @override
  void didUpdateWidget(covariant AsyncView<T> old) {
    super.didUpdateWidget(old);
    if (old.loadKey != widget.loadKey) _future = widget.loader();
  }

  Future<void> _reload() async {
    final f = widget.loader();
    setState(() { _future = f; });
    try {
      await f;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const LoadingView();
          if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _reload);
          return widget.builder(context, snap.data as T, _reload);
        },
      );
}

// ------------------------------------------------------------------ feedback
void showSnack(BuildContext context, String message, {bool error = false}) {
  final m = ScaffoldMessenger.maybeOf(context);
  if (m == null) return;
  m.hideCurrentSnackBar();
  m.showSnackBar(SnackBar(
    content: Text(message),
    backgroundColor: error ? Brand.danger : null,
    behavior: SnackBarBehavior.floating,
    width: isMedium(context) ? 480 : null,
  ));
}

void showError(BuildContext context, Object e) =>
    showSnack(context, e is ApiException ? e.fullMessage : errorMessage(e), error: true);

Future<bool> confirmDialog(BuildContext context,
    {required String title, required String message, String confirmLabel = 'Confirm', bool destructive = false}) async {
  final res = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(message),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(
          style: destructive ? FilledButton.styleFrom(backgroundColor: Brand.danger) : null,
          onPressed: () => Navigator.pop(ctx, true),
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
  return res ?? false;
}

/// Dialog with a titled, scrollable body. Close it with `Navigator.pop(context, result)`.
Future<T?> showAppDialog<T>(BuildContext context, {required String title, required WidgetBuilder builder, double width = 520}) {
  return showDialog<T>(
    context: context,
    barrierDismissible: false,
    builder: (ctx) => AlertDialog(
      title: Row(children: [
        Expanded(child: Text(title)),
        IconButton(onPressed: () => Navigator.pop(ctx), icon: const Icon(Icons.close), tooltip: 'Close'),
      ]),
      content: SizedBox(width: width, child: SingleChildScrollView(child: Builder(builder: builder))),
    ),
  );
}

/// Pulls the "doing something" state out of every form: `await runBusy(() => api.post(...))`.
mixin BusyMixin<S extends StatefulWidget> on State<S> {
  bool busy = false;

  Future<bool> runBusy(Future<void> Function() action, {String? success}) async {
    if (busy) return false;
    setState(() => busy = true);
    try {
      await action();
      if (mounted && success != null) showSnack(context, success);
      return true;
    } catch (e) {
      if (mounted) showError(context, e);
      return false;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

// ------------------------------------------------------------------ form fields
/// Drop-down with a floating label (uses DropdownButton so it is stable across Flutter versions).
class AppDropdown<T> extends StatelessWidget {
  const AppDropdown({
    super.key,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
    this.errorText,
    this.hint,
    this.allowClear = false,
  });

  final String label;
  final T? value;
  final List<DropdownMenuItem<T>> items;
  final ValueChanged<T?>? onChanged;
  final String? errorText;
  final String? hint;

  /// Adds an "All / none" entry (value null) at the top.
  final bool allowClear;

  @override
  Widget build(BuildContext context) {
    final all = <DropdownMenuItem<T?>>[
      if (allowClear) DropdownMenuItem<T?>(value: null, child: Text(hint ?? 'All', style: const TextStyle(color: Brand.muted))),
      ...items.map((i) => DropdownMenuItem<T?>(value: i.value, child: i.child)),
    ];
    final hasValue = value != null && items.any((i) => i.value == value);
    return InputDecorator(
      decoration: InputDecoration(labelText: label, errorText: errorText),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T?>(
          isExpanded: true,
          isDense: true,
          value: hasValue ? value : null,
          hint: Text(hint ?? 'Select', style: const TextStyle(color: Brand.muted)),
          items: all,
          onChanged: onChanged,
        ),
      ),
    );
  }
}

class DateField extends StatelessWidget {
  const DateField({super.key, required this.label, required this.value, required this.onChanged, this.firstDate, this.lastDate, this.errorText, this.clearable = false});
  final String label;
  final DateTime? value;
  final ValueChanged<DateTime?> onChanged;
  final DateTime? firstDate;
  final DateTime? lastDate;
  final String? errorText;
  final bool clearable;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: () async {
        final now = DateTime.now();
        final picked = await showDatePicker(
          context: context,
          initialDate: value ?? now,
          firstDate: firstDate ?? DateTime(now.year - 3),
          lastDate: lastDate ?? DateTime(now.year + 3),
        );
        if (picked != null) onChanged(dateOnly(picked));
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          errorText: errorText,
          suffixIcon: clearable && value != null
              ? IconButton(icon: const Icon(Icons.clear, size: 18), onPressed: () => onChanged(null))
              : const Icon(Icons.calendar_today_outlined, size: 18),
        ),
        child: Text(value == null ? 'Select date' : formatDate(value), style: TextStyle(color: value == null ? Brand.muted : null)),
      ),
    );
  }
}

class TimeField extends StatelessWidget {
  const TimeField({super.key, required this.label, required this.value, required this.onChanged, this.errorText});
  final String label;
  final TimeOfDay? value;
  final ValueChanged<TimeOfDay?> onChanged;
  final String? errorText;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: () async {
        final picked = await showTimePicker(context: context, initialTime: value ?? const TimeOfDay(hour: 8, minute: 0));
        if (picked != null) onChanged(picked);
      },
      child: InputDecorator(
        decoration: InputDecoration(labelText: label, errorText: errorText, suffixIcon: const Icon(Icons.schedule, size: 18)),
        child: Text(value == null ? 'Select time' : formatTimeOfDay(value!), style: TextStyle(color: value == null ? Brand.muted : null)),
      ),
    );
  }
}

/// Type-ahead student search for admins (uses `/lookups/students/search`).
class StudentPickerField extends StatelessWidget {
  const StudentPickerField({super.key, required this.onSelected, this.label = 'Student (type a name or roll no.)', this.initial});
  final ValueChanged<StudentRef> onSelected;
  final String label;
  final StudentRef? initial;

  @override
  Widget build(BuildContext context) {
    final lookups = context.read<Lookups>();
    return Autocomplete<StudentRef>(
      initialValue: initial == null ? null : TextEditingValue(text: initial!.display),
      displayStringForOption: (s) => s.display,
      optionsBuilder: (TextEditingValue v) async {
        if (v.text.trim().length < 2) return const Iterable<StudentRef>.empty();
        try {
          return await lookups.searchStudents(v.text.trim());
        } catch (_) {
          return const Iterable<StudentRef>.empty();
        }
      },
      onSelected: onSelected,
      fieldViewBuilder: (ctx, controller, focusNode, onSubmit) => TextField(
        controller: controller,
        focusNode: focusNode,
        decoration: InputDecoration(labelText: label, prefixIcon: const Icon(Icons.search)),
      ),
      optionsViewBuilder: (ctx, onSel, options) => Align(
        alignment: Alignment.topLeft,
        child: Material(
          elevation: 4,
          borderRadius: BorderRadius.circular(10),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 260, maxWidth: 420),
            child: ListView(
              shrinkWrap: true,
              children: options
                  .map((s) => ListTile(dense: true, title: Text(s.fullName), subtitle: Text('${s.rollNo} · ${s.sectionLabel ?? ''}'), onTap: () => onSel(s)))
                  .toList(),
            ),
          ),
        ),
      ),
    );
  }
}

/// Simple previous / next pager for `{items,total,page,page_size}` lists.
class PaginationBar extends StatelessWidget {
  const PaginationBar({super.key, required this.page, required this.pageSize, required this.total, required this.onPage});
  final int page;
  final int pageSize;
  final int total;
  final ValueChanged<int> onPage;

  @override
  Widget build(BuildContext context) {
    final pages = total == 0 ? 1 : ((total + pageSize - 1) ~/ pageSize);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        IconButton(onPressed: page > 1 ? () => onPage(page - 1) : null, icon: const Icon(Icons.chevron_left), tooltip: 'Previous'),
        Text('Page $page of $pages · $total total'),
        IconButton(onPressed: page < pages ? () => onPage(page + 1) : null, icon: const Icon(Icons.chevron_right), tooltip: 'Next'),
      ]),
    );
  }
}

/// A row of filter controls that wraps on small screens.
class FilterBar extends StatelessWidget {
  const FilterBar({super.key, required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final wide = isMedium(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Wrap(
        spacing: 12,
        runSpacing: 12,
        children: children.map((c) => SizedBox(width: wide ? 220 : double.infinity, child: c)).toList(),
      ),
    );
  }
}

/// Debounces rapid calls (search boxes).
class Debouncer {
  Debouncer([this.delay = const Duration(milliseconds: 350)]);
  final Duration delay;
  Timer? _t;
  void run(VoidCallback action) {
    _t?.cancel();
    _t = Timer(delay, action);
  }

  void dispose() => _t?.cancel();
}

/// Parses `GET` lists into models: `await loadList(api, '/x', Model.fromJson)`.
List<T> parseList<T>(dynamic json, T Function(Map<String, dynamic>) parse) => asMapList(json).map(parse).toList();
