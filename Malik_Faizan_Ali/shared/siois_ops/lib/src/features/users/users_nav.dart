import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'users_page.dart';

List<NavEntry> usersNav(Role role) => role == Role.admin
    ? <NavEntry>[
        NavEntry(
          id: 'users',
          title: 'User Accounts',
          icon: Icons.manage_accounts_outlined,
          group: 'Administration',
          builder: (context) => const UsersPage(),
        ),
      ]
    : <NavEntry>[];
