/// Build-time configuration. Nothing secret lives in the app.
///
///   flutter run --dart-define=API_BASE_URL=http://localhost:8000/api/v1
///
/// There is deliberately no default URL: a missing value produces a clear error instead of
/// silently talking to the wrong server.
class OpsConfig {
  OpsConfig._();

  static const String apiBaseUrl = String.fromEnvironment('API_BASE_URL');

  static bool get isConfigured => apiBaseUrl.isNotEmpty;

  static const String missingUrlMessage =
      'API_BASE_URL is not set. Start the app with '
      '--dart-define=API_BASE_URL=http://<host>:8000/api/v1 '
      '(Android emulator: http://10.0.2.2:8000/api/v1).';
}
