import 'package:flutter/material.dart';

import 'auth.dart';

/// One sidebar / drawer item. Every feature folder exposes a `List<NavEntry> <feature>Nav(Role role)`
/// function (see features/registry.dart); an empty list means "this role has no screen for this module".
class NavEntry {
  const NavEntry({required this.id, required this.title, required this.icon, required this.builder, this.group});

  /// Stable id (e.g. `homework`, `notifications`).
  final String id;
  final String title;
  final IconData icon;
  final WidgetBuilder builder;

  /// Optional sidebar section heading (e.g. "Academics", "Administration").
  final String? group;
}

typedef NavBuilder = List<NavEntry> Function(Role role);
