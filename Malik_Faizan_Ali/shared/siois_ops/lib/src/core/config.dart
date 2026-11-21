import 'auth.dart';

/// Per-app configuration. web_app and mobile_app each build one of these in main.dart.
class AppConfig {
  const AppConfig({
    required this.platform,
    required this.title,
    required this.allowedRoles,
    required this.apiBaseUrl,
    this.demoPassword = '',
    this.demoLoginIds = const <Role, List<String>>{},
    this.pushTokenProvider,
  });

  /// Sent as `X-Client-Platform` on every request. Must be `web` or `mobile`.
  final String platform;
  final String title;

  /// Roles that may use this app (web: admin+teacher, mobile: teacher+student+parent).
  final List<Role> allowedRoles;

  /// From `--dart-define=API_BASE_URL=...`; never hard-coded in the apps.
  final String apiBaseUrl;

  /// Optional (`--dart-define=DEMO_PASSWORD=...`). When set, the login screen shows one-tap demo accounts.
  final String demoPassword;
  final Map<Role, List<String>> demoLoginIds;

  /// Optional (mobile only): returns the device's FCM token after sign-in, or null when push is not set up.
  /// The shared package then registers it with `POST /devices/register`. See mobile_app/PUSH_SETUP.md.
  final Future<String?> Function()? pushTokenProvider;

  bool get isWeb => platform == 'web';
}
