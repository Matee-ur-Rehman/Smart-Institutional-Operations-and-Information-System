import 'package:file_saver/file_saver.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/widgets.dart';

/// Downloads an assignment attachment and hands it to the platform (browser download / save dialog).
Future<void> downloadAssignmentAttachment(BuildContext context, String assignmentId) async {
  final api = context.read<ApiClient>();
  try {
    final f = await api.download('/assignments/$assignmentId/attachment', fallbackName: 'homework');
    final dot = f.filename.lastIndexOf('.');
    final base = dot > 0 ? f.filename.substring(0, dot) : f.filename;
    final ext = dot > 0 ? f.filename.substring(dot + 1) : '';
    await FileSaver.instance.saveFile(name: base, bytes: f.bytes, ext: ext, mimeType: MimeType.other);
    if (context.mounted) showSnack(context, 'Saved ${f.filename}');
  } catch (e) {
    if (context.mounted) showError(context, e);
  }
}
