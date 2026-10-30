import 'package:flutter/material.dart';

import '../core/api_exception.dart';
import 'format.dart';

ThemeData buildOpsTheme() => ThemeData(
      useMaterial3: true,
      colorSchemeSeed: const Color(0xFF1B5E9B),
      visualDensity: VisualDensity.adaptivePlatformDensity,
    );

/// Puts [gap] pixels between widgets of a Column/Wrap child list.
List<Widget> spaced(List<Widget> items, [double gap = 12]) {
  final out = <Widget>[];
  for (var i = 0; i < items.length; i++) {
    if (i > 0) out.add(SizedBox(height: gap));
    out.add(items[i]);
  }
  return out;
}

void showMessage(BuildContext context, String text, {bool error = false}) {
  final messenger = ScaffoldMessenger.maybeOf(context);
  if (messenger == null) return;
  messenger.hideCurrentSnackBar();
  messenger.showSnackBar(SnackBar(
    content: Text(text),
    backgroundColor: error ? Colors.red.shade700 : null,
  ));
}

/// Runs [action]; shows an error SnackBar on failure. Returns true on success.
Future<bool> runAction(BuildContext context, Future<void> Function() action, {String? success}) async {
  try {
    await action();
    if (success != null && context.mounted) showMessage(context, success);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) showMessage(context, e.message, error: true);
    return false;
  } catch (e) {
    if (context.mounted) showMessage(context, 'Something went wrong: $e', error: true);
    return false;
  }
}

Future<bool> confirmDialog(BuildContext context, String title, String body, {String yes = 'Yes'}) async {
  final result = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Text(body),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(yes)),
      ],
    ),
  );
  return result ?? false;
}

/// A small form dialog. The caller keeps the field values in local variables, [validate] returns a
/// message (or null), and [onSubmit] performs the API call (an ApiException is shown inside the dialog).
/// Returns true when the form was submitted successfully.
Future<bool> showFormDialog(
  BuildContext context, {
  required String title,
  String submitLabel = 'Save',
  required Widget Function(BuildContext context, StateSetter setState) builder,
  required String? Function() validate,
  required Future<void> Function() onSubmit,
}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) {
      String? error;
      var busy = false;
      return StatefulBuilder(builder: (ctx, setState) {
        return AlertDialog(
          title: Text(title),
          content: SizedBox(
            width: 420,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 4),
                  builder(ctx, setState),
                  if (error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(error!, style: TextStyle(color: Theme.of(ctx).colorScheme.error)),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(dialogContext, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: busy
                  ? null
                  : () async {
                      final problem = validate();
                      if (problem != null) {
                        setState(() => error = problem);
                        return;
                      }
                      setState(() {
                        busy = true;
                        error = null;
                      });
                      try {
                        await onSubmit();
                        if (dialogContext.mounted) Navigator.pop(dialogContext, true);
                      } on ApiException catch (e) {
                        setState(() {
                          busy = false;
                          error = e.message;
                        });
                      } catch (e) {
                        setState(() {
                          busy = false;
                          error = e.toString();
                        });
                      }
                    },
              child: Text(busy ? 'Saving...' : submitLabel),
            ),
          ],
        );
      });
    },
  );
  return result ?? false;
}

/// Text field for use inside [showFormDialog]. Keeps the value in the caller's variable via [onChanged].
Widget formText(
  String label,
  String initial,
  ValueChanged<String> onChanged, {
  int maxLines = 1,
  bool number = false,
  bool obscure = false,
  String? hint,
}) {
  return TextFormField(
    initialValue: initial,
    onChanged: onChanged,
    maxLines: maxLines,
    obscureText: obscure,
    keyboardType: number ? const TextInputType.numberWithOptions(decimal: true) : null,
    decoration: InputDecoration(labelText: label, hintText: hint, border: const OutlineInputBorder()),
  );
}

/// Dropdown that never uses the (renamed) FormField `value` parameter.
class PickerField<T> extends StatelessWidget {
  const PickerField({
    super.key,
    required this.label,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  final String label;
  final T? value;
  final List<DropdownMenuItem<T>> items;
  final ValueChanged<T?> onChanged;

  @override
  Widget build(BuildContext context) {
    final valid = items.any((i) => i.value == value);
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          value: valid ? value : null,
          isExpanded: true,
          items: items,
          onChanged: onChanged,
        ),
      ),
    );
  }
}

/// Convenience: dropdown over simple (value, text) pairs.
Widget pickString(
  String label,
  String? value,
  List<MapEntry<String, String>> options,
  ValueChanged<String?> onChanged,
) {
  return PickerField<String>(
    label: label,
    value: value,
    items: [for (final o in options) DropdownMenuItem<String>(value: o.key, child: Text(o.value, overflow: TextOverflow.ellipsis))],
    onChanged: onChanged,
  );
}

class DateField extends StatelessWidget {
  const DateField({
    super.key,
    required this.label,
    required this.value,
    required this.onChanged,
    this.firstDate,
    this.lastDate,
  });

  final String label;
  final DateTime? value;
  final ValueChanged<DateTime> onChanged;
  final DateTime? firstDate;
  final DateTime? lastDate;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () async {
        final now = DateTime.now();
        final first = firstDate ?? DateTime(now.year - 2);
        final last = lastDate ?? DateTime(now.year + 3);
        var initial = value ?? now;
        if (initial.isBefore(first)) initial = first;
        if (initial.isAfter(last)) initial = last;
        final picked = await showDatePicker(context: context, initialDate: initial, firstDate: first, lastDate: last);
        if (picked != null) onChanged(picked);
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          suffixIcon: const Icon(Icons.calendar_today, size: 18),
        ),
        child: Text(value == null ? 'Select date' : fmtDate(value)),
      ),
    );
  }
}

/// Time of day as "HH:MM" (the API format).
class TimeField extends StatelessWidget {
  const TimeField({super.key, required this.label, required this.value, required this.onChanged});

  final String label;
  final String? value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () async {
        final picked = await showTimePicker(
          context: context,
          initialTime: timeOfDayFromApi(value) ?? const TimeOfDay(hour: 8, minute: 0),
        );
        if (picked != null) onChanged(timeOfDayToApi(picked));
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
          suffixIcon: const Icon(Icons.access_time, size: 18),
        ),
        child: Text(value == null || value!.isEmpty ? 'Select time' : value!),
      ),
    );
  }
}

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key, this.label});

  final String status;
  final String? label;

  @override
  Widget build(BuildContext context) {
    final c = statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(color: c.withAlpha(35), borderRadius: BorderRadius.circular(12)),
      child: Text(label ?? titleCase(status), style: TextStyle(color: c, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}

class EmptyView extends StatelessWidget {
  const EmptyView(this.message, {super.key, this.icon = Icons.inbox_outlined});

  final String message;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Theme.of(context).disabledColor),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center, style: TextStyle(color: Theme.of(context).disabledColor)),
          ],
        ),
      ),
    );
  }
}

class ErrorView extends StatelessWidget {
  const ErrorView({super.key, required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final text = error is ApiException ? (error as ApiException).message : error.toString();
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: Theme.of(context).colorScheme.error),
            const SizedBox(height: 8),
            Text(text, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Try again')),
          ],
        ),
      ),
    );
  }
}

/// Shows a spinner, an error with a retry button, or [builder] once [future] completes.
class FutureView<T> extends StatelessWidget {
  const FutureView({super.key, required this.future, required this.builder, required this.onRetry});

  final Future<T> future;
  final Widget Function(BuildContext context, T data) builder;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<T>(
      future: future,
      builder: (ctx, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: onRetry);
        return builder(ctx, snap.data as T);
      },
    );
  }
}

/// Keeps page content readable on wide web screens.
class ContentWidth extends StatelessWidget {
  const ContentWidth({super.key, required this.child, this.maxWidth = 980});

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(constraints: BoxConstraints(maxWidth: maxWidth), child: child),
    );
  }
}

/// A "label: value" row used in detail views.
class InfoRow extends StatelessWidget {
  const InfoRow(this.label, this.value, {super.key});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(width: 120, child: Text(label, style: TextStyle(color: Theme.of(context).hintColor))),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}

/// Small coloured number card (fee summary, results, complaint counts).
class StatCard extends StatelessWidget {
  const StatCard({super.key, required this.label, required this.value, this.color});

  final String label;
  final String value;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = color ?? Theme.of(context).colorScheme.primary;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(label, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12)),
            const SizedBox(height: 6),
            Text(value, style: TextStyle(color: c, fontSize: 20, fontWeight: FontWeight.w700)),
          ],
        ),
      ),
    );
  }
}
