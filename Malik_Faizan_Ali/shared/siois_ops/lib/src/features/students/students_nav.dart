import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'students_page.dart';

List<NavEntry> studentsNav(Role role) {
  switch (role) {
    case Role.admin:
      return <NavEntry>[
        NavEntry(id: 'students', title: 'Students', icon: Icons.school_outlined, group: 'People', builder: (context) => const StudentsPage(readOnly: false)),
      ];
    case Role.teacher:
      return <NavEntry>[
        NavEntry(id: 'students', title: 'My Students', icon: Icons.school_outlined, group: 'My Classes', builder: (context) => const StudentsPage(readOnly: true)),
      ];
    case Role.student:
    case Role.parent:
      return <NavEntry>[];
  }
}
