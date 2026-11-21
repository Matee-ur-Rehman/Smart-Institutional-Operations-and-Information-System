import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'notifications_page.dart';

List<NavEntry> notificationsNav(Role role) => <NavEntry>[
      NavEntry(id: 'notifications', title: 'Notifications', icon: Icons.notifications_outlined, group: 'Communication', builder: (context) => const NotificationsPage()),
    ];
