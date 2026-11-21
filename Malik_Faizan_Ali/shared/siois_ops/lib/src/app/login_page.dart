import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/auth.dart';
import '../core/config.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({super.key});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _form = GlobalKey<FormState>();
  final _id = TextEditingController();
  final _pw = TextEditingController();
  bool _hide = true;
  String? _error;

  @override
  void dispose() {
    _id.dispose();
    _pw.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_form.currentState?.validate() ?? false)) return;
    setState(() => _error = null);
    final err = await context.read<AuthController>().login(_id.text, _pw.text);
    if (mounted && err != null) setState(() => _error = err);
  }

  Widget _brandPanel(AppConfig cfg) => Container(
        decoration: const BoxDecoration(gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Brand.primaryDark, Brand.primary])),
        padding: const EdgeInsets.all(48),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Icon(Icons.school, color: Colors.white, size: 56),
          const SizedBox(height: 20),
          const Text('Trends High School\nHassan Abdal', style: TextStyle(color: Colors.white, fontSize: 36, fontWeight: FontWeight.w800, height: 1.15)),
          const SizedBox(height: 12),
          Text('Smart Institutional Operations and Information System', style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 16)),
          const SizedBox(height: 28),
          for (final line in const ['Homework, exams and results', 'Fees, timetable and calendar', 'Announcements and complaints'])
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                const Icon(Icons.check_circle, color: Brand.accent, size: 18),
                const SizedBox(width: 10),
                Text(line, style: const TextStyle(color: Colors.white, fontSize: 15)),
              ]),
            ),
        ]),
      );

  Widget _formCard(AppConfig cfg, bool busy) {
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 420),
      child: Form(
        key: _form,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (!isWide(context)) ...[
            const Icon(Icons.school, color: Brand.primary, size: 48),
            const SizedBox(height: 8),
            const Text('Trends High School', textAlign: TextAlign.center, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            const Text('Hassan Abdal', textAlign: TextAlign.center, style: TextStyle(color: Brand.muted)),
            const SizedBox(height: 28),
          ],
          Text(cfg.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          Text(cfg.isWeb ? 'Sign in with your administrator or teacher account.' : 'Sign in with your teacher, student or parent account.', style: const TextStyle(color: Brand.muted)),
          const SizedBox(height: 24),
          TextFormField(
            controller: _id,
            textInputAction: TextInputAction.next,
            autofillHints: const [AutofillHints.username],
            decoration: const InputDecoration(labelText: 'Login ID', prefixIcon: Icon(Icons.person_outline)),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Enter your login ID' : null,
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _pw,
            obscureText: _hide,
            autofillHints: const [AutofillHints.password],
            onFieldSubmitted: (_) => _submit(),
            decoration: InputDecoration(
              labelText: 'Password',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(icon: Icon(_hide ? Icons.visibility_outlined : Icons.visibility_off_outlined), onPressed: () => setState(() => _hide = !_hide)),
            ),
            validator: (v) => (v == null || v.isEmpty) ? 'Enter your password' : null,
          ),
          if (_error != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Brand.danger.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(10)),
              child: Row(children: [
                const Icon(Icons.error_outline, color: Brand.danger, size: 18),
                const SizedBox(width: 8),
                Expanded(child: Text(_error!, style: const TextStyle(color: Brand.danger))),
              ]),
            ),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: busy ? null : _submit,
            child: busy ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('Sign in'),
          ),
          if (cfg.demoLoginIds.isNotEmpty && cfg.demoPassword.isNotEmpty) ..._demo(cfg),
        ]),
      ),
    );
  }

  List<Widget> _demo(AppConfig cfg) {
    return [
      const SizedBox(height: 28),
      const Text('Demo accounts (development only)', style: TextStyle(color: Brand.muted, fontSize: 12)),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 8, children: [
        for (final e in cfg.demoLoginIds.entries)
          for (final id in e.value)
            ActionChip(
              avatar: const Icon(Icons.bolt, size: 16),
              label: Text('${e.key.label}: $id'),
              onPressed: () {
                _id.text = id;
                _pw.text = cfg.demoPassword;
              },
            ),
      ]),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final cfg = context.read<AppConfig>();
    final busy = context.watch<AuthController>().busy;
    final wide = isWide(context);
    return Scaffold(
      body: wide
          ? Row(children: [
              Expanded(flex: 5, child: _brandPanel(cfg)),
              Expanded(flex: 4, child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(32), child: _formCard(cfg, busy)))),
            ])
          : Center(child: SingleChildScrollView(padding: const EdgeInsets.all(24), child: _formCard(cfg, busy))),
    );
  }
}
