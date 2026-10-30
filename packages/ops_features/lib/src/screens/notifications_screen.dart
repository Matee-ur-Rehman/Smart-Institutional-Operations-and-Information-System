import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

IconData _iconFor(String type) {
  switch (type) {
    case 'homework':
      return Icons.menu_book_outlined;
    case 'marks':
      return Icons.grading_outlined;
    case 'fee':
      return Icons.payments_outlined;
    case 'event':
      return Icons.event_outlined;
    case 'announcement':
      return Icons.campaign_outlined;
    case 'complaint':
      return Icons.support_agent_outlined;
    case 'leave':
      return Icons.event_busy_outlined;
    case 'attendance':
      return Icons.fact_check_outlined;
    default:
      return Icons.notifications_outlined;
  }
}

/// The user's in-app notification inbox (works without Firebase).
class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late Future<Paged<NotificationItem>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().notifications();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().notifications());

  Future<void> _open(NotificationItem n) async {
    if (!n.isRead) {
      await runAction(context, () => context.read<OpsApi>().markRead(n.id));
      if (mounted) _reload();
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(n.title),
        content: Text(n.body),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          IconButton(
            tooltip: 'Mark all as read',
            icon: const Icon(Icons.done_all),
            onPressed: () async {
              final ok = await runAction(context, () => context.read<OpsApi>().markAllRead());
              if (ok && mounted) _reload();
            },
          ),
          IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload),
        ],
      ),
      body: ContentWidth(
        child: FutureView<Paged<NotificationItem>>(
          future: _future,
          onRetry: _reload,
          builder: (ctx, page) {
            if (page.items.isEmpty) return const EmptyView('No notifications', icon: Icons.notifications_none);
            return ListView.separated(
              itemCount: page.items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (ctx, i) {
                final n = page.items[i];
                return ListTile(
                  tileColor: n.isRead ? null : Theme.of(ctx).colorScheme.primary.withAlpha(18),
                  leading: Icon(_iconFor(n.type)),
                  title: Text(n.title, style: TextStyle(fontWeight: n.isRead ? FontWeight.normal : FontWeight.w700)),
                  subtitle: Text('${n.body}\n${fmtDateTime(n.createdAt)}', maxLines: 3, overflow: TextOverflow.ellipsis),
                  isThreeLine: true,
                  onTap: () => _open(n),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

/// App-bar bell with the unread count. Tapping opens the inbox and refreshes the count afterwards.
class NotificationBell extends StatefulWidget {
  const NotificationBell({super.key});

  @override
  State<NotificationBell> createState() => _NotificationBellState();
}

class _NotificationBellState extends State<NotificationBell> {
  int _count = 0;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    try {
      final n = await context.read<OpsApi>().unreadCount();
      if (mounted) setState(() => _count = n);
    } catch (_) {
      // the bell must never break the page it sits on
    }
  }

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: 'Notifications',
      icon: Badge(
        isLabelVisible: _count > 0,
        label: Text(_count > 99 ? '99+' : '$_count'),
        child: const Icon(Icons.notifications_outlined),
      ),
      onPressed: () async {
        await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const NotificationsScreen()));
        _refresh();
      },
    );
  }
}
