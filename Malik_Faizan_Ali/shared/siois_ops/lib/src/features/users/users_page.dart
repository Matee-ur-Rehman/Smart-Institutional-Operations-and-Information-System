import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/auth.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/form_support.dart';
import '../common/paged_list.dart';

class UserRow {
  UserRow(this.json);
  final Map<String, dynamic> json;

  String get id => asStr(json['id']);
  String get loginId => asStr(json['login_id']);
  String get fullName => asStr(json['full_name']);
  String get role => asStr(json['role']);
  String? get email => asStrN(json['email']);
  String? get phone => asStrN(json['phone']);
  bool get isActive => asBool(json['is_active'], true);
  bool get isLocked => asBool(json['is_locked']);
  DateTime? get lastLogin => asDateN(json['last_login_at']);
}

/// Admin: every account (admin, teacher, student, parent). Teachers / students / parents are *created* in their own
/// screens (they need a profile); here an admin can create other admins, edit contact details, reset passwords,
/// unlock and (de)activate any account.
class UsersPage extends StatefulWidget {
  const UsersPage({super.key});

  @override
  State<UsersPage> createState() => _UsersPageState();
}

class _UsersPageState extends State<UsersPage> {
  String _q = '';
  String? _role;
  String? _active; // 'true' | 'false' | null
  int _reload = 0;

  @override
  Widget build(BuildContext context) {
    final me = context.read<AuthController>().user;
    return PageFrame(
      title: 'User Accounts',
      subtitle: 'Sign-in accounts and access for everyone at the school',
      actions: [
        FilledButton.icon(
          onPressed: () async {
            final ok = await showAppDialog<bool>(context, title: 'New administrator', builder: (_) => const _AdminForm());
            if (ok == true) setState(() => _reload++);
          },
          icon: const Icon(Icons.person_add_alt_1),
          label: const Text('New admin'),
        ),
      ],
      child: Column(children: [
        FilterBar(children: [
          SearchBox(hint: 'Name, login or email', onChanged: (v) => setState(() => _q = v)),
          AppDropdown<String>(
            label: 'Role',
            value: _role,
            allowClear: true,
            items: const [
              DropdownMenuItem(value: 'admin', child: Text('Administrators')),
              DropdownMenuItem(value: 'teacher', child: Text('Teachers')),
              DropdownMenuItem(value: 'student', child: Text('Students')),
              DropdownMenuItem(value: 'parent', child: Text('Parents')),
            ],
            onChanged: (v) => setState(() => _role = v),
          ),
          AppDropdown<String>(
            label: 'Status',
            value: _active,
            allowClear: true,
            items: const [
              DropdownMenuItem(value: 'true', child: Text('Active')),
              DropdownMenuItem(value: 'false', child: Text('Inactive')),
            ],
            onChanged: (v) => setState(() => _active = v),
          ),
        ]),
        Expanded(
          child: PagedList<UserRow>(
            path: '/users',
            query: {'q': _q, 'role': _role, 'is_active': _active},
            reloadKey: _reload,
            parse: UserRow.new,
            emptyTitle: 'No accounts match',
            emptyIcon: Icons.people_outline,
            itemBuilder: (context, u, reload) => _UserCard(user: u, isMe: u.id == me?.id, onChanged: reload),
          ),
        ),
      ]),
    );
  }
}

class _UserCard extends StatelessWidget {
  const _UserCard({required this.user, required this.isMe, required this.onChanged});
  final UserRow user;
  final bool isMe;
  final Future<void> Function() onChanged;

  Future<void> _toggleActive(BuildContext context) async {
    final to = !user.isActive;
    final ok = await confirmDialog(context,
        title: to ? 'Activate account?' : 'Deactivate account?',
        message: to
            ? '${user.fullName} will be able to sign in again.'
            : '${user.fullName} will no longer be able to sign in. Their records are kept.',
        confirmLabel: to ? 'Activate' : 'Deactivate',
        destructive: !to);
    if (!ok || !context.mounted) return;
    try {
      await context.read<ApiClient>().patch('/users/${user.id}', body: {'is_active': to});
      if (context.mounted) showSnack(context, to ? 'Account activated' : 'Account deactivated');
      await onChanged();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  Future<void> _unlock(BuildContext context) async {
    try {
      await context.read<ApiClient>().post('/users/${user.id}/unlock');
      if (context.mounted) showSnack(context, 'Account unlocked');
      await onChanged();
    } catch (e) {
      if (context.mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AppCard(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      child: Row(children: [
        CircleAvatar(
          backgroundColor: Brand.primary.withValues(alpha: 0.12),
          child: Text(user.fullName.isEmpty ? '?' : user.fullName[0].toUpperCase(), style: const TextStyle(color: Brand.primaryDark, fontWeight: FontWeight.w700)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(user.fullName, style: const TextStyle(fontWeight: FontWeight.w700), overflow: TextOverflow.ellipsis),
            Text('@${user.loginId}${user.email == null ? '' : ' · ${user.email}'}', style: const TextStyle(color: Brand.muted, fontSize: 12.5), overflow: TextOverflow.ellipsis),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 4, children: [
              StatusChip(user.role, color: Brand.info),
              if (!user.isActive) const StatusChip('inactive', color: Brand.danger),
              if (user.isLocked) const StatusChip('locked', color: Brand.warning),
              if (isMe) const StatusChip('you', color: Brand.primary),
              if (user.lastLogin != null) Text('Last sign-in ${formatDateTime(user.lastLogin)}', style: const TextStyle(color: Brand.muted, fontSize: 12)),
            ]),
          ]),
        ),
        PopupMenuButton<String>(
          tooltip: 'Actions',
          onSelected: (v) async {
            switch (v) {
              case 'edit':
                final ok = await showAppDialog<bool>(context, title: 'Edit account', builder: (_) => _EditForm(user: user));
                if (ok == true) await onChanged();
              case 'reset':
                await showAppDialog<bool>(context, title: 'Reset password', builder: (_) => ResetPasswordForm(userId: user.id, loginId: user.loginId, fullName: user.fullName));
              case 'unlock':
                await _unlock(context);
              case 'active':
                await _toggleActive(context);
            }
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'edit', child: Text('Edit details')),
            const PopupMenuItem(value: 'reset', child: Text('Reset password')),
            if (user.isLocked) const PopupMenuItem(value: 'unlock', child: Text('Unlock account')),
            if (!isMe) PopupMenuItem(value: 'active', child: Text(user.isActive ? 'Deactivate' : 'Activate')),
          ],
        ),
      ]),
    );
  }
}

// ------------------------------------------------------------------ forms
class _AdminForm extends StatefulWidget {
  const _AdminForm();

  @override
  State<_AdminForm> createState() => _AdminFormState();
}

class _AdminFormState extends State<_AdminForm> with BusyMixin {
  final _name = TextEditingController();
  final _login = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final FormErrors _err = FormErrors();

  @override
  void dispose() {
    for (final c in [_name, _login, _email, _phone, _password]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_name.text.trim().length < 2) _err.local['full_name'] = 'Enter the full name';
    if (_login.text.trim().length < 3) _err.local['login_id'] = 'At least 3 characters';
    if (_email.text.trim().isNotEmpty && !kEmailPattern.hasMatch(_email.text.trim())) _err.local['email'] = 'Enter a valid email';
    if (_phone.text.trim().isNotEmpty && !kPhonePattern.hasMatch(_phone.text.trim())) _err.local['phone'] = 'Enter a valid phone number';
    if (_password.text.isNotEmpty && _password.text.length < 8) _err.local['password'] = 'At least 8 characters (letters and digits)';
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    Map<String, dynamic>? created;
    final ok = await _submit(() async {
      created = asMap(await api.post('/users', body: {
        'login_id': _login.text.trim(),
        'full_name': _name.text.trim(),
        if (_email.text.trim().isNotEmpty) 'email': _email.text.trim(),
        if (_phone.text.trim().isNotEmpty) 'phone': _phone.text.trim(),
        if (_password.text.isNotEmpty) 'password': _password.text,
      }));
    });
    if (!ok || !mounted) return;
    final temp = asStrN(created?['temporary_password']);
    // The credentials dialog is shown from the root navigator's context because this form closes first.
    final rootContext = Navigator.of(context, rootNavigator: true).context;
    Navigator.pop(context, true);
    if (rootContext.mounted) {
      await showCredentialsDialog(rootContext, loginId: _login.text.trim(), temporaryPassword: temp, title: 'Administrator created');
    }
  }

  Future<bool> _submit(Future<void> Function() action) async {
    setState(() => busy = true);
    try {
      await action();
      return true;
    } on ApiException catch (e) {
      _err.server = e;
      return false;
    } catch (e) {
      if (mounted) showError(context, e);
      return false;
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        ErrorBanner(_err.general),
        AppTextField(controller: _name, label: 'Full name', required: true, error: _err.of('full_name')),
        kGap,
        AppTextField(controller: _login, label: 'Login ID', required: true, error: _err.of('login_id'), helper: 'Letters, digits, dot, dash or underscore'),
        kGap,
        AppTextField(controller: _email, label: 'Email', keyboard: TextInputType.emailAddress, error: _err.of('email')),
        kGap,
        AppTextField(controller: _phone, label: 'Phone', keyboard: TextInputType.phone, error: _err.of('phone')),
        kGap,
        AppTextField(controller: _password, label: 'Password', obscure: true, error: _err.of('password'), helper: 'Leave empty to generate a temporary password'),
        DialogActions(busy: busy, onSave: _save, saveLabel: 'Create'),
      ]);
}

class _EditForm extends StatefulWidget {
  const _EditForm({required this.user});
  final UserRow user;

  @override
  State<_EditForm> createState() => _EditFormState();
}

class _EditFormState extends State<_EditForm> with BusyMixin {
  late final TextEditingController _name = TextEditingController(text: widget.user.fullName);
  late final TextEditingController _email = TextEditingController(text: widget.user.email ?? '');
  late final TextEditingController _phone = TextEditingController(text: widget.user.phone ?? '');
  final FormErrors _err = FormErrors();

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_name.text.trim().length < 2) _err.local['full_name'] = 'Enter the full name';
    if (_email.text.trim().isNotEmpty && !kEmailPattern.hasMatch(_email.text.trim())) _err.local['email'] = 'Enter a valid email';
    if (_phone.text.trim().isNotEmpty && !kPhonePattern.hasMatch(_phone.text.trim())) _err.local['phone'] = 'Enter a valid phone number';
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    setState(() => busy = true);
    try {
      await api.patch('/users/${widget.user.id}', body: {
        'full_name': _name.text.trim(),
        'email': _email.text.trim().isEmpty ? null : _email.text.trim(),
        'phone': _phone.text.trim().isEmpty ? null : _phone.text.trim(),
      });
      if (!mounted) return;
      showSnack(context, 'Account updated');
      Navigator.pop(context, true);
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
        InfoRow('Login ID', widget.user.loginId),
        InfoRow('Role', humanize(widget.user.role)),
        kGap,
        AppTextField(controller: _name, label: 'Full name', required: true, error: _err.of('full_name')),
        kGap,
        AppTextField(controller: _email, label: 'Email', keyboard: TextInputType.emailAddress, error: _err.of('email')),
        kGap,
        AppTextField(controller: _phone, label: 'Phone', keyboard: TextInputType.phone, error: _err.of('phone')),
        DialogActions(busy: busy, onSave: _save),
      ]);
}

/// Reset-password dialog body (also used by the Teachers and Parents screens).
class ResetPasswordForm extends StatefulWidget {
  const ResetPasswordForm({super.key, required this.userId, required this.loginId, required this.fullName});
  final String userId;
  final String loginId;
  final String fullName;

  @override
  State<ResetPasswordForm> createState() => _ResetFormState();
}

class _ResetFormState extends State<ResetPasswordForm> with BusyMixin {
  final _password = TextEditingController();
  final FormErrors _err = FormErrors();

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_password.text.isNotEmpty && _password.text.length < 8) {
      setState(() => _err.local['new_password'] = 'At least 8 characters (letters and digits)');
      return;
    }
    final api = context.read<ApiClient>();
    setState(() => busy = true);
    try {
      final res = asMap(await api.post('/users/${widget.userId}/reset-password',
          body: _password.text.isEmpty ? <String, dynamic>{} : {'new_password': _password.text}));
      if (!mounted) return;
      final temp = asStrN(res['temporary_password']);
      final rootContext = Navigator.of(context, rootNavigator: true).context;
      Navigator.pop(context, true);
      if (rootContext.mounted) {
        await showCredentialsDialog(rootContext, loginId: widget.loginId, temporaryPassword: temp, title: 'Password reset');
      }
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
        Text('Reset the password of ${widget.fullName} (@${widget.loginId}). They will be signed out everywhere and must choose a new password at the next sign-in.'),
        kGap,
        AppTextField(controller: _password, label: 'New password', obscure: true, error: _err.of('new_password'), helper: 'Leave empty to generate a temporary password'),
        DialogActions(busy: busy, onSave: _save, saveLabel: 'Reset password'),
      ]);
}
