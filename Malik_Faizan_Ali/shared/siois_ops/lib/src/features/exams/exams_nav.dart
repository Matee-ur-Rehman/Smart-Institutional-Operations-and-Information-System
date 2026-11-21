import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'exams_list_page.dart';
import 'exams_view_page.dart';

List<NavEntry> examsNav(Role role) {
  switch (role) {
    case Role.admin:
    case Role.teacher:
      return <NavEntry>[
        NavEntry(id: 'exams', title: 'Exams & Results', icon: Icons.assignment_outlined, group: 'Academics', builder: (context) => ExamsListPage(isAdmin: role == Role.admin)),
      ];
    case Role.student:
    case Role.parent:
      return <NavEntry>[
        NavEntry(id: 'exams', title: 'Exams & Results', icon: Icons.assignment_outlined, group: 'Academics', builder: (context) => const ExamsViewPage()),
      ];
  }
}
