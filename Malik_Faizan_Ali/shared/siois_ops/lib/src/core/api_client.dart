import 'dart:async';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'json.dart';

class FieldError {
  const FieldError(this.field, this.message);
  final String field;
  final String message;
}

/// Every non-2xx response (and network failure) becomes one of these. `message` is safe to show to users.
class ApiException implements Exception {
  ApiException(this.statusCode, this.code, this.message, {this.fieldErrors = const <FieldError>[]});

  final int? statusCode;
  final String code;
  final String message;
  final List<FieldError> fieldErrors;

  bool get isUnauthorized => statusCode == 401;
  bool get isForbidden => statusCode == 403;
  bool get isNotFound => statusCode == 404;

  /// Server-side validation message for a form field, e.g. `errorFor('due_date')`.
  String? errorFor(String field) {
    for (final e in fieldErrors) {
      if (e.field == field || e.field.endsWith('.$field')) return e.message;
    }
    return null;
  }

  /// Message plus any field errors on separate lines (for snack bars / dialogs).
  String get fullMessage => fieldErrors.isEmpty
      ? message
      : '$message\n${fieldErrors.map((e) => '• ${e.field}: ${e.message}').join('\n')}';

  @override
  String toString() => message;
}

/// Access/refresh token persistence (secure storage; falls back to memory if storage is unavailable).
class TokenStore {
  TokenStore([FlutterSecureStorage? storage]) : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;
  String? access;
  String? refresh;

  Future<void> load() async {
    try {
      access = await _storage.read(key: 'siois_access');
      refresh = await _storage.read(key: 'siois_refresh');
    } catch (_) {
      // storage unavailable: stay in memory
    }
  }

  Future<void> save(String accessToken, String refreshToken) async {
    access = accessToken;
    refresh = refreshToken;
    try {
      await _storage.write(key: 'siois_access', value: accessToken);
      await _storage.write(key: 'siois_refresh', value: refreshToken);
    } catch (_) {}
  }

  Future<void> clear() async {
    access = null;
    refresh = null;
    try {
      await _storage.delete(key: 'siois_access');
      await _storage.delete(key: 'siois_refresh');
    } catch (_) {}
  }
}

/// A downloaded file.
class DownloadedFile {
  DownloadedFile(this.bytes, this.filename, this.contentType);
  final Uint8List bytes;
  final String filename;
  final String? contentType;
}

/// Thin Dio wrapper: Bearer header, `X-Client-Platform`, one silent token refresh on 401, uniform errors.
/// Returns decoded JSON (Map / List / null for 204).
class ApiClient {
  ApiClient({required this.baseUrl, required this.platform, required this.tokens})
      : _dio = Dio(BaseOptions(
          baseUrl: apiRoot(baseUrl),
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'X-Client-Platform': platform, 'Accept': 'application/json'},
        ));

  final String baseUrl;
  final String platform;
  final TokenStore tokens;
  final Dio _dio;

  /// The backend serves every route under `/api/v1`; callers pass only the host (e.g. http://localhost:8000)
  /// and use short paths such as `/auth/login`.
  static String apiRoot(String host) {
    final h = host.endsWith('/') ? host.substring(0, host.length - 1) : host;
    return h.endsWith('/api/v1') ? h : '$h/api/v1';
  }

  /// Called when the session can no longer be refreshed (the app returns to the login screen).
  void Function()? onSessionExpired;

  Completer<bool>? _refreshing;

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) => _send('GET', path, query: query);

  Future<dynamic> post(String path, {Object? body, Map<String, dynamic>? query, bool auth = true}) =>
      _send('POST', path, body: () => body, query: query, auth: auth);

  Future<dynamic> put(String path, {Object? body}) => _send('PUT', path, body: () => body);

  Future<dynamic> patch(String path, {Object? body}) => _send('PATCH', path, body: () => body);

  Future<dynamic> delete(String path) => _send('DELETE', path);

  /// multipart/form-data upload of one file.
  Future<dynamic> upload(String path, {required String field, required Uint8List bytes, required String filename}) =>
      _send('POST', path, body: () => FormData.fromMap({field: MultipartFile.fromBytes(bytes, filename: filename)}));

  Future<DownloadedFile> download(String path, {String fallbackName = 'download'}) async {
    final res = await _sendRaw('GET', path, responseType: ResponseType.bytes);
    final data = res.data;
    final bytes = data is Uint8List ? data : Uint8List.fromList(List<int>.from(data as List));
    var name = fallbackName;
    final cd = res.headers.value('content-disposition');
    if (cd != null) {
      final m = RegExp('filename\\*?=(?:UTF-8\'\')?"?([^";]+)"?').firstMatch(cd);
      if (m != null) name = Uri.decodeComponent(m.group(1)!);
    }
    return DownloadedFile(bytes, name, res.headers.value('content-type'));
  }

  Map<String, dynamic>? _clean(Map<String, dynamic>? q) {
    if (q == null) return null;
    final out = <String, dynamic>{};
    q.forEach((k, v) {
      if (v == null) return;
      if (v is String && v.isEmpty) return;
      out[k] = v is DateTime ? isoDate(v) : v;
    });
    return out;
  }

  Future<Response<dynamic>> _sendRaw(String method, String path,
      {Object? Function()? body,
      Map<String, dynamic>? query,
      bool auth = true,
      ResponseType? responseType,
      bool retry = true}) async {
    try {
      return await _dio.request<dynamic>(
        path,
        data: body?.call(),
        queryParameters: _clean(query),
        options: Options(
          method: method,
          responseType: responseType,
          headers: {if (auth && tokens.access != null) 'Authorization': 'Bearer ${tokens.access}'},
        ),
      );
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == 401 && auth && retry && tokens.refresh != null) {
        if (await _refreshTokens()) {
          return _sendRaw(method, path, body: body, query: query, auth: auth, responseType: responseType, retry: false);
        }
        onSessionExpired?.call();
      }
      throw _toException(e);
    }
  }

  Future<dynamic> _send(String method, String path,
      {Object? Function()? body, Map<String, dynamic>? query, bool auth = true}) async {
    final res = await _sendRaw(method, path, body: body, query: query, auth: auth);
    final d = res.data;
    if (d is String && d.isEmpty) return null;
    return d;
  }

  /// One refresh at a time; concurrent 401s wait for the same result.
  Future<bool> _refreshTokens() {
    final running = _refreshing;
    if (running != null) return running.future;
    final c = Completer<bool>();
    _refreshing = c;
    () async {
      try {
        final bare = Dio(BaseOptions(baseUrl: apiRoot(baseUrl), headers: {'X-Client-Platform': platform}));
        final res = await bare.post<dynamic>('/auth/refresh', data: {'refresh_token': tokens.refresh});
        final m = asMap(res.data);
        await tokens.save(asStr(m['access_token']), asStr(m['refresh_token']));
        c.complete(true);
      } catch (_) {
        await tokens.clear();
        c.complete(false);
      } finally {
        _refreshing = null;
      }
    }();
    return c.future;
  }

  ApiException _toException(DioException e) {
    final status = e.response?.statusCode;
    final data = e.response?.data;
    if (status == null) {
      final timedOut = e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout ||
          e.type == DioExceptionType.sendTimeout;
      return ApiException(null, 'network_error',
          timedOut ? 'The server took too long to respond. Please try again.' : 'Cannot reach the server. Check your connection and the API address.');
    }
    if (data is Map) {
      final m = asMap(data);
      final detail = m['detail'];
      final errs = asMapList(m['errors']).map((x) => FieldError(asStr(x['field']), asStr(x['message']))).toList();
      final message = detail is String ? detail : 'Request failed ($status)';
      return ApiException(status, asStr(m['code'], 'error'), message, fieldErrors: errs);
    }
    return ApiException(status, 'error', 'Request failed ($status)');
  }
}
