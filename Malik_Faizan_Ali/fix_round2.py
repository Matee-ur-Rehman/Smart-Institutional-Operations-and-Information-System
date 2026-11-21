#!/usr/bin/env python3
"""Run from the SIOIS root (the folder that contains setup.py):   python fix_round2.py
Applies exact, minimal fixes to shared/siois_ops/lib/src. Safe to run twice (it only changes what is still wrong)."""
import pathlib, re, sys

SRC = pathlib.Path("shared/siois_ops/lib/src")
if not SRC.is_dir():
    sys.exit("Run this from the SIOIS root folder (where setup.py is).")
changed = []

def edit(path, fn):
    p = SRC / path
    s = p.read_text(encoding="utf-8")
    t = fn(s)
    if t != s:
        p.write_text(t, encoding="utf-8", newline="")
        changed.append(path)

# 1) setState(() => _x = <Future>) throws "setState() callback argument returned a Future"
fut = re.compile(r"setState\(\(\) => (_\w+ = (?:[A-Za-z_.<>()]*?(?:sections\([^()]*\)|_load\w*\(\)|\bf\b)))\)")
for f in SRC.rglob("*.dart"):
    edit(f.relative_to(SRC).as_posix(), lambda s: fut.sub(lambda m: "setState(() { " + m.group(1) + "; })", s))

# 2) leave endpoints are /leave-requests on the backend
leave = re.compile(r"'/leave(?=['/])")
for rel in ("features/leave/leave_page.dart", "features/dashboard/dashboard_page.dart"):
    edit(rel, lambda s: leave.sub("'/leave-requests", s))

# 3) timetable grid: stretch Row inside a vertical scroll view needs IntrinsicHeight
def grid(s):
    a = "      rows.add(Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: ["
    b = "        for (var d = 1; d <= 6; d++) _cell(context, d, p),\n      ]));"
    if a in s and b in s:
        s = s.replace(a, "      rows.add(IntrinsicHeight(child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [")
        s = s.replace(b, "        for (var d = 1; d <= 6; d++) _cell(context, d, p),\n      ])));")
    return s
edit("features/timetable/timetable_grid.dart", grid)

# 4) one sidebar "Academics" block: Reports before Calendar
edit("features/registry.dart", lambda s: s.replace(
    "      ...calendarNav(role),\n      ...reportsNav(role),\n",
    "      ...reportsNav(role),\n      ...calendarNav(role),\n"))

print("changed %d file(s):" % len(changed))
for c in changed:
    print("  ", c)
if not changed:
    print("nothing to change - already fixed")