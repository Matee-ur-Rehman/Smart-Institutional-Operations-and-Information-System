import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/auth.dart';
import '../core/config.dart';
import '../core/lookups.dart';
import '../core/theme.dart';
import '../core/widgets.dart';
import '../features/registry.dart';
import 'force_password_page.dart';
import 'login_page.dart';
import 'shell.dart';

/// Root widget shared by web_app and mobile_app. Only [AppConfig] differs between them.
///
/// TEMPORARY STAND-IN for Member 1's app shell (login, token storage, API client, role navigation).
/// The feature screens only depend on: ApiClient, AuthController, Lookups, AppConfig (via Provider),
/// ShellController, and the widgets in core/widgets.dart — keep those names when swapping the shell.
class SiOisApp extends StatefulWidget {
  const SiOisApp({super.key, required this.config});
  final AppConfig config;

  @override
  State<SiOisApp> createState() => _SiOisAppState();
}

class _SiOisAppState extends State<SiOisApp> {
  late final TokenStore _tokens;
  late final ApiClient _api;
  late final AuthController _auth;
  late final Lookups _lookups;
  String? _pushRegisteredFor;

  @override
  void initState() {
    super.initState();
    _tokens = TokenStore();
    _api = ApiClient(baseUrl: widget.config.apiBaseUrl, platform: widget.config.platform, tokens: _tokens);
    _auth = AuthController(api: _api, tokens: _tokens, allowedRoles: widget.config.allowedRoles);
    _lookups = Lookups(_api);
    _api.onSessionExpired = () {
      _auth.forceLogout();
    };
    _auth.addListener(() {
      final u = _auth.user;
      if (u == null) {
        _lookups.clear();
        _pushRegisteredFor = null;
      } else if (!u.mustChangePassword && _pushRegisteredFor != u.id) {
        _pushRegisteredFor = u.id;
        _registerPush();
      }
    });
    _auth.restore();
  }

  /// Mobile only and only when the app wired a token provider (Firebase configured); never blocks the UI.
  Future<void> _registerPush() async {
    final provider = widget.config.pushTokenProvider;
    if (provider == null) return;
    try {
      final token = await provider();
      if (token == null || token.length < 10) return;
      await _api.post('/devices/register', body: {'token': token, 'platform': widget.config.isWeb ? 'web' : 'android'});
    } catch (_) {
      // push is optional: the in-app notification list always works
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<AppConfig>.value(value: widget.config),
        Provider<ApiClient>.value(value: _api),
        Provider<Lookups>.value(value: _lookups),
        ChangeNotifierProvider<AuthController>.value(value: _auth),
      ],
      child: MaterialApp(
        title: widget.config.title,
        debugShowCheckedModeBanner: false,
        theme: buildTheme(Brightness.light),
        home: const _Root(),
      ),
    );
  }
}

class _Root extends StatelessWidget {
  const _Root();

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthController>();
    if (auth.restoring) {
      return const Scaffold(body: LoadingView());
    }
    final user = auth.user;
    if (user == null) return const LoginPage();
    if (user.mustChangePassword) return const ForcePasswordPage();
    final entries = buildNav(user.role);
    return AppShell(key: ValueKey<String>(user.id), entries: entries, user: user, onLogout: auth.logout);
  }
}

