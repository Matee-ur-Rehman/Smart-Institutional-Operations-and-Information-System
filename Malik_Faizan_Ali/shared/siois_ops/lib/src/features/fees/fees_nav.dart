import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'fees_admin_page.dart';
import 'fees_parent_page.dart';

/// Admin manages fees; parents see their children's invoices. Students do not see fees (parents only).
List<NavEntry> feesNav(Role role) {
  switch (role) {
    case Role.admin:
      return <NavEntry>[
        NavEntry(id: 'fees', title: 'Fees', icon: Icons.payments_outlined, group: 'Finance', builder: (context) => const FeesAdminPage()),
      ];
    case Role.parent:
      return <NavEntry>[
        NavEntry(id: 'fees', title: 'Fees', icon: Icons.payments_outlined, group: 'Finance', builder: (context) => const FeesParentPage()),
      ];
    case Role.teacher:
    case Role.student:
      return <NavEntry>[];
  }
}
