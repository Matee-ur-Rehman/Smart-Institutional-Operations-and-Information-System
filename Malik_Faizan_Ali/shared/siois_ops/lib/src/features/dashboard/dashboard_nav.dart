import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'dashboard_page.dart';

/// First entry of every role's menu.
List<NavEntry> dashboardNav(Role role) => <NavEntry>[
      NavEntry(id: 'dashboard', title: 'Dashboard', icon: Icons.dashboard_outlined, builder: (context) => DashboardPage(role: role)),
    ];
