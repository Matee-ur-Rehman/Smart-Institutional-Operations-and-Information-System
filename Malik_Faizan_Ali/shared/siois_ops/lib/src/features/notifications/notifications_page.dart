import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/shell.dart';
import '../../core/api_client.dart';
import '../../core/format.dart';
import '../../core/json.dart';
import '../../core/theme.dart';
import '../../core/widgets.dart';
import '../common/paged_list.dart';

class _Note {
  _Note(this.json);
  final Map<String, dynamic> json;
  String get id => asStr(json['id']);
  String get title => asStr(json['title']);
  String get body => asStr(json['body']);
  String get type => asStr(json['type']);
  bool get isRead => asBool(json['is_read']);
  DateTime? get createdAt => asDateN(json['created_at']);
}

IconData _iconFor(String type) {
  switch (type) {
    case 'homework':
    case 'assignment':
      return Icons.menu_book_outlined;
    case 'marks':
    case 'exam':
      return Icons.assignment_outlined;
    case 'fee':
    case 'fees':
      return Icons.payments_outlined;
    case 'attendance':
      return Icons.fact_check_outlined;
    case 'leave':
      return Icons.event_available_outlined;
    case 'announcement':
      return Icons.campaign_outlined;
    case 'event':
    case 'calendar':
      return Icons.event_outlined;
    case 'complaint':
      return Icons.support_agent_outlined;
    default:
      return Icons.notifications_outlined;
  }
}

/// The user's in-app notifications (the same messages that are pushed to phones when FCM is configured).
class NotificationsPage extends StatefulWidget {
  const NotificationsPage({super.key});
  @override
  State<NotificationsPage> createState() => _NotificationsPageState();
}

class _NotificationsPageState extends State<NotificationsPage> {
  bool _unreadOnly = false;
  int _key = 0;

  Future<void> _readAll() async {
    final shell = context.read<ShellController>();
    try {
      await context.read<ApiClient>().post('/notifications/read-all');
      await shell.refreshUnread();
      if (mounted) setState(() => _key++);
    } catch (e) {
      if (mounted) showError(context, e);
    }
  }

  Future<void> _open(_Note n, Future<void> Function() reload) async {
    final shell = context.read<ShellController>();
    if (!n.isRead) {
      try {
        await context.read<ApiClient>().post('/notifications/${n.id}/read');
        await shell.refreshUnread();
        await reload();
      } catch (_) {
        // reading is best-effort; the message stays unread
      }
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(n.title),
        content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(formatDateTime(n.createdAt), style: const TextStyle(color: Brand.muted, fontSize: 12.5)),
          const SizedBox(height: 10),
          Text(n.body),
        ]),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return PageFrame(
      title: 'Notifications',
      subtitle: 'Messages about homework, results, fees, leave and more',
      actions: [OutlinedButton.icon(onPressed: _readAll, icon: const Icon(Icons.done_all), label: const Text('Mark all as read'))],
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: SegmentedButton<bool>(
            segments: const [ButtonSegment(value: false, label: Text('All')), ButtonSegment(value: true, label: Text('Unread'))],
            selected: {_unreadOnly},
            onSelectionChanged: (s) => setState(() => _unreadOnly = s.first),
          ),
        ),
        Expanded(
          child: PagedList<_Note>(
            path: '/notifications',
            reloadKey: _key,
            query: {'is_read': _unreadOnly ? false : null},
            parse: _Note.new,
            emptyTitle: _unreadOnly ? 'No unread notifications' : 'No notifications yet',
            emptyIcon: Icons.notifications_none,
            itemBuilder: (context, n, reload) => AppCard(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              onTap: () => _open(n, reload),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(_iconFor(n.type), color: n.isRead ? Brand.muted : Brand.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(n.title, style: TextStyle(fontWeight: n.isRead ? FontWeight.w500 : FontWeight.w800)),
                    Text(n.body, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(color: Brand.muted)),
                    const SizedBox(height: 2),
                    Text(formatDateTime(n.createdAt), style: const TextStyle(color: Brand.muted, fontSize: 11.5)),
                  ]),
                ),
                if (!n.isRead) const Padding(padding: EdgeInsets.only(top: 4), child: Icon(Icons.circle, size: 10, color: Brand.primary)),
              ]),
            ),
          ),
        ),
      ]),
    );
  }
}
