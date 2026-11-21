import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/auth.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import '../features/common/form_support.dart';

/// Shown instead of the app while the account still has an administrator-issued (temporary) password.
class ForcePasswordPage extends StatefulWidget {
  const ForcePasswordPage({super.key});
  @override
  State<ForcePasswordPage> createState() => _ForcePasswordPageState();
}

class _ForcePasswordPageState extends State<ForcePasswordPage> with BusyMixin {
  final _current = TextEditingController();
  final _new = TextEditingController();
  final _confirm = TextEditingController();
  final FormErrors _err = FormErrors();

  @override
  void dispose() {
    _current.dispose();
    _new.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    _err.clear();
    if (_current.text.isEmpty) _err.local['current_password'] = 'Enter the temporary password you were given';
    final n = _new.text;
    if (n.length < 8 || !RegExp(r'[A-Za-z]').hasMatch(n) || !RegExp(r'\d').hasMatch(n)) {
      _err.local['new_password'] = 'At least 8 characters, with a letter and a digit';
    } else if (n == _current.text) {
      _err.local['new_password'] = 'The new password must be different';
    }
    if (_confirm.text != n) _err.local['confirm'] = 'Passwords do not match';
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    final auth = context.read<AuthController>();
    final messenger = ScaffoldMessenger.of(context);
    setState(() => busy = true);
    try {
      await api.post('/auth/change-password', body: {'current_password': _current.text, 'new_password': n});
      // the server ends every session when the password changes: sign in again with the new one
      await auth.logout();
      messenger.showSnackBar(const SnackBar(content: Text('Password changed. Please sign in with your new password.')));
    } on ApiException catch (e) {
      _err.server = e;
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final auth = context.read<AuthController>();
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Icon(Icons.lock_reset, color: Brand.primary, size: 48),
              const SizedBox(height: 12),
              Text('Choose a new password', textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 6),
              const Text('Your account uses a temporary password. Set your own before you continue.', textAlign: TextAlign.center, style: TextStyle(color: Brand.muted)),
              const SizedBox(height: 24),
              ErrorBanner(_err.general),
              AppTextField(controller: _current, label: 'Temporary password', obscure: true, required: true, error: _err.of('current_password')),
              kGap,
              AppTextField(controller: _new, label: 'New password', obscure: true, required: true, error: _err.of('new_password'), helper: 'At least 8 characters, with a letter and a digit'),
              kGap,
              AppTextField(controller: _confirm, label: 'Confirm new password', obscure: true, required: true, error: _err.of('confirm')),
              const SizedBox(height: 20),
              FilledButton(onPressed: busy ? null : _submit, child: busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Change password')),
              TextButton(onPressed: busy ? null : auth.logout, child: const Text('Sign out')),
            ]),
          ),
        ),
      ),
    );
  }
}
