import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'timetable_page.dart';

List<NavEntry> timetableNav(Role role) => <NavEntry>[
      NavEntry(id: 'timetable', title: 'Timetable', icon: Icons.calendar_view_week_outlined, group: 'Academics', builder: (context) => TimetablePage(role: role)),
    ];
