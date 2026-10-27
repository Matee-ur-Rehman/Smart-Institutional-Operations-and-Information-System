import 'package:dio/dio.dart';

import 'api_exception.dart';
import 'config.dart';
import 'json_utils.dart';
import 'token_store.dart';

/// Thin Dio wrapper used by every screen through OpsApi.
///  * adds `Authorization: Bearer <access>` and `X-Client-Platform: web|mobile`
///  * on `401 token_expired` calls POST /auth/refresh once and retries the request
///  * turns every failure into an [ApiException]
class ApiClient {
  ApiClient({required this.platform, required this.tokens, Dio? dio, String? baseUrl})
      : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: _normalize(baseUrl ?? OpsConfig.apiBaseUrl),
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 30),
              headers: <String, dynamic>{'Accept': 'application/json'},
            ));

  final String platform; // 'web' or 'mobile'
  final TokenStore tokens;
  final Dio _dio;

  /// Called when the session cannot be recovered (refresh failed or token invalid).
  void Function()? onSessionExpired;

  Future<bool>? _refreshing;

  static String _normalize(String url) => url.endsWith('/') ? url.substring(0, url.length - 1) : url;

  static Map<String, dynamic>? _clean(Map<String, dynamic>? query) {
    if (query == null) return null;
    final out = <String, dynamic>{};
    query.forEach((k, v) {
      if (v != null && v.toString().isNotEmpty) out[k] = v;
    });
    return out;
  }

  Future<dynamic> _send(
    String method,
    String path, {
    Map<String, dynamic>? query,
    Object? data,
    bool auth = true,
    bool retry = true,
    ResponseType? responseType,
  }) async {
    if (_dio.options.baseUrl.isEmpty) {
      throw const ApiException(code: 'config', detail: OpsConfig.missingUrlMessage);
    }
    final headers = <String, dynamic>{'X-Client-Platform': platform};
    if (auth) {
      final token = await tokens.readAccess();
      if (token != null) headers['Authorization'] = 'Bearer $token';
    }
    try {
      final res = await _dio.request<dynamic>(
        path,
        data: data,
        queryParameters: _clean(query),
        options: Options(method: method, headers: headers, responseType: responseType),
      );
      return res.data;
    } on DioException catch (e) {
      final ex = ApiException.fromDio(e);
      if (auth && retry && data is! FormData && ex.statusCode == 401 && ex.code == 'token_expired') {
        if (await _refresh()) {
          return _send(method, path,
              query: query, data: data, auth: auth, retry: false, responseType: responseType);
        }
      }
      if (auth && ex.statusCode == 401) {
        await tokens.clear();
        onSessionExpired?.call();
      }
      throw ex;
    }
  }

  Future<bool> _refresh() {
    return _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);
  }

  Future<bool> _doRefresh() async {
    final refreshToken = await tokens.readRefresh();
    if (refreshToken == null) return false;
    try {
      final res = await _dio.post<dynamic>(
        '/auth/refresh',
        data: <String, dynamic>{'refresh_token': refreshToken},
        options: Options(headers: <String, dynamic>{'X-Client-Platform': platform}),
      );
      final body = jMap(res.data);
      final access = jStrN(body['access_token']);
      if (access == null) return false;
      await tokens.save(access, jStrN(body['refresh_token']) ?? refreshToken);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) => _send('GET', path, query: query);

  Future<dynamic> post(String path, {Object? data, Map<String, dynamic>? query, bool auth = true}) =>
      _send('POST', path, data: data, query: query, auth: auth);

  Future<dynamic> put(String path, {Object? data}) => _send('PUT', path, data: data);

  Future<dynamic> patch(String path, {Object? data}) => _send('PATCH', path, data: data);

  Future<dynamic> delete(String path) => _send('DELETE', path);

  /// Multipart upload (homework attachment).
  Future<dynamic> postForm(String path, FormData form) => _send('POST', path, data: form);

  /// File download. The body is returned as raw bytes.
  Future<List<int>> getBytes(String path) async {
    final data = await _send('GET', path, responseType: ResponseType.bytes);
    if (data is List) return List<int>.from(data);
    return <int>[];
  }
}
