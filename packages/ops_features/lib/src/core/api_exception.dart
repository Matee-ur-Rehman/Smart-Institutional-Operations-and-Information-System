import 'dart:convert';

import 'package:dio/dio.dart';

/// One field-level problem from a 422 response: {"field": "...", "message": "..."}.
class FieldError {
  const FieldError({required this.field, required this.message});

  final String field;
  final String message;

  @override
  String toString() => field.isEmpty ? message : '$field: $message';
}

/// Every API failure, parsed from the shared error shape (docs/API_CONTRACT.md section 1):
///   {"detail": "...", "code": "...", "errors": [{"field": "...", "message": "..."}]}
class ApiException implements Exception {
  const ApiException({
    this.statusCode,
    required this.code,
    required this.detail,
    this.errors = const <FieldError>[],
  });

  final int? statusCode;
  final String code;
  final String detail;
  final List<FieldError> errors;

  static String defaultCodeFor(int? status) {
    switch (status) {
      case 400:
        return 'bad_request';
      case 401:
        return 'not_authenticated';
      case 403:
        return 'forbidden';
      case 404:
        return 'not_found';
      case 409:
        return 'conflict';
      case 413:
        return 'payload_too_large';
      case 422:
        return 'validation_error';
      default:
        return 'error';
    }
  }

  /// Builds an exception from a decoded (or raw bytes / String) response body.
  factory ApiException.fromBody(int? statusCode, dynamic body) {
    dynamic data = body;
    if (data is List<int>) {
      try {
        data = jsonDecode(utf8.decode(data));
      } catch (_) {
        data = null;
      }
    } else if (data is String) {
      try {
        data = jsonDecode(data);
      } catch (_) {
        // keep the raw string
      }
    }
    if (data is Map) {
      final rawDetail = data['detail'];
      final detail = rawDetail is String && rawDetail.isNotEmpty ? rawDetail : 'Request failed';
      final rawCode = data['code'];
      final code = rawCode is String && rawCode.isNotEmpty ? rawCode : defaultCodeFor(statusCode);
      final errors = <FieldError>[];
      final rawErrors = data['errors'];
      if (rawErrors is List) {
        for (final e in rawErrors) {
          if (e is Map) {
            errors.add(FieldError(
              field: (e['field'] ?? '').toString(),
              message: (e['message'] ?? e['msg'] ?? '').toString(),
            ));
          }
        }
      }
      return ApiException(statusCode: statusCode, code: code, detail: detail, errors: errors);
    }
    final text = data is String && data.isNotEmpty ? data : 'Request failed (HTTP ${statusCode ?? '?'})';
    return ApiException(statusCode: statusCode, code: defaultCodeFor(statusCode), detail: text);
  }

  factory ApiException.fromDio(DioException e) {
    final res = e.response;
    if (res != null) return ApiException.fromBody(res.statusCode, res.data);
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(code: 'timeout', detail: 'The server took too long to respond. Please try again.');
      default:
        return const ApiException(
          code: 'network',
          detail: 'Cannot reach the server. Check your connection and the API address.',
        );
    }
  }

  bool get isNetwork => code == 'network' || code == 'timeout';

  /// Text for a SnackBar or an inline error.
  String get message {
    if (errors.isEmpty) return detail;
    return '$detail: ${errors.map((e) => e.toString()).join('; ')}';
  }

  @override
  String toString() => message;
}
