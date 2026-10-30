import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../ui/ui.dart';

/// School announcements. Everyone reads (the server only returns what their audience allows);
/// the admin ([canManage]) creates, publishes, archives and deletes.
class AnnouncementsScreen extends StatefulWidget {
  const AnnouncementsScreen({super.key, this.canManage = false});

  final bool canManage;

  @override
  State<AnnouncementsScreen> createState() => _AnnouncementsScreenState();
}

class _AnnouncementsScreenState extends State<AnnouncementsScreen> {
  late Future<Paged<Announcement>> _future;
  String? _status;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<Paged<Announcement>> _load() => context.read<OpsApi>().announcements(status: widget.canManage ? _status : null);

  void _reload() => setState(() => _future = _load());

  Future<void> _create() async {
    final api = context.read<OpsApi>();
    List<SectionItem> sections;
    try {
      sections = await api.sections();
    } on ApiException catch (e) {
      if (mounted) showMessage(context, e.message, error: true);
      return;
    }
    if (!mounted) return;
    var title = '';
    var body = '';
    var audience = 'all';
    var priority = 'normal';
    var publishNow = true;
    String? sectionId;

    final saved = await showFormDialog(
      context,
      title: 'New announcement',
      builder: (ctx, set) => Column(
        mainAxisSize: MainAxisSize.min,
        children: spaced([
          formText('Title', title, (v) => title = v),
          formText('Message', body, (v) => body = v, maxLines: 5),
          pickString('Audience', audience, const [
            MapEntry('all', 'Everyone'),
            MapEntry('teachers', 'Teachers'),
            MapEntry('students', 'Students'),
            MapEntry('parents', 'Parents'),
            MapEntry('class', 'One class section'),
          ], (v) => set(() => audience = v ?? audience)),
          if (audience == 'class')
            pickString('Section', sectionId, [for (final s in sections) MapEntry(s.id, s.display)],
                (v) => set(() => sectionId = v)),
          pickString('Priority', priority, const [
            MapEntry('normal', 'Normal'),
            MapEntry('important', 'Important'),
            MapEntry('urgent', 'Urgent'),
          ], (v) => set(() => priority = v ?? priority)),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('Publish now'),
            subtitle: const Text('Turn off to save as a draft'),
            value: publishNow,
            onChanged: (v) => set(() => publishNow = v),
          ),
        ]),
      ),
      validate: () {
        if (audience == 'class' && sectionId == null) return 'Choose a section';
        return Validators.minLength(title, 3, 'Title') ?? Validators.minLength(body, 3, 'Message');
      },
      onSubmit: () => api.createAnnouncement(<String, dynamic>{
        'title': title.trim(),
        'body': body.trim(),
        'audience': audience,
        if (audience == 'class') 'section_id': sectionId,
        'priority': priority,
        'status': publishNow ? 'published' : 'draft',
      }),
    );
    if (saved) {
      _reload();
      if (mounted) showMessage(context, publishNow ? 'Announcement published' : 'Draft saved');
    }
  }

  Future<void> _act(Announcement a, String action) async {
    final api = context.read<OpsApi>();
    if (action == 'delete' &&
        !await confirmDialog(context, 'Delete announcement?', '"${a.title}" will be removed.', yes: 'Delete')) {
      return;
    }
    if (!mounted) return;
    final ok = await runAction(
      context,
      () {
        switch (action) {
          case 'publish':
            return api.publishAnnouncement(a.id);
          case 'archive':
            return api.archiveAnnouncement(a.id);
          default:
            return api.deleteAnnouncement(a.id);
        }
      },
      success: action == 'publish' ? 'Published' : (action == 'archive' ? 'Archived' : 'Deleted'),
    );
    if (ok) _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Announcements'),
        actions: [IconButton(tooltip: 'Refresh', icon: const Icon(Icons.refresh), onPressed: _reload)],
      ),
      floatingActionButton: widget.canManage
          ? FloatingActionButton.extended(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New announcement'))
          : null,
      body: ContentWidth(
        child: Column(
          children: [
            if (widget.canManage)
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                child: Wrap(
                  spacing: 8,
                  children: [
                    for (final s in const <String?>[null, 'draft', 'published', 'archived'])
                      ChoiceChip(
                        label: Text(s == null ? 'All' : titleCase(s)),
                        selected: _status == s,
                        onSelected: (_) {
                          _status = s;
                          _reload();
                        },
                      ),
                  ],
                ),
              ),
            Expanded(
              child: FutureView<Paged<Announcement>>(
                future: _future,
                onRetry: _reload,
                builder: (ctx, page) {
                  if (page.items.isEmpty) return const EmptyView('No announcements', icon: Icons.campaign_outlined);
                  return ListView.builder(
                    padding: const EdgeInsets.fromLTRB(12, 8, 12, 88),
                    itemCount: page.items.length,
                    itemBuilder: (ctx, i) {
                      final a = page.items[i];
                      return Card(
                        child: Padding(
                          padding: const EdgeInsets.all(14),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Expanded(child: Text(a.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700))),
                                  if (a.priority != 'normal') StatusChip(a.priority),
                                  if (widget.canManage) ...[
                                    const SizedBox(width: 6),
                                    StatusChip(a.status),
                                    PopupMenuButton<String>(
                                      onSelected: (v) => _act(a, v),
                                      itemBuilder: (_) => [
                                        if (a.status == 'draft') const PopupMenuItem(value: 'publish', child: Text('Publish')),
                                        if (a.status == 'published') const PopupMenuItem(value: 'archive', child: Text('Archive')),
                                        const PopupMenuItem(value: 'delete', child: Text('Delete')),
                                      ],
                                    ),
                                  ],
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(a.body),
                              const SizedBox(height: 8),
                              Text(
                                '${fmtDateTime(a.publishAt ?? a.createdAt)}  -  for ${a.audience == 'class' ? 'one class' : a.audience}',
                                style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
