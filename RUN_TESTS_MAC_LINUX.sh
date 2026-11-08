#!/usr/bin/env sh
set -u
cd "$(dirname "$0")" || exit 2
if command -v python3 >/dev/null 2>&1; then
    python3 run_all_tests.py "$@"
else
    echo 'Python 3.10+ is needed. Install it and rerun.' >&2
    exit 2
fi
