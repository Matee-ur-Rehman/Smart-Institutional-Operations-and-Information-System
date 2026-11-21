import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../core/api_client.dart';
import '../../core/widgets.dart';

/// Client-side + server-side validation messages for one form.
class FormErrors {
  final Map<String, String> local = <String, String>{};
  ApiException? server;

  String? of(String field) => local[field] ?? server?.errorFor(field);

  void clear() {
    local.clear();
    server = null;
  }

  bool get hasLocal => local.isNotEmpty;

  /// Message of a server error that is not tied to a field (e.g. "Login ID already taken").
  String? get general => (server != null && server!.fieldErrors.isEmpty) ? server!.message : null;
}

class AppTextField extends StatelessWidget {
  const AppTextField({
    super.key,
    required this.controller,
    required this.label,
    this.error,
    this.keyboard,
    this.obscure = false,
    this.maxLines = 1,
    this.required = false,
    this.helper,
    this.onChanged,
  });

  final TextEditingController controller;
  final String label;
  final String? error;
  final TextInputType? keyboard;
  final bool obscure;
  final int maxLines;
  final bool required;
  final String? helper;
  final ValueChanged<String>? onChanged;

  @override
  Widget build(BuildContext context) => TextField(
        controller: controller,
        keyboardType: keyboard,
        obscureText: obscure,
        maxLines: obscure ? 1 : maxLines,
        onChanged: onChanged,
        decoration: InputDecoration(labelText: required ? '$label *' : label, errorText: error, helperText: helper),
      );
}

/// Vertical spacing between form fields.
const SizedBox kGap = SizedBox(height: 14);

/// Red banner for general (non-field) errors inside a dialog.
class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.message, {super.key});
  final String? message;

  @override
  Widget build(BuildContext context) {
    if (message == null) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(color: const Color(0xFFFDE8E7), borderRadius: BorderRadius.circular(8)),
        child: Text(message!, style: const TextStyle(color: Color(0xFFB91C1C))),
      ),
    );
  }
}

/// Cancel / Save row for dialog forms.
class DialogActions extends StatelessWidget {
  const DialogActions({super.key, required this.busy, required this.onSave, this.saveLabel = 'Save', this.destructive = false});
  final bool busy;
  final VoidCallback onSave;
  final String saveLabel;
  final bool destructive;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20),
        child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
          TextButton(onPressed: busy ? null : () => Navigator.pop(context, false), child: const Text('Cancel')),
          const SizedBox(width: 8),
          FilledButton(
            style: destructive ? FilledButton.styleFrom(backgroundColor: const Color(0xFFB91C1C)) : null,
            onPressed: busy ? null : onSave,
            child: busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(saveLabel),
          ),
        ]),
      );
}

/// Shows a login ID and (once) its temporary password after an account was created / reset.
Future<void> showCredentialsDialog(BuildContext context, {required String loginId, String? temporaryPassword, String title = 'Account ready'}) {
  return showDialog<void>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(title),
      content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
        InfoRow('Login ID', loginId, bold: true),
        if (temporaryPassword != null) ...[
          const InfoRow('Temporary password', ''),
          SelectableText(temporaryPassword, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800, letterSpacing: 1)),
          const SizedBox(height: 12),
          const Text('This password is shown only once. Share it with the user; they must change it at their first sign-in.',
              style: TextStyle(fontSize: 12.5)),
        ] else
          const Text('The password chosen by the administrator is in effect.', style: TextStyle(fontSize: 12.5)),
      ]),
      actions: [
        if (temporaryPassword != null)
          TextButton.icon(
            onPressed: () {
              Clipboard.setData(ClipboardData(text: temporaryPassword));
              showSnack(ctx, 'Password copied');
            },
            icon: const Icon(Icons.copy, size: 18),
            label: const Text('Copy password'),
          ),
        FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Done')),
      ],
    ),
  );
}

/// Search box that reports changes after a short pause.
class SearchBox extends StatefulWidget {
  const SearchBox({super.key, required this.onChanged, this.hint = 'Search'});
  final ValueChanged<String> onChanged;
  final String hint;

  @override
  State<SearchBox> createState() => _SearchBoxState();
}

class _SearchBoxState extends State<SearchBox> {
  final Debouncer _debounce = Debouncer();
  final TextEditingController _c = TextEditingController();

  @override
  void dispose() {
    _debounce.dispose();
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
        controller: _c,
        onChanged: (v) => _debounce.run(() => widget.onChanged(v.trim())),
        decoration: InputDecoration(labelText: widget.hint, prefixIcon: const Icon(Icons.search)),
      );
}

/// Phone numbers: digits, +, -, spaces, brackets (same rule as the API).
final RegExp kPhonePattern = RegExp(r'^[0-9+\-\s()]{7,20}$');
final RegExp kEmailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
