import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/form_support.dart';
import '../common/paged_list.dart';
import '../users/users_page.dart' show ResetPasswordForm;

class ParentRow {
  ParentRow(this.json);
  final Map<String, dynamic> json;

  String get id => asStr(json['id']);
  String get userId => asStr(json['user_id']);
  String get loginId => asStr(json['login_id']);
  String get fullName => asStr(json['full_name']);
  String? get email => asStrN(json['email']);
  String? get phone => asStrN(json['phone']);
  String? get cnic => asStrN(json['cnic']);
  String? get address => asStrN(json['address']);
  String? get occupation => asStrN(json['occupation']);
  bool get isActive => asBool(json['is_active'], true);
  List<Map<String, dynamic>> get children => asMapList(json['children']);
}

/// Admin: parent / guardian accounts and the children linked to them.
class ParentsPage extends StatefulWidget {
  const ParentsPage({super.key});

  @override
  State<ParentsPage> createState() => _ParentsPageState();
}

class _ParentsPageState extends State<ParentsPage> {
  String _q = '';
  int _reload = 0;

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Parents',
      subtitle: 'Guardian accounts and the children they can see',
      actions: [
        FilledButton.icon(
          onPressed: () async {
            final ok = await showAppDialog<bool>(context, title: 'New parent / guardian', width: 600, builder: (_) => const ParentForm());
            if (ok == true) setState(() => _reload++);
          },
          icon: const Icon(Icons.person_add_alt_1),
          label: const Text('New parent'),
        ),
      ],
      child: Column(children: [
        FilterBar(children: [SearchBox(hint: 'Name, phone, login or CNIC', onChanged: (v) => setState(() => _q = v))]),
        Expanded(
          child: PagedList<ParentRow>(
            path: '/parents',
            query: {'q': _q},
            reloadKey: _reload,
            parse: ParentRow.new,
            emptyTitle: 'No parents found',
            emptyIcon: Icons.family_restroom_outlined,
            itemBuilder: (context, p, reload) => AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                CircleAvatar(backgroundColor: Brand.primary.withValues(alpha: 0.12), child: const Icon(Icons.person_outline, color: Brand.primaryDark)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(p.fullName, style: const TextStyle(fontWeight: FontWeight.w700)),
                    Text('${p.phone ?? '—'} · @${p.loginId}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                    const SizedBox(height: 6),
                    Wrap(spacing: 6, runSpacing: 4, children: [
                      if (!p.isActive) const StatusChip('inactive', color: Brand.danger),
                      if (p.children.isEmpty) const StatusChip('no child linked', color: Brand.warning),
                      for (final c in p.children) StatusChip('${asStr(c['full_name'])} · ${asStr(c['section_label'])}', color: Brand.info),
                    ]),
                  ]),
                ),
                PopupMenuButton<String>(
                  tooltip: 'Actions',
                  onSelected: (v) async {
                    if (v == 'edit') {
                      final ok = await showAppDialog<bool>(context, title: 'Edit parent', width: 600, builder: (_) => ParentForm(parent: p));
                      if (ok == true) await reload();
                    } else if (v == 'reset') {
                      await showAppDialog<bool>(context, title: 'Reset password', builder: (_) => ResetPasswordForm(userId: p.userId, loginId: p.loginId, fullName: p.fullName));
                    }
                  },
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'edit', child: Text('Edit details')),
                    PopupMenuItem(value: 'reset', child: Text('Reset password')),
                  ],
                ),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

class _ChildLink {
  _ChildLink(this.student, this.relation);
  final StudentRef student;
  String relation;
}

class ParentForm extends StatefulWidget {
  const ParentForm({super.key, this.parent});

  /// Null = create.
  final ParentRow? parent;

  @override
  State<ParentForm> createState() => _ParentFormState();
}

class _ParentFormState extends State<ParentForm> with BusyMixin {
  late final TextEditingController _name = TextEditingController(text: widget.parent?.fullName ?? '');
  late final TextEditingController _phone = TextEditingController(text: widget.parent?.phone ?? '');
  late final TextEditingController _email = TextEditingController(text: widget.parent?.email ?? '');
  late final TextEditingController _cnic = TextEditingController(text: widget.parent?.cnic ?? '');
  late final TextEditingController _address = TextEditingController(text: widget.parent?.address ?? '');
  late final TextEditingController _occupation = TextEditingController(text: widget.parent?.occupation ?? '');
  final _login = TextEditingController();
  final _password = TextEditingController();
  final List<_ChildLink> _children = <_ChildLink>[];
  String _relation = 'father';
  bool _active = true;
  final FormErrors _err = FormErrors();

  bool get _editing => widget.parent != null;

  @override
  void initState() {
    super.initState();
    _active = widget.parent?.isActive ?? true;
  }

  @override
  void dispose() {
    for (final c in [_name, _phone, _email, _cnic, _address, _occupation, _login, _password]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_name.text.trim().length < 2) _err.local['full_name'] = 'Enter the full name';
    if (!kPhonePattern.hasMatch(_phone.text.trim())) _err.local['phone'] = 'Enter a valid phone number';
    if (_email.text.trim().isNotEmpty && !kEmailPattern.hasMatch(_email.text.trim())) _err.local['email'] = 'Enter a valid email';
    if (_cnic.text.trim().isNotEmpty && !RegExp(r'^\d{5}-\d{7}-\d$').hasMatch(_cnic.text.trim())) _err.local['cnic'] = 'Format: 12345-1234567-1';
    if (!_editing) {
      if (_login.text.trim().length < 3) _err.local['login_id'] = 'At least 3 characters';
      if (_password.text.isNotEmpty && _password.text.length < 8) _err.local['password'] = 'At least 8 characters (letters and digits)';
    }
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    final body = <String, dynamic>{
      'full_name': _name.text.trim(),
      'phone': _phone.text.trim(),
      'email': _email.text.trim().isEmpty ? null : _email.text.trim(),
      'cnic': _cnic.text.trim().isEmpty ? null : _cnic.text.trim(),
      'address': _address.text.trim().isEmpty ? null : _address.text.trim(),
      'occupation': _occupation.text.trim().isEmpty ? null : _occupation.text.trim(),
    };
    setState(() => busy = true);
    try {
      if (_editing) {
        body['is_active'] = _active;
        await api.patch('/parents/${widget.parent!.id}', body: body);
        if (!mounted) return;
        showSnack(context, 'Parent updated');
        Navigator.pop(context, true);
      } else {
        body['login_id'] = _login.text.trim();
        if (_password.text.isNotEmpty) body['password'] = _password.text;
        body['children'] = _children.map((c) => {'student_id': c.student.id, 'relation': c.relation}).toList();
        body.removeWhere((k, v) => v == null);
        final res = asMap(await api.post('/parents', body: body));
        if (!mounted) return;
        final rootContext = Navigator.of(context, rootNavigator: true).context;
        Navigator.pop(context, true);
        if (rootContext.mounted) {
          await showCredentialsDialog(rootContext, loginId: asStr(res['login_id']), temporaryPassword: asStrN(res['temporary_password']), title: 'Parent account created');
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
        AppTextField(controller: _phone, label: 'Phone', required: true, keyboard: TextInputType.phone, error: _err.of('phone')),
        AppTextField(controller: _email, label: 'Email', keyboard: TextInputType.emailAddress, error: _err.of('email')),
      ),
      kGap,
      pair(
        AppTextField(controller: _cnic, label: 'CNIC', error: _err.of('cnic'), helper: '12345-1234567-1'),
        AppTextField(controller: _occupation, label: 'Occupation', error: _err.of('occupation')),
      ),
      kGap,
      AppTextField(controller: _address, label: 'Address', maxLines: 2, error: _err.of('address')),
      if (_editing) ...[
        kGap,
        SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Active account'), value: _active, onChanged: (v) => setState(() => _active = v)),
      ] else ...[
        const Divider(height: 28),
        pair(
          AppTextField(controller: _login, label: 'Login ID', required: true, error: _err.of('login_id')),
          AppTextField(controller: _password, label: 'Password', obscure: true, error: _err.of('password'), helper: 'Empty = temporary password'),
        ),
        const SectionTitle('Children (optional)'),
        AppDropdown<String>(
          label: 'Relation of the next child you add',
          value: _relation,
          items: const [DropdownMenuItem(value: 'father', child: Text('Father')), DropdownMenuItem(value: 'mother', child: Text('Mother')), DropdownMenuItem(value: 'guardian', child: Text('Guardian'))],
          onChanged: (v) => setState(() => _relation = v ?? 'father'),
        ),
        kGap,
        StudentPickerField(
          key: ValueKey<int>(_children.length),
          label: 'Find a student to link',
          onSelected: (s) {
            if (_children.any((c) => c.student.id == s.id)) return;
            setState(() => _children.add(_ChildLink(s, _relation)));
          },
        ),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 4, children: [
          for (final c in _children)
            InputChip(
              label: Text('${c.student.fullName} (${humanizeRelation(c.relation)})'),
              onDeleted: () => setState(() => _children.remove(c)),
            ),
        ]),
        if (_err.of('children') != null) Text(_err.of('children')!, style: const TextStyle(color: Brand.danger, fontSize: 12.5)),
      ],
      DialogActions(busy: busy, onSave: _save, saveLabel: _editing ? 'Save' : 'Create account'),
    ]);
  }
}

String humanizeRelation(String r) => r.isEmpty ? r : r[0].toUpperCase() + r.substring(1);
