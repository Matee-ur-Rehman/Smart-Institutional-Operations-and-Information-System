import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'reports_page.dart';

List<NavEntry> reportsNav(Role role) => (role == Role.admin || role == Role.teacher)
    ? <NavEntry>[
        NavEntry(id: 'reports', title: 'Reports', icon: Icons.summarize_outlined, group: 'Academics', builder: (context) => ReportsPage(isAdmin: role == Role.admin)),
      ]
    : <NavEntry>[];
