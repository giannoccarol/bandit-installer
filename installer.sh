#!/bin/sh
# Android installer for the Nokia Lumia 1520 (bandit), Linux launcher.
# Options are passed through, for example: ./installer.sh --lang it --text
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3 || command -v python)"
[ -n "$PY" ] || { echo "Python 3 is needed (python3)."; exit 1; }
exec "$PY" -B installer.py "$@"
