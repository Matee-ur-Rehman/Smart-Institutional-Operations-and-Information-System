import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'leave_page.dart';

/// Parents apply; admin and teachers decide; students have no leave screen (their parent applies for them).
List<NavEntry> leaveNav(Role role) {
  switch (role) {
    case Role.admin:
    case Role.teacher:
      return <NavEntry>[
        NavEntry(id: 'leave', title: 'Leave Requests', icon: Icons.event_available_outlined, group: 'Academics', builder: (context) => const LeaveStaffPage()),
      ];
    case Role.parent:
      return <NavEntry>[
        NavEntry(id: 'leave', title: 'Leave', icon: Icons.event_available_outlined, group: 'Academics', builder: (context) => const LeaveParentPage()),
      ];
    case Role.student:
      return <NavEntry>[];
  }
}
