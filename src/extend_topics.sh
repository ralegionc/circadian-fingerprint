#!/usr/bin/env bash
# Extend the per-article topic window from two weeks to four, one project at a
# time. dumps.wikimedia.org asks for low concurrency, so these run sequentially
# at two workers each rather than in parallel.
set -u
cd "$(dirname "$0")/.."

echo "=== en 2025-09-15 .. 2025-09-28 ==="
python src/fetch_pageview_dumps.py 2025-09-15 2025-09-28 --workers 2

echo
echo "=== ja 2025-09-15 .. 2025-09-28 ==="
CF_PROJECT=ja python src/fetch_pageview_dumps.py 2025-09-15 2025-09-28 --workers 2

echo
echo "ALL DONE"
