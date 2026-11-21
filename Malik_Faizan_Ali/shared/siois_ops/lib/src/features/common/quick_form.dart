import 'package:flutter/material.dart';

import '../../core/api_client.dart';
import '../../core/widgets.dart';
import 'form_support.dart';

enum QType { text, multiline, number, dropdown, date, toggle, time}

/// One field of a [QuickForm]. Values handed to `onSubmit`:
/// text / multiline -> String (trimmed), number -> String, dropdown -> String? (the option value),
/// date -> DateTime?, toggle -> bool.
class QField {
  const QField(this.key, this.label, this.type,
      {this.required = false, this.options = const <MapEntry<String, String>>[], this.initial, this.helper, this.clearable = false});

  /// API field name (also used to show server-side validation errors).
  final String key;
  final String label;
  final QType type;
  final bool required;
  final List<MapEntry<String, String>> options; // value -> label
  final dynamic initial;
  final String? helper;
  final bool clearable;
}

/// A small declarative form shown inside `showAppDialog`. Pops `true` after [onSubmit] succeeds.
/// [onSubmit] may throw an [ApiException]; its field errors are shown next to the fields.
class QuickForm extends StatefulWidget {
  const QuickForm({super.key, required this.fields, required this.onSubmit, this.submitLabel = 'Save', this.intro, this.destructive = false});

  final List<QField> fields;
  final Future<void> Function(Map<String, dynamic> values) onSubmit;
  final String submitLabel;
  final String? intro;
  final bool destructive;

  @override
  State<QuickForm> createState() => _QuickFormState();
}

class _QuickFormState extends State<QuickForm> with BusyMixin {
  final Map<String, TextEditingController> _controllers = <String, TextEditingController>{};
  final Map<String, dynamic> _values = <String, dynamic>{};
  final FormErrors _err = FormErrors();

  @override
  void initState() {
    super.initState();
    for (final f in widget.fields) {
      switch (f.type) {
        case QType.text:
        case QType.multiline:
        case QType.number:
          _controllers[f.key] = TextEditingController(text: f.initial?.toString() ?? '');
        case QType.dropdown:
          _values[f.key] = f.initial as String?;
        case QType.date:
          _values[f.key] = f.initial as DateTime?;
        case QType.time:
          _values[f.key] = f.initial as TimeOfDay?;
        case QType.toggle:
          _values[f.key] = (f.initial as bool?) ?? false;
      }
    }
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    _err.clear();
    final out = <String, dynamic>{};
    for (final f in widget.fields) {
      final c = _controllers[f.key];
      final dynamic v = c != null ? c.text.trim() : _values[f.key];
      final empty = v == null || (v is String && v.isEmpty);
      if (f.required && empty) _err.local[f.key] = 'This field is required';
      if (f.type == QType.number && !empty && num.tryParse(v as String) == null) _err.local[f.key] = 'Enter a number';
      out[f.key] = v;
    }
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    setState(() => busy = true);
    try {
      await widget.onSubmit(out);
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      _err.server = e;
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget _field(QField f) {
    switch (f.type) {
      case QType.text:
      case QType.multiline:
      case QType.number:
        return AppTextField(
          controller: _controllers[f.key]!,
          label: f.label,
          required: f.required,
          error: _err.of(f.key),
          helper: f.helper,
          maxLines: f.type == QType.multiline ? 3 : 1,
          keyboard: f.type == QType.number ? const TextInputType.numberWithOptions(decimal: true) : null,
        );
      case QType.dropdown:
        return AppDropdown<String>(
          label: f.required ? '${f.label} *' : f.label,
          value: _values[f.key] as String?,
          errorText: _err.of(f.key),
          allowClear: f.clearable,
          hint: f.clearable ? 'None' : null,
          items: f.options.map((o) => DropdownMenuItem<String>(value: o.key, child: Text(o.value))).toList(),
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case QType.date:
        return DateField(
          label: f.required ? '${f.label} *' : f.label,
          value: _values[f.key] as DateTime?,
          errorText: _err.of(f.key),
          clearable: f.clearable,
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case QType.time:
        return TimeField(
          label: f.required ? '${f.label} *' : f.label,
          value: _values[f.key] as TimeOfDay?,
          errorText: _err.of(f.key),
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case QType.toggle:
        return SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(f.label),
          subtitle: f.helper == null ? null : Text(f.helper!),
          value: _values[f.key] as bool,
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
    }
  }

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        ErrorBanner(_err.general),
        if (widget.intro != null) Padding(padding: const EdgeInsets.only(bottom: 14), child: Text(widget.intro!)),
        for (final f in widget.fields) ...[_field(f), kGap],
        DialogActions(busy: busy, onSave: _submit, saveLabel: widget.submitLabel, destructive: widget.destructive),
      ]);
}
