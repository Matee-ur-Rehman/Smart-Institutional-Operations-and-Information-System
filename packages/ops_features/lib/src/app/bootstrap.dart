import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../ui/ui.dart';
import 'login_screen.dart';

/// Wires up everything both apps share: token storage, the API client, login state, the
/// theme and the sign-in gate.
///
///   runApp(OpsApp(
///     title: 'Trends High School',
///     platform: 'web',                          // or 'mobile'
///     allowedRoles: {'admin', 'teacher'},
///     homeForRole: (context, user) => ...,      // the dashboard for user.role
///   ));
///
/// Signing in or out replaces the whole navigator, so no screen from a previous session can
/// stay on top of the login page.
class OpsApp extends StatefulWidget {
  const OpsApp({
    super.key,
    required this.title,
    required this.platform,
    required this.allowedRoles,
    required this.homeForRole,
    this.tokenStore,
  });

  final String title;

  /// 'web' or 'mobile': sent to the server in `X-Client-Platform`.
  final String platform;
  final Set<String> allowedRoles;
  final Widget Function(BuildContext context, AuthUser user) homeForRole;

  /// Tests pass a MemoryTokenStore; the real apps use the secure store.
  final TokenStore? tokenStore;

  @override
  State<OpsApp> createState() => _OpsAppState();
}

class _OpsAppState extends State<OpsApp> {
  late final TokenStore _tokens;
  late final ApiClient _client;
  late final AuthState _auth;
  late final OpsApi _api;

  @override
  void initState() {
    super.initState();
    _tokens = widget.tokenStore ?? SecureTokenStore();
    _client = ApiClient(platform: widget.platform, tokens: _tokens);
    _auth = AuthState(client: _client, tokens: _tokens, allowedRoles: widget.allowedRoles);
    _api = OpsApi(_client);
    _auth.restore();
  }

  @override
  void dispose() {
    _auth.dispose();
    super.dispose();
  }

  Widget _home(BuildContext context, AuthState auth) {
    switch (auth.status) {
      case AuthStatus.unknown:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));
      case AuthStatus.signedOut:
        return LoginScreen(
          title: widget.title,
          subtitle: widget.platform == 'web' ? 'Administration and teacher portal' : 'Sign in to continue',
        );
      case AuthStatus.signedIn:
        return widget.homeForRole(context, auth.user!);
    }
  }

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: _client),
        ChangeNotifierProvider<AuthState>.value(value: _auth),
        Provider<OpsApi>.value(value: _api),
      ],
      child: Consumer<AuthState>(
        builder: (context, auth, _) => MaterialApp(
          // A new key on every sign-in/sign-out gives a fresh navigator.
          key: ValueKey<String>('${auth.status.name}-${auth.user?.id ?? ''}'),
          title: widget.title,
          debugShowCheckedModeBanner: false,
          theme: buildOpsTheme(),
          home: Builder(builder: (ctx) => _home(ctx, auth)),
        ),
      ),
    );
  }
}
