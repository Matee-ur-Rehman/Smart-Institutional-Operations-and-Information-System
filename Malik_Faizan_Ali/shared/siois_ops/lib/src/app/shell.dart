import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/auth.dart';
import '../core/json.dart';
import '../core/nav.dart';
import '../core/theme.dart';
import '../core/widgets.dart';

/// Lets any screen jump to another sidebar item and read / refresh the unread-notification badge.
///
/// ```dart
/// context.read<ShellController>().goTo('fees');
/// await context.read<ShellController>().refreshUnread();
/// ```
class ShellController extends ChangeNotifier {
  ShellController(this._api);
  final ApiClient _api;

  String? _requested;
  int unread = 0;

  /// Entry id requested by [goTo] (consumed by the shell).
  String? takeRequest() {
    final r = _requested;
    _requested = null;
    return r;
  }

  void goTo(String id) {
    _requested = id;
    notifyListeners();
  }

  Future<void> refreshUnread() async {
    try {
      final m = asMap(await _api.get('/notifications/unread-count'));
      final c = asInt(m['count']);
      if (c != unread) {
        unread = c;
        notifyListeners();
      }
    } catch (_) {
      // badge is best effort
    }
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.entries, required this.user, required this.onLogout});
  final List<NavEntry> entries;
  final AppUser user;
  final Future<void> Function() onLogout;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  late final ShellController _shell;
  int _index = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _shell = ShellController(context.read<ApiClient>());
    _shell.addListener(_onShell);
    _shell.refreshUnread();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _shell.refreshUnread());
  }

  void _onShell() {
    final id = _shell.takeRequest();
    if (id == null) return;
    final i = widget.entries.indexWhere((e) => e.id == id);
    if (i >= 0 && mounted) setState(() => _index = i);
  }

  @override
  void dispose() {
    _timer?.cancel();
    _shell.removeListener(_onShell);
    _shell.dispose();
    super.dispose();
  }

  void _select(int i, {bool closeDrawer = false}) {
    setState(() => _index = i);
    if (closeDrawer) Navigator.of(context).maybePop();
  }

  Widget _menu({required bool inDrawer}) {
    final items = <Widget>[];
    String? lastGroup;
    for (var i = 0; i < widget.entries.length; i++) {
      final e = widget.entries[i];
      if (e.group != null && e.group != lastGroup) {
        items.add(Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 16, 6),
          child: Text(e.group!.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: 1.1, fontWeight: FontWeight.w700, color: Brand.muted)),
        ));
      }
      lastGroup = e.group;
      final selected = i == _index;
      items.add(Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 1),
        child: ListTile(
          dense: true,
          selected: selected,
          selectedTileColor: Brand.primary.withValues(alpha: 0.10),
          selectedColor: Brand.primaryDark,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
          leading: Icon(e.icon, size: 22),
          title: Text(e.title, style: TextStyle(fontWeight: selected ? FontWeight.w700 : FontWeight.w500)),
          trailing: e.id == 'notifications' && _shell.unread > 0 ? _Badge(count: _shell.unread) : null,
          onTap: () => _select(i, closeDrawer: inDrawer),
        ),
      ));
    }
    return Column(children: [
      Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(20, 24, 16, 20),
        decoration: const BoxDecoration(gradient: LinearGradient(colors: [Brand.primaryDark, Brand.primary])),
        child: SafeArea(
          bottom: false,
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Icon(Icons.school, color: Colors.white, size: 32),
            const SizedBox(height: 8),
            const Text('Trends High School', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 17)),
            Text('Hassan Abdal · SIOIS', style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 12)),
          ]),
        ),
      ),
      Expanded(child: ListView(padding: const EdgeInsets.only(bottom: 12), children: items)),
      const Divider(),
      ListTile(
        dense: true,
        leading: CircleAvatar(radius: 16, backgroundColor: Brand.primary, child: Text(widget.user.initials, style: const TextStyle(color: Colors.white, fontSize: 12))),
        title: Text(widget.user.fullName, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(widget.user.role.label),
        trailing: IconButton(tooltip: 'Sign out', icon: const Icon(Icons.logout), onPressed: widget.onLogout),
      ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<ShellController>.value(
      value: _shell,
      child: ListenableBuilder(
        listenable: _shell,
        builder: (context, _) {
          final entry = widget.entries[_index.clamp(0, widget.entries.length - 1)];
          final body = KeyedSubtree(key: ValueKey<String>(entry.id), child: entry.builder(context));
          if (isWide(context)) {
            return Scaffold(
              body: Row(children: [
                SizedBox(width: 264, child: Material(color: Colors.white, child: _menu(inDrawer: false))),
                const VerticalDivider(width: 1),
                Expanded(child: body),
              ]),
            );
          }
          return Scaffold(
            appBar: AppBar(
              title: Text(entry.title),
              actions: [
                IconButton(
                  tooltip: 'Notifications',
                  icon: Badge(isLabelVisible: _shell.unread > 0, label: Text('${_shell.unread}'), child: const Icon(Icons.notifications_outlined)),
                  onPressed: () => _shell.goTo('notifications'),
                ),
              ],
            ),
            drawer: Drawer(child: _menu(inDrawer: true)),
            body: body,
          );
        },
      ),
    );
  }
}

class _Badge extends StatelessWidget {
  const _Badge({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: Brand.danger, borderRadius: BorderRadius.circular(12)),
        child: Text(count > 99 ? '99+' : '$count', style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700)),
      );
}
