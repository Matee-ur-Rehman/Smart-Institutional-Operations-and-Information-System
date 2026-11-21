import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/lookups.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/form_support.dart';
import '../common/paged_list.dart';
import '../common/report_download.dart';

class StudentRow {
  StudentRow(this.json);
  final Map<String, dynamic> json;

  String get id => asStr(json['id']);
  String get fullName => asStr(json['full_name']);
  String get rollNo => asStr(json['roll_no']);
  String get sectionId => asStr(json['section_id']);
  String get sectionLabel => asStr(json['section_label'], '—');
  String? get loginId => asStrN(json['login_id']);
  bool get isActive => asBool(json['is_active'], true);
  String? get gender => asStrN(json['gender']);
  DateTime? get dateOfBirth => asDateN(json['date_of_birth']);
  DateTime? get admissionDate => asDateN(json['admission_date']);
  String? get address => asStrN(json['address']);
  List<Map<String, dynamic>> get parents => asMapList(json['parents']);
}

/// Students. Admin: full management. Teacher ([readOnly]): the students of the sections they teach.
class StudentsPage extends StatefulWidget {
  const StudentsPage({super.key, required this.readOnly});
  final bool readOnly;

  @override
  State<StudentsPage> createState() => _StudentsPageState();
}

class _StudentsPageState extends State<StudentsPage> {
  String _q = '';
  String? _sectionId;
  String? _active;
  int _reload = 0;
  late final Future<List<SectionRef>> _sections = context.read<Lookups>().sections(all: !widget.readOnly);

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: widget.readOnly ? 'My Students' : 'Students',
      subtitle: widget.readOnly ? 'Students of the classes you teach' : 'Admissions, class placement and family links',
      actions: [
        if (!widget.readOnly)
          FilledButton.icon(
            onPressed: () async {
              final ok = await showAppDialog<bool>(context, title: 'Admit a student', builder: (_) => const StudentForm());
              if (ok == true) setState(() => _reload++);
            },
            icon: const Icon(Icons.person_add_alt_1),
            label: const Text('New student'),
          ),
        if (!widget.readOnly)
          ReportButton(label: 'Export CSV', path: '/reports/students', query: {'section_id': _sectionId}, icon: Icons.table_view_outlined, fallbackName: 'students.csv'),
      ],
      child: Column(children: [
        FilterBar(children: [
          SearchBox(hint: 'Name or roll number', onChanged: (v) => setState(() => _q = v)),
          FutureBuilder<List<SectionRef>>(
            future: _sections,
            builder: (context, snap) => AppDropdown<String>(
              label: 'Class / section',
              value: _sectionId,
              allowClear: true,
              items: (snap.data ?? <SectionRef>[]).map((s) => DropdownMenuItem(value: s.id, child: Text(s.label))).toList(),
              onChanged: (v) => setState(() => _sectionId = v),
            ),
          ),
          if (!widget.readOnly)
            AppDropdown<String>(
              label: 'Status',
              value: _active,
              allowClear: true,
              items: const [DropdownMenuItem(value: 'true', child: Text('Active')), DropdownMenuItem(value: 'false', child: Text('Inactive'))],
              onChanged: (v) => setState(() => _active = v),
            ),
        ]),
        Expanded(
          child: PagedList<StudentRow>(
            path: '/students',
            query: {'q': _q, 'section_id': _sectionId, 'is_active': _active},
            reloadKey: _reload,
            parse: StudentRow.new,
            emptyTitle: 'No students found',
            emptyIcon: Icons.school_outlined,
            itemBuilder: (context, s, reload) => AppCard(
              onTap: () async {
                await showAppDialog<void>(context, title: s.fullName, width: 640, builder: (_) => StudentDetail(studentId: s.id, readOnly: widget.readOnly));
                await reload();
              },
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(children: [
                CircleAvatar(
                  backgroundColor: Brand.primary.withValues(alpha: 0.12),
                  child: Text(s.rollNo.length > 3 ? s.rollNo.substring(s.rollNo.length - 3) : s.rollNo, style: const TextStyle(color: Brand.primaryDark, fontSize: 12, fontWeight: FontWeight.w700)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(s.fullName, style: const TextStyle(fontWeight: FontWeight.w700), overflow: TextOverflow.ellipsis),
                    Text('${s.rollNo} · ${s.sectionLabel}', style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
                  ]),
                ),
                if (!s.isActive) const StatusChip('inactive', color: Brand.danger),
                if (!widget.readOnly && s.loginId == null) const Padding(padding: EdgeInsets.only(left: 6), child: StatusChip('no login', color: Brand.warning)),
                const Icon(Icons.chevron_right, color: Brand.muted),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}

// ------------------------------------------------------------------ create / edit form
class StudentForm extends StatefulWidget {
  const StudentForm({super.key, this.student});

  /// Null = create.
  final StudentRow? student;

  @override
  State<StudentForm> createState() => _StudentFormState();
}

class _StudentFormState extends State<StudentForm> with BusyMixin {
  late final TextEditingController _name = TextEditingController(text: widget.student?.fullName ?? '');
  late final TextEditingController _roll = TextEditingController(text: widget.student?.rollNo ?? '');
  late final TextEditingController _address = TextEditingController(text: widget.student?.address ?? '');
  final _login = TextEditingController();
  final _password = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  String? _sectionId;
  String? _gender;
  DateTime? _dob;
  DateTime? _admission;
  bool _createLogin = true;
  bool _active = true;
  List<SectionRef> _sections = <SectionRef>[];
  final FormErrors _err = FormErrors();

  bool get _editing => widget.student != null;

  @override
  void initState() {
    super.initState();
    final s = widget.student;
    if (s != null) {
      _sectionId = s.sectionId;
      _gender = s.gender;
      _dob = s.dateOfBirth;
      _admission = s.admissionDate;
      _active = s.isActive;
    }
    context.read<Lookups>().sections(all: true).then((v) {
      if (mounted) setState(() => _sections = v);
    }).catchError((Object e) {
      if (mounted) showError(context, e);
    });
  }

  @override
  void dispose() {
    for (final c in [_name, _roll, _address, _login, _password, _email, _phone]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    _err.clear();
    if (_name.text.trim().length < 2) _err.local['full_name'] = 'Enter the full name';
    if (_roll.text.trim().isEmpty) _err.local['roll_no'] = 'Enter a roll number';
    if (_sectionId == null) _err.local['section_id'] = 'Choose a class / section';
    if (!_editing) {
      if (_email.text.trim().isNotEmpty && !kEmailPattern.hasMatch(_email.text.trim())) _err.local['email'] = 'Enter a valid email';
      if (_phone.text.trim().isNotEmpty && !kPhonePattern.hasMatch(_phone.text.trim())) _err.local['phone'] = 'Enter a valid phone number';
      if (_password.text.isNotEmpty && _password.text.length < 8) _err.local['password'] = 'At least 8 characters (letters and digits)';
    }
    if (_err.hasLocal) {
      setState(() {});
      return;
    }
    final api = context.read<ApiClient>();
    final body = <String, dynamic>{
      'full_name': _name.text.trim(),
      'roll_no': _roll.text.trim(),
      'section_id': _sectionId,
      'gender': _gender,
      'date_of_birth': _dob == null ? null : isoDate(_dob!),
      'admission_date': _admission == null ? null : isoDate(_admission!),
      'address': _address.text.trim().isEmpty ? null : _address.text.trim(),
    };
    setState(() => busy = true);
    try {
      if (_editing) {
        body['is_active'] = _active;
        await api.patch('/students/${widget.student!.id}', body: body);
        if (!mounted) return;
        showSnack(context, 'Student updated');
        Navigator.pop(context, true);
      } else {
        body['create_login'] = _createLogin;
        if (_createLogin && _login.text.trim().isNotEmpty) body['login_id'] = _login.text.trim();
        if (_createLogin && _password.text.isNotEmpty) body['password'] = _password.text;
        if (_email.text.trim().isNotEmpty) body['email'] = _email.text.trim();
        if (_phone.text.trim().isNotEmpty) body['phone'] = _phone.text.trim();
        body.removeWhere((k, v) => v == null);
        final res = asMap(await api.post('/students', body: body));
        if (!mounted) return;
        final rootContext = Navigator.of(context, rootNavigator: true).context;
        Navigator.pop(context, true);
        final loginId = asStrN(res['login_id']);
        if (loginId != null && rootContext.mounted) {
          await showCredentialsDialog(rootContext, loginId: loginId, temporaryPassword: asStrN(res['temporary_password']), title: 'Student admitted');
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
        AppTextField(controller: _roll, label: 'Roll number', required: true, error: _err.of('roll_no')),
        AppDropdown<String>(
          label: 'Class / section *',
          value: _sectionId,
          errorText: _err.of('section_id'),
          items: _sections.map((s) => DropdownMenuItem(value: s.id, child: Text(s.label))).toList(),
          onChanged: (v) => setState(() => _sectionId = v),
        ),
      ),
      kGap,
      pair(
        AppDropdown<String>(
          label: 'Gender',
          value: _gender,
          allowClear: true,
          hint: 'Not specified',
          items: const [DropdownMenuItem(value: 'male', child: Text('Male')), DropdownMenuItem(value: 'female', child: Text('Female')), DropdownMenuItem(value: 'other', child: Text('Other'))],
          onChanged: (v) => setState(() => _gender = v),
        ),
        DateField(label: 'Date of birth', value: _dob, clearable: true, firstDate: DateTime(1995), lastDate: DateTime.now(), errorText: _err.of('date_of_birth'), onChanged: (v) => setState(() => _dob = v)),
      ),
      kGap,
      DateField(label: 'Admission date', value: _admission, clearable: true, lastDate: DateTime.now().add(const Duration(days: 30)), errorText: _err.of('admission_date'), onChanged: (v) => setState(() => _admission = v)),
      kGap,
      AppTextField(controller: _address, label: 'Address', maxLines: 2, error: _err.of('address')),
      if (_editing) ...[
        kGap,
        SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Active student'), subtitle: const Text('Inactive students are hidden from class lists'), value: _active, onChanged: (v) => setState(() => _active = v)),
      ] else ...[
        const Divider(height: 28),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Create a student login'),
          subtitle: const Text('Lets the student sign in on the mobile app'),
          value: _createLogin,
          onChanged: (v) => setState(() => _createLogin = v),
        ),
        if (_createLogin) ...[
          pair(
            AppTextField(controller: _login, label: 'Login ID', error: _err.of('login_id'), helper: 'Empty = roll number'),
            AppTextField(controller: _password, label: 'Password', obscure: true, error: _err.of('password'), helper: 'Empty = temporary password'),
          ),
          kGap,
          pair(
            AppTextField(controller: _email, label: 'Email', keyboard: TextInputType.emailAddress, error: _err.of('email')),
            AppTextField(controller: _phone, label: 'Phone', keyboard: TextInputType.phone, error: _err.of('phone')),
          ),
        ],
      ],
      DialogActions(busy: busy, onSave: _save, saveLabel: _editing ? 'Save' : 'Admit student'),
    ]);
  }
}

// ------------------------------------------------------------------ detail (profile + family links)
class StudentDetail extends StatefulWidget {
  const StudentDetail({super.key, required this.studentId, required this.readOnly});
  final String studentId;
  final bool readOnly;

  @override
  State<StudentDetail> createState() => _StudentDetailState();
}

class _StudentDetailState extends State<StudentDetail> {
  late Future<StudentRow> _future = _load();

  Future<StudentRow> _load() async => StudentRow(asMap(await context.read<ApiClient>().get('/students/${widget.studentId}')));

  void _refresh() => setState(() { _future = _load(); });

  Future<void> _createLogin(StudentRow s) async {
    try {
      final res = asMap(await context.read<ApiClient>().post('/students/${s.id}/login', body: <String, dynamic>{}));
      _refresh();
      if (!mounted) return;
      await showCredentialsDialog(context, loginId: asStr(res['login_id']), temporaryPassword: asStrN(res['temporary_password']), title: 'Login created');
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _unlink(StudentRow s, Map<String, dynamic> p) async {
    final ok = await confirmDialog(context, title: 'Remove link?', message: '${asStr(p['full_name'])} will no longer see ${s.fullName}.', confirmLabel: 'Remove', destructive: true);
    if (!ok || !mounted) return;
    try {
      await context.read<ApiClient>().delete('/students/${s.id}/parents/${asStr(p['parent_id'])}');
      _refresh();
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<StudentRow>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const SizedBox(height: 160, child: LoadingView());
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _refresh);
        final s = snap.data!;
        return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Wrap(spacing: 8, runSpacing: 4, children: [
            StatusChip(s.isActive ? 'active' : 'inactive', color: s.isActive ? Brand.success : Brand.danger),
            if (s.loginId != null) StatusChip('login: ${s.loginId}', color: Brand.info),
          ]),
          const SizedBox(height: 8),
          InfoRow('Roll number', s.rollNo),
          InfoRow('Class / section', s.sectionLabel),
          InfoRow('Gender', s.gender == null ? '—' : humanize(s.gender!)),
          InfoRow('Date of birth', formatDate(s.dateOfBirth)),
          InfoRow('Admission date', formatDate(s.admissionDate)),
          InfoRow('Address', s.address ?? '—'),
          const SectionTitle('Parents / guardians'),
          if (s.parents.isEmpty) const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('No parent is linked yet.', style: TextStyle(color: Brand.muted))),
          for (final p in s.parents)
            ListTile(
              contentPadding: EdgeInsets.zero,
              dense: true,
              leading: const Icon(Icons.family_restroom_outlined),
              title: Text(asStr(p['full_name'])),
              subtitle: Text('${humanize(asStr(p['relation']))}${p['phone'] == null ? '' : ' · ${asStr(p['phone'])}'}'),
              trailing: widget.readOnly ? null : IconButton(tooltip: 'Remove link', icon: const Icon(Icons.link_off), onPressed: () => _unlink(s, p)),
            ),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 8, children: [
            if (!widget.readOnly)
              OutlinedButton.icon(
                onPressed: () async {
                  final ok = await showAppDialog<bool>(context, title: 'Link a parent', builder: (_) => _LinkParentForm(studentId: s.id));
                  if (ok == true) _refresh();
                },
                icon: const Icon(Icons.add_link),
                label: const Text('Link parent'),
              ),
            if (!widget.readOnly)
              OutlinedButton.icon(
                onPressed: () async {
                  final ok = await showAppDialog<bool>(context, title: 'Edit student', builder: (_) => StudentForm(student: s));
                  if (ok == true) _refresh();
                },
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Edit'),
              ),
            if (!widget.readOnly && s.loginId == null)
              OutlinedButton.icon(onPressed: () => _createLogin(s), icon: const Icon(Icons.key_outlined), label: const Text('Create login')),
            ReportButton(label: 'Attendance PDF', path: '/reports/attendance/students/${s.id}', fallbackName: 'attendance.pdf'),
            if (!widget.readOnly) ReportButton(label: 'Fee statement', path: '/reports/fee-statement/${s.id}', fallbackName: 'fee_statement.pdf'),
          ]),
        ]);
      },
    );
  }
}

class _LinkParentForm extends StatefulWidget {
  const _LinkParentForm({required this.studentId});
  final String studentId;

  @override
  State<_LinkParentForm> createState() => _LinkParentFormState();
}

class _LinkParentFormState extends State<_LinkParentForm> with BusyMixin {
  final Debouncer _debounce = Debouncer();
  List<Map<String, dynamic>> _results = <Map<String, dynamic>>[];
  bool _searching = false;
  String _relation = 'guardian';
  Object? _error;

  @override
  void dispose() {
    _debounce.dispose();
    super.dispose();
  }

  void _search(String q) {
    _debounce.run(() async {
      if (q.trim().length < 2) {
        if (mounted) setState(() => _results = <Map<String, dynamic>>[]);
        return;
      }
      setState(() => _searching = true);
      try {
        final res = asMap(await context.read<ApiClient>().get('/parents', query: {'q': q.trim(), 'page_size': 10}));
        if (mounted) {
          setState(() {
            _results = asMapList(res['items']);
            _error = null;
          });
        }
      } catch (e) {
        if (mounted) setState(() => _error = e);
      } finally {
        if (mounted) setState(() => _searching = false);
      }
    });
  }

  Future<void> _link(Map<String, dynamic> p) async {
    final api = context.read<ApiClient>();
    final ok = await runBusy(() async {
      await api.post('/students/${widget.studentId}/parents', body: {'parent_id': asStr(p['id']), 'relation': _relation});
    }, success: 'Parent linked');
    if (ok && mounted) Navigator.pop(context, true);
  }

  @override
  Widget build(BuildContext context) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        AppDropdown<String>(
          label: 'Relation',
          value: _relation,
          items: const [DropdownMenuItem(value: 'father', child: Text('Father')), DropdownMenuItem(value: 'mother', child: Text('Mother')), DropdownMenuItem(value: 'guardian', child: Text('Guardian'))],
          onChanged: (v) => setState(() => _relation = v ?? 'guardian'),
        ),
        kGap,
        TextField(onChanged: _search, decoration: const InputDecoration(labelText: 'Search parent by name, phone, login or CNIC', prefixIcon: Icon(Icons.search))),
        const SizedBox(height: 8),
        if (_searching) const LinearProgressIndicator(),
        if (_error != null) Text(errorMessage(_error!), style: const TextStyle(color: Brand.danger)),
        for (final p in _results)
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.person_outline),
            title: Text(asStr(p['full_name'])),
            subtitle: Text('${asStr(p['phone'])} · @${asStr(p['login_id'])}'),
            trailing: FilledButton(onPressed: busy ? null : () => _link(p), child: const Text('Link')),
          ),
        if (_results.isEmpty && !_searching) const Padding(padding: EdgeInsets.only(top: 8), child: Text('Type at least 2 characters. New parents are created in the Parents screen.', style: TextStyle(color: Brand.muted, fontSize: 12.5))),
      ]);
}
