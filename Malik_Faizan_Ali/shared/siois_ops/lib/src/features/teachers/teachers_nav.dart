import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'teachers_page.dart';

List<NavEntry> teachersNav(Role role) => role == Role.admin
    ? <NavEntry>[
        NavEntry(id: 'teachers', title: 'Teachers', icon: Icons.badge_outlined, group: 'People', builder: (context) => const TeachersPage()),
      ]
    : <NavEntry>[];
