#!/usr/bin/env bash
# One command for everything that can be checked. Run from shared/siois_ops:  bash tool/verify.sh
set -u
fail=0
for t in dartcheck argcheck funccheck; do
  echo "== $t"; python3 tool/$t.py . || fail=1
done
if command -v flutter >/dev/null 2>&1; then
  echo "== flutter pub get";  flutter pub get            || fail=1
  echo "== flutter analyze";  flutter analyze            || fail=1
  echo "== flutter test";     flutter test               || fail=1
  for app in ../../web_app ../../mobile_app; do
    echo "== analyze $app"; (cd "$app" && flutter pub get && flutter analyze) || fail=1
  done
else
  echo "!! flutter not found: only the three python checks ran (they are heuristics, not a compiler)"
  fail=1
fi
exit $fail
