import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/core.dart';
import '../data/ops_api.dart';
import '../models/models.dart';
import '../screens/announcements_screen.dart';
import '../screens/calendar_screen.dart';
import '../screens/complaints_screens.dart';
import '../screens/exams_screens.dart';
import '../screens/fees_screens.dart';
import '../screens/homework_screen.dart';
import '../screens/notifications_screen.dart';
import '../screens/timetable_screens.dart';
import '../ui/ui.dart';

/// One entry of a dashboard (a tile on a phone, a menu row on a wide screen).
/// Member 1 adds his modules (attendance, leave, reports, ...) by passing more of these as
/// `extraItems` to a dashboard, so the two members never edit the same list.
class DashboardItem {
  const DashboardItem({required this.label, required this.icon, required this.builder});

  final String label;
  final IconData icon;
  final WidgetBuilder builder;
}

/// Layout shared by every role: a side menu with the selected page on screens at least 900 wide
/// (web), otherwise a grid of tiles that open pages on top (phones).
class DashboardShell extends StatefulWidget {
  const DashboardShell({super.key, required this.title, required this.items, this.header});

  final String title;
  final List<DashboardItem> items;

  /// Shown under the title (the child picker for parents).
  final Widget? header;

  @override
  State<DashboardShell> createState() => _DashboardShellState();
}

class _DashboardShellState extends State<DashboardShell> {
  int _index = 0;

  Future<void> _logout() async {
    final ok = await confirmDialog(context, 'Sign out?', 'You will need to sign in again.', yes: 'Sign out');
    if (!ok || !mounted) return;
    await context.read<AuthState>().logout();
  }

  @override
  Widget build(BuildContext context) {
    final name = context.watch<AuthState>().user?.fullName ?? '';
    return LayoutBuilder(
      builder: (context, constraints) =>
          constraints.maxWidth >= 900 ? _wide(context, name) : _narrow(context, name),
    );
  }

  Widget _wide(BuildContext context, String name) {
    final items = widget.items;
    final index = items.isEmpty ? 0 : _index.clamp(0, items.length - 1);
    return Scaffold(
      body: Row(
        children: [
          SizedBox(
            width: 250,
            child: Material(
              color: Colors.blueGrey.shade50,
              child: SafeArea(
                child: Column(
                  children: [
                    Padding(
                      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
                      child: Align(
                        alignment: Alignment.centerLeft,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(widget.title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
                            const SizedBox(height: 4),
                            Text(name, style: TextStyle(color: Theme.of(context).hintColor)),
                          ],
                        ),
                      ),
                    ),
                    if (widget.header != null)
                      Padding(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4), child: widget.header),
                    const Divider(height: 1),
                    Expanded(
                      child: ListView(
                        children: [
                          for (var i = 0; i < items.length; i++)
                            ListTile(
                              dense: true,
                              leading: Icon(items[i].icon),
                              title: Text(items[i].label),
                              selected: i == index,
                              onTap: () => setState(() => _index = i),
                            ),
                        ],
                      ),
                    ),
                    const Divider(height: 1),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      child: Row(
                        children: [
                          const NotificationBell(),
                          const Spacer(),
                          IconButton(tooltip: 'Sign out', icon: const Icon(Icons.logout), onPressed: _logout),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const VerticalDivider(width: 1),
          Expanded(
            child: items.isEmpty
                ? const EmptyView('Nothing to show here yet')
                : KeyedSubtree(
                    key: ValueKey<String>('$index-${items[index].label}'),
                    child: items[index].builder(context),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _narrow(BuildContext context, String name) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          const NotificationBell(),
          IconButton(tooltip: 'Sign out', icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Welcome, $name', style: Theme.of(context).textTheme.titleLarge),
          if (widget.header != null) ...[const SizedBox(height: 12), widget.header!],
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.25,
            children: [
              for (final item in widget.items)
                Card(
                  child: InkWell(
                    borderRadius: BorderRadius.circular(12),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: item.builder)),
                    child: Padding(
                      padding: const EdgeInsets.all(8),
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(item.icon, size: 34, color: Theme.of(context).colorScheme.primary),
                          const SizedBox(height: 8),
                          Text(item.label, textAlign: TextAlign.center),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------- admin (web)

class AdminDashboard extends StatelessWidget {
  const AdminDashboard({super.key, this.extraItems = const <DashboardItem>[]});

  final List<DashboardItem> extraItems;

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      title: 'Admin',
      items: [
        DashboardItem(label: 'Exams', icon: Icons.quiz_outlined, builder: (_) => const ExamsAdminScreen()),
        DashboardItem(label: 'Class results', icon: Icons.assessment_outlined, builder: (_) => const SectionResultsScreen()),
        DashboardItem(label: 'Grade scale', icon: Icons.grade_outlined, builder: (_) => const GradeScaleScreen()),
        DashboardItem(label: 'Fees', icon: Icons.payments_outlined, builder: (_) => const FeesAdminScreen()),
        DashboardItem(label: 'Timetable', icon: Icons.calendar_view_week, builder: (_) => const AdminTimetableScreen()),
        DashboardItem(label: 'Periods', icon: Icons.schedule, builder: (_) => const PeriodsScreen()),
        DashboardItem(label: 'Homework', icon: Icons.menu_book_outlined, builder: (_) => const HomeworkScreen(canManage: true)),
        DashboardItem(label: 'Calendar', icon: Icons.event_outlined, builder: (_) => const CalendarScreen(canManage: true)),
        DashboardItem(
            label: 'Announcements', icon: Icons.campaign_outlined, builder: (_) => const AnnouncementsScreen(canManage: true)),
        DashboardItem(
            label: 'Complaints', icon: Icons.support_agent_outlined, builder: (_) => const ComplaintsScreen(isAdmin: true)),
        ...extraItems,
      ],
    );
  }
}

// ---------------------------------------------------------------- teacher (web and mobile)

class TeacherDashboard extends StatelessWidget {
  const TeacherDashboard({super.key, this.extraItems = const <DashboardItem>[]});

  final List<DashboardItem> extraItems;

  @override
  Widget build(BuildContext context) {
    return DashboardShell(
      title: 'Teacher',
      items: [
        DashboardItem(label: 'Homework', icon: Icons.menu_book_outlined, builder: (_) => const HomeworkScreen(canManage: true)),
        DashboardItem(
          label: 'Exams and marks',
          icon: Icons.edit_note,
          builder: (_) => const ExamBrowserScreen(title: 'Exams and marks', canEnterMarks: true, onlyMine: true),
        ),
        DashboardItem(label: 'Class results', icon: Icons.assessment_outlined, builder: (_) => const SectionResultsScreen()),
        DashboardItem(
          label: 'My timetable',
          icon: Icons.calendar_view_week,
          builder: (_) => TimetableViewScreen(
            title: 'My timetable',
            loader: (api) => api.myWeek(),
            showTeacher: false,
            showSection: true,
          ),
        ),
        DashboardItem(label: 'Calendar', icon: Icons.event_outlined, builder: (_) => const CalendarScreen()),
        DashboardItem(label: 'Announcements', icon: Icons.campaign_outlined, builder: (_) => const AnnouncementsScreen()),
        ...extraItems,
      ],
    );
  }
}

// ---------------------------------------------------------------- student (mobile)

class StudentDashboard extends StatefulWidget {
  const StudentDashboard({super.key, this.extraItems = const <DashboardItem>[]});

  final List<DashboardItem> extraItems;

  @override
  State<StudentDashboard> createState() => _StudentDashboardState();
}

class _StudentDashboardState extends State<StudentDashboard> {
  late Future<StudentItem> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().myStudent();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().myStudent());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<StudentItem>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snap.hasError) return _SignOutScaffold(title: 'Student', body: ErrorView(error: snap.error!, onRetry: _reload));
        final me = snap.data!;
        return DashboardShell(
          title: 'Student',
          header: Text('${me.fullName}  |  ${me.sectionName}'),
          items: [
            DashboardItem(label: 'Homework', icon: Icons.menu_book_outlined, builder: (_) => const HomeworkScreen()),
            DashboardItem(
              label: 'Exam schedule',
              icon: Icons.quiz_outlined,
              builder: (_) => ExamBrowserScreen(title: 'Exam schedule', sectionId: me.sectionId),
            ),
            DashboardItem(label: 'Results', icon: Icons.assessment_outlined, builder: (_) => ResultsScreen(studentId: me.id)),
            DashboardItem(
              label: 'Timetable',
              icon: Icons.calendar_view_week,
              builder: (_) => TimetableViewScreen(title: 'Timetable', loader: (api) => api.myWeek()),
            ),
            DashboardItem(label: 'Calendar', icon: Icons.event_outlined, builder: (_) => const CalendarScreen()),
            DashboardItem(label: 'Announcements', icon: Icons.campaign_outlined, builder: (_) => const AnnouncementsScreen()),
            ...widget.extraItems,
          ],
        );
      },
    );
  }
}

// ---------------------------------------------------------------- parent (mobile)

class ParentDashboard extends StatefulWidget {
  const ParentDashboard({super.key, this.extraItems = const <DashboardItem>[]});

  /// Called by Member 1's modules (attendance, leave) with the child currently selected.
  final List<DashboardItem> extraItems;

  @override
  State<ParentDashboard> createState() => _ParentDashboardState();
}

class _ParentDashboardState extends State<ParentDashboard> {
  late Future<List<StudentItem>> _future;
  String? _childId;

  @override
  void initState() {
    super.initState();
    _future = context.read<OpsApi>().myChildren();
  }

  void _reload() => setState(() => _future = context.read<OpsApi>().myChildren());

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<StudentItem>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snap.hasError) return _SignOutScaffold(title: 'Parent', body: ErrorView(error: snap.error!, onRetry: _reload));
        final children = snap.data!;
        if (children.isEmpty) {
          return const _SignOutScaffold(
            title: 'Parent',
            body: EmptyView('No child is linked to your account yet. Please contact the school office.',
                icon: Icons.child_care),
          );
        }
        final child = children.firstWhere((c) => c.id == _childId, orElse: () => children.first);
        final header = children.length > 1
            ? PickerField<String>(
                label: 'Child',
                value: child.id,
                items: [
                  for (final c in children) DropdownMenuItem<String>(value: c.id, child: Text('${c.fullName} (${c.sectionName})')),
                ],
                onChanged: (v) => setState(() => _childId = v),
              )
            : Text('${child.fullName}  |  ${child.sectionName}');
        return DashboardShell(
          key: ValueKey<String>(child.id),
          title: 'Parent',
          header: header,
          items: [
            DashboardItem(
                label: 'Homework', icon: Icons.menu_book_outlined, builder: (_) => HomeworkScreen(studentId: child.id)),
            DashboardItem(
              label: 'Exam schedule',
              icon: Icons.quiz_outlined,
              builder: (_) => ExamBrowserScreen(title: 'Exam schedule', sectionId: child.sectionId),
            ),
            DashboardItem(label: 'Results', icon: Icons.assessment_outlined, builder: (_) => ResultsScreen(studentId: child.id)),
            DashboardItem(label: 'Fees', icon: Icons.payments_outlined, builder: (_) => FeesScreen(studentId: child.id)),
            DashboardItem(
              label: 'Timetable',
              icon: Icons.calendar_view_week,
              builder: (_) => TimetableViewScreen(title: 'Timetable', loader: (api) => api.studentWeek(child.id)),
            ),
            DashboardItem(label: 'Calendar', icon: Icons.event_outlined, builder: (_) => const CalendarScreen()),
            DashboardItem(label: 'Announcements', icon: Icons.campaign_outlined, builder: (_) => const AnnouncementsScreen()),
            DashboardItem(
                label: 'Complaints', icon: Icons.support_agent_outlined, builder: (_) => const ComplaintsScreen(isAdmin: false)),
            ...widget.extraItems,
          ],
        );
      },
    );
  }
}

/// Error / empty page that still lets the user sign out.
class _SignOutScaffold extends StatelessWidget {
  const _SignOutScaffold({required this.title, required this.body});

  final String title;
  final Widget body;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(title),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => context.read<AuthState>().logout(),
          ),
        ],
      ),
      body: body,
    );
  }
}
