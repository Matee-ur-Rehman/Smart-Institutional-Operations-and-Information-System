import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/form_support.dart';
import '../common/paged_list.dart';
import '../users/users_page.dart' show ResetPasswordForm;

class TeacherRow {
  TeacherRow(this.json);
  final Map<String, dynamic> json;

  String get id => asStr(json['id']);
  String get userId => asStr(json['user_id']);
  String get loginId => asStr(json['login_id']);
  String get fullName => asStr(json['full_name']);
  String get employeeNo => asStr(json['employee_no']);
  String? get email => asStrN(json['email']);
  String? get phone => asStrN(json['phone']);
  String? get qualification => asStrN(json['qualification']);
  DateTime? get joiningDate => asDateN(json['joining_date']);
  bool get isActive => asBool(json['is_active'], true);
  List<Map<String, dynamic>> get assignments => asMapList(json['assignments']);
  List<Map<String, dynamic>> get classTeacherOf => asMapList(json['class_teacher_of']);
}

/// Admin: teacher accounts, profiles and (read-only here) their current teaching load.
/// Teaching assignments are managed in "Academics".
class TeachersPage extends StatefulWidget {
  const TeachersPage({super.key});

  @override
  State<TeachersPage> createState() => _TeachersPageState();
}

class _TeachersPageState extends State<TeachersPage> {
  String _q = '';
  String? _active;
  int _reload = 0;

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Teachers',
      subtitle: 'Staff accounts and teaching load',
      actions: [
        FilledButton.icon(
          onPressed: () async {
            final ok = await showAppDialog<bool>(context, title: 'New teacher', width: 600, builder: (_) => const TeacherForm());
            if (ok == true) setState(() => _reload++);
          },
          icon: const Icon(Icons.person_add_alt_1),
          label: const Text('New teacher'),
        ),
      ],
      child: Column(children: [
        FilterBar(children: [
          SearchBox(hint: 'Name, employee no. or login', onChanged: (v) => setState(() => _q = v)),
          AppDropdown<String>(
            label: 'Status',
            value: _active,
            allowClear: true,
            items: const [DropdownMenuItem(value: 'true', child: Text('Active')), DropdownMenuItem(value: 'false', child: Text('Inactive'))],
            onChanged: (v) => setState(() => _active = v),
          ),
        ]),
        Expanded(
          child: PagedList<TeacherRow>(
            path: '/teachers',
            query: {'q': _q, 'is_active': _active},
            reloadKey: _reload,
            parse: TeacherRow.new,
            emptyTitle: 'No teachers found',
            emptyIcon: Icons.badge_outlined,
            itemBuilder: (context, t, reload) => AppCard(
              onTap: () async {
                await showAppDialog<void>(context, title: t.fullName, width: 640, builder: (_) => TeacherDetail(teacherId: t.id));
                await reload();
              },
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(children: [
                CircleAvatar(backgroundColor: Brand.primary.withValues(alpha: 0.12), child: const Icon(Icons.badge_outlined, color: Brand.primaryDark)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(t.fullName, style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text('${t.employeeNo} · ${t.qualification ?? 'Qualification not set'}', style: const TextStyle(color: Brand.muted, fontSize: 12.5), overflow: TextOverflow.ellipsis),
                  ]),
                ),
                if (!t.isActive) const StatusChip('inactive', color: Brand.danger),
                const Icon(Icons.chevron_right, color: Brand.muted),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

class TeacherDetail extends StatefulWidget {
  const TeacherDetail({super.key, required this.teacherId});
  final String teacherId;

  @override
  State<TeacherDetail> createState() => _TeacherDetailState();
}

class _TeacherDetailState extends State<TeacherDetail> {
  late Future<TeacherRow> _future = _load();

  Future<TeacherRow> _load() async => TeacherRow(asMap(await context.read<ApiClient>().get('/teachers/${widget.teacherId}')));

  void _refresh() => setState(() { _future = _load(); });

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<TeacherRow>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const SizedBox(height: 160, child: LoadingView());
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _refresh);
        final t = snap.data!;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 8, children: [
            StatusChip(t.isActive ? 'active' : 'inactive', color: t.isActive ? Brand.success : Brand.danger),
            StatusChip('login: ${t.loginId}', color: Brand.info),
          ]),
          const SizedBox(height: 8),
          InfoRow('Employee no.', t.employeeNo),
          InfoRow('Email', t.email ?? '—'),
          InfoRow('Phone', t.phone ?? '—'),
          InfoRow('Qualification', t.qualification ?? '—'),
          InfoRow('Joined', formatDate(t.joiningDate)),
          if (t.classTeacherOf.isNotEmpty) InfoRow('Class teacher of', t.classTeacherOf.map((c) => asStr(c['section_label'])).join(', ')),
          const SectionTitle('Teaching this year'),
          if (t.assignments.isEmpty) const Text('No class or subject assigned yet (see Academics → Teaching).', style: TextStyle(color: Brand.muted)),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final a in t.assignments) Chip(label: Text('${asStr(a['section_label'])} · ${asStr(a['subject_name'])}')),
          ]),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton.icon(
              onPressed: () async {
                final ok = await showAppDialog<bool>(context, title: 'Edit teacher', width: 600, builder: (_) => TeacherForm(teacher: t));
                if (ok == true) _refresh();
              },
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Edit'),
            ),
            OutlinedButton.icon(
              onPressed: () => showAppDialog<bool>(context, title: 'Reset password', builder: (_) => ResetPasswordForm(userId: t.userId, loginId: t.loginId, fullName: t.fullName)),
              icon: const Icon(Icons.lock_reset),
              label: const Text('Reset password'),
            ),
          ]),
        ]);
      },
    );
  }
}

class TeacherForm extends StatefulWidget {
  const TeacherForm({super.key, this.teacher});

  /// Null = create.
  final TeacherRow? teacher;

  @override
  State<TeacherForm> createState() => _TeacherFormState();
}

class _TeacherFormState extends State<TeacherForm> with BusyMixin {
  late final TextEditingController _name = TextEditingController(text: widget.teacher?.fullName ?? '');
  late final TextEditingController _emp = TextEditingController(text: widget.teacher?.employeeNo ?? '');
  late final TextEditingController _email = TextEditingController(text: widget.teacher?.email ?? '');
  late final TextEditingController _phone = TextEditingController(text: widget.teacher?.phone ?? '');
  late final TextEditingController _qual = TextEditingController(text: widget.teacher?.qualification ?? '');
  final _login = TextEditingController();
  final _password = TextEditingController();
  DateTime? _joined;
  bool _active = true;
  final FormErrors _err = FormErrors();

  bool get _editing => widget.teacher != null;

  @override
  void initState() {
    super.initState();
    _joined = widget.teacher?.joiningDate;
    _active = widget.teacher?.isActive ?? true;
  }

  @override
  void dispose() {
    for (final c in [_name, _emp, _email, _phone, _qual, _login, _password]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_name.text.trim().length < 2) _err.local['full_name'] = 'Enter the full name';
    if (_emp.text.trim().isEmpty) _err.local['employee_no'] = 'Enter the employee number';
    if (_email.text.trim().isNotEmpty && !kEmailPattern.hasMatch(_email.text.trim())) _err.local['email'] = 'Enter a valid email';
    if (_phone.text.trim().isNotEmpty && !kPhonePattern.hasMatch(_phone.text.trim())) _err.local['phone'] = 'Enter a valid phone number';
    if (!_editing && _password.text.isNotEmpty && _password.text.length < 8) _err.local['password'] = 'At least 8 characters (letters and digits)';
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    final body = <String, dynamic>{
      'full_name': _name.text.trim(),
      'employee_no': _emp.text.trim(),
      'email': _email.text.trim().isEmpty ? null : _email.text.trim(),
      'phone': _phone.text.trim().isEmpty ? null : _phone.text.trim(),
      'qualification': _qual.text.trim().isEmpty ? null : _qual.text.trim(),
      'joining_date': _joined == null ? null : isoDate(_joined!),
    };
    setState(() => busy = true);
    try {
      if (_editing) {
        body['is_active'] = _active;
        await api.patch('/teachers/${widget.teacher!.id}', body: body);
        if (!mounted) return;
        showSnack(context, 'Teacher updated');
        Navigator.pop(context, true);
      } else {
        if (_login.text.trim().isNotEmpty) body['login_id'] = _login.text.trim();
        if (_password.text.isNotEmpty) body['password'] = _password.text;
        body.removeWhere((k, v) => v == null);
        final res = asMap(await api.post('/teachers', body: body));
        if (!mounted) return;
        final rootContext = Navigator.of(context, rootNavigator: true).context;
        Navigator.pop(context, true);
        if (rootContext.mounted) {
          await showCredentialsDialog(rootContext, loginId: asStr(res['login_id']), temporaryPassword: asStrN(res['temporary_password']), title: 'Teacher account created');
        }
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
  Widget build(BuildContext context) {
    final twoCol = isMedium(context);
    Widget pair(Widget a, Widget b) => twoCol
        ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: a), const SizedBox(width: 12), Expanded(child: b)])
        : Column(children: [a, kGap, b]);
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      ErrorBanner(_err.general),
      AppTextField(controller: _name, label: 'Full name', required: true, error: _err.of('full_name')),
      kGap,
      pair(
        AppTextField(controller: _emp, label: 'Employee number', required: true, error: _err.of('employee_no')),
        DateField(label: 'Joining date', value: _joined, clearable: true, lastDate: DateTime.now().add(const Duration(days: 30)), errorText: _err.of('joining_date'), onChanged: (v) => setState(() => _joined = v)),
      ),
      kGap,
      pair(
        AppTextField(controller: _email, label: 'Email', keyboard: TextInputType.emailAddress, error: _err.of('email')),
        AppTextField(controller: _phone, label: 'Phone', keyboard: TextInputType.phone, error: _err.of('phone')),
      ),
      kGap,
      AppTextField(controller: _qual, label: 'Qualification', error: _err.of('qualification')),
      if (_editing) ...[
        kGap,
        SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Active teacher'), subtitle: const Text('Inactive teachers cannot sign in or be assigned'), value: _active, onChanged: (v) => setState(() => _active = v)),
      ] else ...[
        const Divider(height: 28),
        pair(
          AppTextField(controller: _login, label: 'Login ID', error: _err.of('login_id'), helper: 'Empty = employee number'),
          AppTextField(controller: _password, label: 'Password', obscure: true, error: _err.of('password'), helper: 'Empty = temporary password'),
        ),
      ],
      DialogActions(busy: busy, onSave: _save, saveLabel: _editing ? 'Save' : 'Create account'),
    ]);
  }
}
