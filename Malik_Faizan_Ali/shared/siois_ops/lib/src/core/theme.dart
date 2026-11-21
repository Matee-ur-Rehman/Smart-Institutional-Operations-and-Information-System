import 'package:flutter/material.dart';

/// Brand palette: deep teal (trust, education) with a warm amber accent.
class Brand {
  static const Color primary = Color(0xFF0F766E);
  static const Color primaryDark = Color(0xFF134E4A);
  static const Color accent = Color(0xFFF59E0B);
  static const Color surfaceTint = Color(0xFFF1F5F4);
  static const Color success = Color(0xFF15803D);
  static const Color warning = Color(0xFFB45309);
  static const Color danger = Color(0xFFB91C1C);
  static const Color info = Color(0xFF1D4ED8);
  static const Color muted = Color(0xFF64748B);
}

ThemeData buildTheme(Brightness brightness) {
  final scheme = ColorScheme.fromSeed(seedColor: Brand.primary, brightness: brightness);
  final isLight = brightness == Brightness.light;
  final border = OutlineInputBorder(borderRadius: BorderRadius.circular(10));
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: isLight ? const Color(0xFFF6F8F8) : null,
    visualDensity: VisualDensity.adaptivePlatformDensity,
    appBarTheme: AppBarTheme(
      centerTitle: false,
      elevation: 0,
      scrolledUnderElevation: 1,
      backgroundColor: isLight ? Colors.white : null,
      foregroundColor: isLight ? const Color(0xFF0F172A) : null,
    ),
    cardTheme: CardThemeData(
      elevation: 0,
      color: isLight ? Colors.white : null,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: scheme.outlineVariant),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      border: border,
      enabledBorder: border.copyWith(borderSide: BorderSide(color: scheme.outlineVariant)),
      isDense: true,
      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      filled: true,
      fillColor: isLight ? Colors.white : null,
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(64, 44),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(64, 44),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    ),
    chipTheme: ChipThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      side: BorderSide.none,
    ),
    dividerTheme: DividerThemeData(color: scheme.outlineVariant, space: 1),
    dialogTheme: DialogThemeData(shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
  );
}
