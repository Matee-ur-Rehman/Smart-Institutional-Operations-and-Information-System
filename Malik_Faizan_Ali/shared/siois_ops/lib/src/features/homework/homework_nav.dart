import 'package:flutter/material.dart';

import '../../core/auth.dart';
import '../../core/nav.dart';
import 'homework_page.dart';

List<NavEntry> homeworkNav(Role role) => <NavEntry>[
      NavEntry(
        id: 'homework',
        title: 'Homework',
        icon: Icons.menu_book_outlined,
        group: 'Academics',
        builder: (context) => HomeworkPage(role: role),
      ),
    ];
