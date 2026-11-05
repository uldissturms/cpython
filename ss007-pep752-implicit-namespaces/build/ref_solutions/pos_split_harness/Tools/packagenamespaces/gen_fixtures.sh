#!/bin/bash
# Generate offline fixture indexes for PEP 752 namespace verification.
#
# Usage: gen_fixtures.sh <outdir>
#
# Split layout: the fixture documents live in the sibling _fixtures.py
# helper; this entrypoint only delegates to it.  Pure local computation;
# safe under --network=none.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: gen_fixtures.sh <outdir>" >&2
    exit 2
fi

OUTDIR="$1"
mkdir -p "$OUTDIR"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON="${PYTHON:-python3}"
"$PYTHON" "$SCRIPT_DIR/_fixtures.py" "$OUTDIR"
