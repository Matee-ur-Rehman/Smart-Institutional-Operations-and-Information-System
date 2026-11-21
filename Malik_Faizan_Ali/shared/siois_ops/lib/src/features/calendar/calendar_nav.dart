import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'calendar_page.dart';

/// Everyone sees the school calendar; only the admin edits it.
List<NavEntry> calendarNav(Role role) => <NavEntry>[
      NavEntry(
        id: 'calendar',
        title: 'Calendar',
        icon: Icons.event_outlined,
        group: 'Communication',
        builder: (context) => CalendarPage(isAdmin: role == Role.admin),
      ),
    ];
