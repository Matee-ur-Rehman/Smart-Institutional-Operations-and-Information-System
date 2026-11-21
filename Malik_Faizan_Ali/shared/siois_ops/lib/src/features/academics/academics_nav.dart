import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'academics_page.dart';

List<NavEntry> academicsNav(Role role) => role == Role.admin
    ? <NavEntry>[
        NavEntry(id: 'academics', title: 'Classes & Subjects', icon: Icons.account_tree_outlined, group: 'Academics', builder: (context) => const AcademicsPage()),
      ]
    : <NavEntry>[];
