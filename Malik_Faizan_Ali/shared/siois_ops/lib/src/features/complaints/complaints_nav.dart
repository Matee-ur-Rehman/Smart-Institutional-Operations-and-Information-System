import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'complaints_page.dart';

/// Parents file complaints / feedback and follow their tickets; the admin handles them.
List<NavEntry> complaintsNav(Role role) {
  switch (role) {
    case Role.admin:
      return <NavEntry>[
        NavEntry(id: 'complaints', title: 'Complaints', icon: Icons.support_agent_outlined, group: 'Communication', builder: (context) => const ComplaintsPage(isAdmin: true)),
      ];
    case Role.parent:
      return <NavEntry>[
        NavEntry(id: 'complaints', title: 'Complaints & Feedback', icon: Icons.support_agent_outlined, group: 'Communication', builder: (context) => const ComplaintsPage(isAdmin: false)),
      ];
    case Role.teacher:
    case Role.student:
      return <NavEntry>[];
  }
}
