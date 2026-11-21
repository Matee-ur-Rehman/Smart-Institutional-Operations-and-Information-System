import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'announcements_page.dart';

/// Everyone reads announcements; only the admin writes them.
List<NavEntry> announcementsNav(Role role) => <NavEntry>[
      NavEntry(
        id: 'announcements',
        title: 'Announcements',
        icon: Icons.campaign_outlined,
        group: 'Communication',
        builder: (context) => AnnouncementsPage(isAdmin: role == Role.admin),
      ),
    ];
