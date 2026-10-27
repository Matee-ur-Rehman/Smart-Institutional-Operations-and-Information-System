import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'api_exception.dart';
import 'json_utils.dart';
import 'token_store.dart';

class AuthUser {
  const AuthUser({required this.id, required this.loginId, required this.fullName, required this.role});

  final String id;
  final String loginId;
  final String fullName;
  final String role;

  factory AuthUser.fromJson(Map<String, dynamic> j) => AuthUser(
        id: jStr(j['id']),
        loginId: jStr(j['login_id']),
        fullName: jStr(j['full_name'] ?? j['name'] ?? j['login_id']),
        role: jStr(j['role']),
      );
}

enum AuthStatus { unknown, signedOut, signedIn }

/// Login state shared by the whole app. The shell (Faizan's or ours) only needs `status`,
/// `user`, `login()` and `logout()`.
class AuthState extends ChangeNotifier {
  AuthState({required this.client, required this.tokens, required this.allowedRoles}) {
    client.onSessionExpired = _onSessionExpired;
  }

  final ApiClient client;
  final TokenStore tokens;

  /// Roles that may use this app: web = {admin, teacher}, mobile = {teacher, student, parent}.
  final Set<String> allowedRoles;

  AuthStatus status = AuthStatus.unknown;
  AuthUser? user;
  String? _deviceToken;

  static String roleNotAllowedMessage(String role, Set<String> allowed) {
    final list = allowed.toList()..sort();
    return 'A "$role" account cannot sign in on this app. This app is for: ${list.join(', ')}.';
  }

  /// Called once at start-up: restores a saved session if the server still accepts it.
  Future<void> restore() async {
    final access = await tokens.readAccess();
    if (access == null) {
      status = AuthStatus.signedOut;
      notifyListeners();
      return;
    }
    try {
      final me = AuthUser.fromJson(jMap(await client.get('/auth/me')));
      if (!allowedRoles.contains(me.role)) {
        await tokens.clear();
        status = AuthStatus.signedOut;
      } else {
        user = me;
        status = AuthStatus.signedIn;
      }
    } catch (_) {
      status = AuthStatus.signedOut;
    }
    notifyListeners();
  }

  /// Throws [ApiException] on failure (wrong password, wrong platform, wrong role, no network).
  Future<void> login(String loginId, String password) async {
    final body = jMap(await client.post(
      '/auth/login',
      data: <String, dynamic>{'login_id': loginId.trim(), 'password': password},
      auth: false,
    ));
    final signedIn = AuthUser.fromJson(jMap(body['user']));
    if (!allowedRoles.contains(signedIn.role)) {
      throw ApiException(
        statusCode: 403,
        code: 'forbidden',
        detail: roleNotAllowedMessage(signedIn.role, allowedRoles),
      );
    }
    final access = jStrN(body['access_token']);
    if (access == null) {
      throw const ApiException(code: 'error', detail: 'The server did not return an access token.');
    }
    await tokens.save(access, jStrN(body['refresh_token']));
    user = signedIn;
    status = AuthStatus.signedIn;
    notifyListeners();
  }

  /// Remember the FCM token so logout can unregister it. Used only when Firebase is configured
  /// (see packages/ops_features/FCM_TODO.md).
  void rememberDeviceToken(String token) => _deviceToken = token;

  Future<void> logout() async {
    final token = _deviceToken;
    if (token != null) {
      try {
        await client.delete('/devices/${Uri.encodeComponent(token)}');
      } catch (_) {
        // logging out must never fail because the device could not be unregistered
      }
      _deviceToken = null;
    }
    await tokens.clear();
    user = null;
    status = AuthStatus.signedOut;
    notifyListeners();
  }

  void _onSessionExpired() {
    if (status != AuthStatus.signedIn) return;
    user = null;
    status = AuthStatus.signedOut;
    notifyListeners();
  }
}
