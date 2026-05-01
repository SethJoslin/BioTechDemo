#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PYTHONPATH=. "${PYTHONPATH:-python}" -m pytest -q tests || exit $?
