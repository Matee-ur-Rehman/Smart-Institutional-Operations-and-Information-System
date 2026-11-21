import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/auth.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/form_support.dart';
import '../common/quick_form.dart';

/// Own account: view details, edit e-mail / phone, change password.
class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  Future<void> _editContact(BuildContext context, AppUser u) async {
    final api = context.read<ApiClient>();
    final auth = context.read<AuthController>();
    final ok = await showAppDialog<bool>(
      context,
      title: 'Edit contact details',
      builder: (_) => QuickForm(
        intro: 'Your name and login ID can only be changed by the school office.',
        fields: [
          QField('email', 'Email', QType.text, initial: u.email, helper: 'Optional'),
          QField('phone', 'Phone', QType.text, initial: u.phone, helper: 'Optional, e.g. 0300-1234567'),
        ],
        onSubmit: (v) async {
          final email = (v['email'] as String).trim();
          final phone = (v['phone'] as String).trim();
          if (email.isNotEmpty && !kEmailPattern.hasMatch(email)) {
            throw ApiException(422, 'validation_error', 'Please correct the highlighted field', fieldErrors: const [FieldError('email', 'Enter a valid email address')]);
          }
          if (phone.isNotEmpty && !kPhonePattern.hasMatch(phone)) {
            throw ApiException(422, 'validation_error', 'Please correct the highlighted field', fieldErrors: const [FieldError('phone', 'Enter a valid phone number')]);
          }
          await api.patch('/auth/me', body: {'email': email.isEmpty ? null : email, 'phone': phone.isEmpty ? null : phone});
          await auth.refreshUser();
        },
      ),
    );
    if (ok == true && context.mounted) showSnack(context, 'Profile updated');
  }

  Future<void> _changePassword(BuildContext context) async {
    final api = context.read<ApiClient>();
    final auth = context.read<AuthController>();
    // capture before the dialog closes: the account screen is replaced by the login screen afterwards
    final messenger = ScaffoldMessenger.maybeOf(context);
    final ok = await showAppDialog<bool>(
      context,
      title: 'Change password',
      builder: (_) => _PasswordForm(api: api),
    );
    if (ok == true) {
      // the server ends every session when the password changes, so sign in again with the new one
      await auth.logout();
      messenger?.showSnackBar(const SnackBar(content: Text('Password changed. Please sign in again.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final u = context.watch<AuthController>().user;
    if (u == null) return const SizedBox.shrink();
    return PageFrame(
      title: 'My profile',
      maxWidth: 720,
      child: ListView(children: [
        AppCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              CircleAvatar(radius: 28, backgroundColor: Brand.primary, child: Text(u.initials, style: const TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.w700))),
              const SizedBox(width: 14),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(u.fullName, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  StatusChip(u.role.name, color: Brand.primary),
                ]),
              ),
            ]),
            const SizedBox(height: 16),
            InfoRow('Login ID', u.loginId),
            InfoRow('Email', (u.email ?? '').isEmpty ? '—' : u.email!),
            InfoRow('Phone', (u.phone ?? '').isEmpty ? '—' : u.phone!),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              OutlinedButton.icon(onPressed: () => _editContact(context, u), icon: const Icon(Icons.edit_outlined, size: 18), label: const Text('Edit contact details')),
              OutlinedButton.icon(onPressed: () => _changePassword(context), icon: const Icon(Icons.lock_reset, size: 18), label: const Text('Change password')),
            ]),
          ]),
        ),
        const SizedBox(height: 12),
        AppCard(
          child: Row(children: [
            const Icon(Icons.logout, color: Brand.danger),
            const SizedBox(width: 12),
            const Expanded(child: Text('Sign out of this device')),
            TextButton(
              onPressed: () => context.read<AuthController>().logout(),
              style: TextButton.styleFrom(foregroundColor: Brand.danger),
              child: const Text('Sign out'),
            ),
          ]),
        ),
      ]),
    );
  }
}

class _PasswordForm extends StatefulWidget {
  const _PasswordForm({required this.api});
  final ApiClient api;
  @override
  State<_PasswordForm> createState() => _PasswordFormState();
}

class _PasswordFormState extends State<_PasswordForm> with BusyMixin {
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
    if (_current.text.isEmpty) _err.local['current_password'] = 'Enter your current password';
    final n = _new.text;
    if (n.length < 8 || !RegExp(r'[A-Za-z]').hasMatch(n) || !RegExp(r'\d').hasMatch(n)) {
      _err.local['new_password'] = 'At least 8 characters, with a letter and a digit';
    }
    if (_confirm.text != n) _err.local['confirm'] = 'Passwords do not match';
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    setState(() => busy = true);
    try {
      await widget.api.post('/auth/change-password', body: {'current_password': _current.text, 'new_password': n});
      if (mounted) Navigator.pop(context, true);
    } on ApiException catch (e) {
      _err.server = e;
    } catch (e) {
      if (mounted) showError(context, e);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        ErrorBanner(_err.general),
        AppTextField(controller: _current, label: 'Current password', obscure: true, required: true, error: _err.of('current_password')),
        kGap,
        AppTextField(controller: _new, label: 'New password', obscure: true, required: true, error: _err.of('new_password'), helper: 'At least 8 characters, with a letter and a digit'),
        kGap,
        AppTextField(controller: _confirm, label: 'Confirm new password', obscure: true, required: true, error: _err.of('confirm')),
        kGap,
        DialogActions(busy: busy, onSave: _submit, saveLabel: 'Change password'),
      ]);
}
