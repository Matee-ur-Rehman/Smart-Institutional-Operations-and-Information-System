import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/json.dart';
import '../../core/widgets.dart';

/// Downloads a report (`/reports/...`) and hands it to the platform (browser download / save dialog).
/// [query] values may be String, num, bool or DateTime; null / empty values are skipped.
Future<void> downloadReport(BuildContext context, String path,
    {Map<String, dynamic>? query, String fallbackName = 'report.pdf'}) async {
  final api = context.read<ApiClient>();
  final params = <String, String>{};
  query?.forEach((k, v) {
    if (v == null) return;
    final s = v is DateTime ? isoDate(v) : v.toString();
    if (s.isNotEmpty) params[k] = s;
  });
  final url = params.isEmpty ? path : Uri(path: path, queryParameters: params).toString();
  showSnack(context, 'Preparing report…');
  try {
    final f = await api.download(url, fallbackName: fallbackName);
    final dot = f.filename.lastIndexOf('.');
    final base = dot > 0 ? f.filename.substring(0, dot) : f.filename;
    final ext = dot > 0 ? f.filename.substring(dot + 1).toLowerCase() : '';
    final mime = ext == 'pdf' ? MimeType.pdf : (ext == 'csv' ? MimeType.csv : MimeType.other);
    await FileSaver.instance.saveFile(name: base, bytes: f.bytes, ext: ext, mimeType: mime);
    if (context.mounted) showSnack(context, 'Saved ${f.filename}');
  } catch (e) {
    if (context.mounted) showError(context, e);
  }
}

/// A small "download" button used on cards and list rows.
class ReportButton extends StatelessWidget {
  const ReportButton({super.key, required this.label, required this.path, this.query, this.icon = Icons.picture_as_pdf_outlined, this.fallbackName = 'report.pdf'});
  final String label;
  final String path;
  final Map<String, dynamic>? query;
  final IconData icon;
  final String fallbackName;

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
        onPressed: () => downloadReport(context, path, query: query, fallbackName: fallbackName),
        icon: Icon(icon, size: 18),
        label: Text(label),
      );
}
