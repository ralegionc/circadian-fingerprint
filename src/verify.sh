#!/usr/bin/env bash
# Everything that can be checked without a human looking at the page.
set -u
cd "$(dirname "$0")/.."
fail=0

run () {
  echo
  echo "--- $1 ---"
  shift
  if "$@"; then :; else fail=1; echo "  ^ FAILED"; fi
}

run "build"            python src/build_site.py
run "js syntax"        python src/check_js.py
run "theme tokens"     python src/check_tokens.py
run "chart palette"    python src/check_palette.py
run "headless render"  node src/smoke_dom.js

echo
if [ "$fail" -eq 0 ]; then echo "ALL CHECKS PASSED"; else echo "SOME CHECKS FAILED"; fi
exit "$fail"
