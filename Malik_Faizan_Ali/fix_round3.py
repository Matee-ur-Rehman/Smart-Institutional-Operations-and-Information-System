#!/usr/bin/env python3
"""Run from the SIOIS root (folder with setup.py):   python fix_round3.py
Fix: sidebar unread-notification badge now updates right after 'Mark all as read' / opening a notification."""
import pathlib, sys

p = pathlib.Path("shared/siois_ops/lib/src/features/notifications/notifications_page.dart")
if not p.exists():
    sys.exit("Run this from the SIOIS root folder (where setup.py is).")
s = p.read_text(encoding="utf-8")
orig = s

def swap(old, new, label):
    global s
    if new in s:
        return
    if old not in s:
        sys.exit("Could not find the code for step '%s'. Send me this file's lines 1-80." % label)
    s = s.replace(old, new, 1)

swap("import '../../core/api_client.dart';\n",
     "import '../../app/shell.dart';\nimport '../../core/api_client.dart';\n", "import")

swap("""  Future<void> _readAll() async {
    try {
      await context.read<ApiClient>().post('/notifications/read-all');
      if (mounted) setState(() => _key++);
""", """  Future<void> _readAll() async {
    final shell = context.read<ShellController>();
    try {
      await context.read<ApiClient>().post('/notifications/read-all');
      await shell.refreshUnread();
      if (mounted) setState(() => _key++);
""", "read-all")

swap("""  Future<void> _open(_Note n, Future<void> Function() reload) async {
    if (!n.isRead) {
      try {
        await context.read<ApiClient>().post('/notifications/${n.id}/read');
        await reload();
""", """  Future<void> _open(_Note n, Future<void> Function() reload) async {
    final shell = context.read<ShellController>();
    if (!n.isRead) {
      try {
        await context.read<ApiClient>().post('/notifications/${n.id}/read');
        await shell.refreshUnread();
        await reload();
""", "open")

if s != orig:
    p.write_text(s, encoding="utf-8", newline="")
    print("fixed:", p.as_posix())
else:
    print("nothing to change - already fixed")