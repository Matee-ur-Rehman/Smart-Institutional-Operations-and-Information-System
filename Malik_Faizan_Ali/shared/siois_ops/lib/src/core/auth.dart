import 'package:flutter/foundation.dart';

import 'api_client.dart';
import 'json.dart';

enum Role { admin, teacher, student, parent }

extension RoleX on Role {
  String get label => switch (this) {
        Role.admin => 'Administrator',
        Role.teacher => 'Teacher',
        Role.student => 'Student',
        Role.parent => 'Parent',
      };

  static Role? parse(String? s) {
    for (final r in Role.values) {
      if (r.name == s) return r;
    }
    return null;
  }
}

class AppUser {
  AppUser({required this.id, required this.loginId, required this.role, required this.fullName, this.email, this.phone, this.mustChangePassword = false});

  final String id;
  final String loginId;
  final Role role;
  final String fullName;
  final String? email;
  final String? phone;

  /// True for accounts created / reset by an admin: the app asks for a new password before anything else.
  final bool mustChangePassword;

  String get initials {
    final parts = fullName.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first[0].toUpperCase();
    return (parts.first[0] + parts.last[0]).toUpperCase();
  }

  static AppUser? tryParse(dynamic json) {
    final m = asMap(json);
    final role = RoleX.parse(asStrN(m['role']));
    if (role == null) return null;
    return AppUser(
      id: asStr(m['id']),
      loginId: asStr(m['login_id']),
      role: role,
      fullName: asStr(m['full_name']),
      email: asStrN(m['email']),
      phone: asStrN(m['phone']),
      mustChangePassword: asBool(m['must_change_password']),
    );
  }
}

/// Holds the signed-in user. Login / restore / logout talk to Member 1's `/auth/*` endpoints.
class AuthController extends ChangeNotifier {
  AuthController({required this.api, required this.tokens, required this.allowedRoles});

  final ApiClient api;
  final TokenStore tokens;
  final List<Role> allowedRoles;

  AppUser? user;
  bool restoring = true;
  bool busy = false;

  /// Restores a previous session from secure storage (called once at start-up).
  Future<void> restore() async {
    await tokens.load();
    if (tokens.access != null) {
      try {
        final u = AppUser.tryParse(await api.get('/auth/me'));
        if (u != null && allowedRoles.contains(u.role)) {
          user = u;
        } else {
          await tokens.clear();
        }
      } catch (_) {
        await tokens.clear();
      }
    }
    restoring = false;
    notifyListeners();
  }

  /// Returns an error message, or null on success.
  Future<String?> login(String loginId, String password) async {
    busy = true;
    notifyListeners();
    try {
      final res = asMap(await api.post('/auth/login', body: {'login_id': loginId.trim(), 'password': password}, auth: false));
      final u = AppUser.tryParse(res['user']);
      if (u == null) return 'The server returned an unexpected response.';
      if (!allowedRoles.contains(u.role)) {
        return '${u.role.label} accounts cannot sign in here. Please use the correct app.';
      }
      await tokens.save(asStr(res['access_token']), asStr(res['refresh_token']));
      user = u;
      return null;
    } on ApiException catch (e) {
      return e.message;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  /// Re-reads `/auth/me` (after the user edited their own profile) and refreshes listeners.
  Future<void> refreshUser() async {
    final u = AppUser.tryParse(await api.get('/auth/me'));
    if (u != null) {
      user = u;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    try {
      if (tokens.access != null) await api.post('/auth/logout');
    } catch (_) {
      // best effort: the local session ends regardless
    }
    await forceLogout();
  }

  /// Local sign-out (used when the refresh token is rejected).
  Future<void> forceLogout() async {
    await tokens.clear();
    user = null;
    notifyListeners();
  }
}
