import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'parents_page.dart';

List<NavEntry> parentsNav(Role role) => role == Role.admin
    ? <NavEntry>[
        NavEntry(id: 'parents', title: 'Parents', icon: Icons.family_restroom_outlined, group: 'People', builder: (context) => const ParentsPage()),
      ]
    : <NavEntry>[];
