import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'profile_page.dart';

/// Every role has a profile screen.
List<NavEntry> profileNav(Role role) => <NavEntry>[
      NavEntry(id: 'profile', title: 'My Profile', icon: Icons.account_circle_outlined, group: 'Account', builder: (context) => const ProfilePage()),
    ];
