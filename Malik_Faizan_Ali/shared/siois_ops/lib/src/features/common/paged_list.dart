import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/api_client.dart';
import '../../core/json.dart';
import '../../core/widgets.dart';

typedef PagedItemBuilder<T> = Widget Function(BuildContext context, T item, Future<void> Function() reload);

/// A server-paginated list: `GET [path]?page=&page_size=&...query` returning `{items,total,page,page_size}`.
///
/// Changing [query] or [reloadKey] reloads from page 1. [itemBuilder] receives a `reload` callback to call
/// after it changed something (edit / delete) so the list refreshes in place.
class PagedList<T> extends StatefulWidget {
  const PagedList({
    super.key,
    required this.path,
    required this.parse,
    required this.itemBuilder,
    this.query = const <String, dynamic>{},
    this.reloadKey = 0,
    this.pageSize = 20,
    this.emptyTitle = 'Nothing here yet',
    this.emptyMessage,
    this.emptyIcon = Icons.inbox_outlined,
  });

  final String path;
  final T Function(Map<String, dynamic>) parse;
  final PagedItemBuilder<T> itemBuilder;
  final Map<String, dynamic> query;
  final int reloadKey;
  final int pageSize;
  final String emptyTitle;
  final String? emptyMessage;
  final IconData emptyIcon;

  @override
  State<PagedList<T>> createState() => _PagedListState<T>();
}

class _PagedListState<T> extends State<PagedList<T>> {
  int _page = 1;
  late Future<PageResult<T>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  @override
  void didUpdateWidget(covariant PagedList<T> old) {
    super.didUpdateWidget(old);
    if (old.reloadKey != widget.reloadKey || old.path != widget.path || !mapEquals(old.query, widget.query)) {
      _page = 1;
      _future = _load();
    }
  }

  Future<PageResult<T>> _load() async {
    final api = context.read<ApiClient>();
    final res = await api.get(widget.path, query: <String, dynamic>{
      ...widget.query,
      'page': _page,
      'page_size': widget.pageSize,
    });
    return PageResult<T>.fromJson(res, widget.parse);
  }

  Future<void> _reload() async {
    final f = _load();
    setState(() { _future = f; });
    try {
      await f;
    } catch (_) {}
  }

  void _goTo(int page) {
    setState(() {
      _page = page;
      _future = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<PageResult<T>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const LoadingView();
        if (snap.hasError) return ErrorView(error: snap.error!, onRetry: _reload);
        final data = snap.data!;
        if (data.items.isEmpty) {
          return EmptyState(icon: widget.emptyIcon, title: widget.emptyTitle, message: widget.emptyMessage);
        }
        return Column(children: [
          Expanded(
            child: ListView.separated(
              padding: const EdgeInsets.only(bottom: 8),
              itemCount: data.items.length,
              separatorBuilder: (context, index) => const SizedBox(height: 8),
              itemBuilder: (context, index) => widget.itemBuilder(context, data.items[index], _reload),
            ),
          ),
          PaginationBar(page: data.page, pageSize: data.pageSize, total: data.total, onPage: _goTo),
        ]);
      },
    );
  }
}
