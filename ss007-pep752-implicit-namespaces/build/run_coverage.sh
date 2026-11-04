#!/bin/bash
# Golden-patch coverage: which added lines the graded tests execute.
#
# Prints one line: COVERAGE [<unit>] <pct>.  The denominator is the added
# executable Python lines of the golden patch under Lib/packagenamespaces/
# (shell scripts and docs are behaviorally covered by the harness and docs
# tests, not line-measured).  Threshold is 80%.
set -uo pipefail

TASKDIR="$(cd "$(dirname "$0")/.." && pwd)"
TASK=ss007-pep752-implicit-namespaces
PLUGIN_ROOT=/home/uldis/cpython/.autopilot/portfolios/accepted-peps-cpython/runtime/62e711dad94714a3c723dc92603cc6cd5599b8859c21abdf532f0b112f43b4d9/lambo-express/skills/lh-create-swe-single-turn/scripts/taskbuild.sh
IMG=ss007-pep752-coverage:v1
STEP=1_pep752
BASE=416e8d89f57ac39f0ca8187dc6bc44f5f6ff994c
LIMITS="--cpus=4 --memory=8192m --memory-swap=8192m"

"$PLUGIN_ROOT" "$TASK" \
    -t "$IMG" -f "$TASKDIR/environment/Dockerfile" "$TASKDIR/environment" \
    >"$TASKDIR/build/.coverage-build.log" 2>&1 || {
    echo "run_coverage: image build failed; see build/.coverage-build.log" >&2
    exit 1
}

# shellcheck disable=SC2086
CID="$(docker run -d --rm $LIMITS "$IMG" sleep 3600)" || {
    echo "run_coverage: cannot start container" >&2
    exit 1
}
cleanup() { docker rm -f "$CID" >/dev/null 2>&1; }
trap cleanup EXIT

docker cp "$TASKDIR/steps/$STEP/tests/." "$CID:/tests/" >/dev/null 2>&1
docker exec "$CID" bash -c 'rm -rf /solution && mkdir -p /solution' >/dev/null 2>&1
docker cp "$TASKDIR/steps/$STEP/solution/." "$CID:/solution/" >/dev/null 2>&1
docker exec "$CID" bash /solution/solve.sh >/dev/null 2>&1 || {
    echo "run_coverage: solve.sh failed" >&2
    exit 1
}
# Install the graded tests the same way test.sh does.
docker exec "$CID" bash /tests/test.sh >/dev/null 2>&1 || true

docker exec -i "$CID" ./python - "$BASE" "$STEP" <<'PY'
import subprocess
import sys
import trace
import unittest

base = sys.argv[1]
unit = sys.argv[2]

# Added lines per package file: tracked hunks from the uncommitted golden
# diff, plus every code line of untracked files (git diff skips those).
diff = subprocess.run(
    ["git", "-C", "/app", "diff", base, "--", "Lib/packagenamespaces"],
    capture_output=True, text=True, check=True).stdout
added = {}
current = None
lineno = 0
for line in diff.splitlines():
    if line.startswith("+++ b/"):
        current = line[len("+++ b/"):]
        added[current] = set()
    elif line.startswith("@@ "):
        # @@ -a,b +c,d @@
        plus = line.split("+")[1]
        lineno = int(plus.split(",")[0])
    elif current is not None and line.startswith("+") and not line.startswith("+++"):
        code = line[1:].strip()
        if code and not code.startswith("#"):
            added[current].add(lineno)
        lineno += 1
    elif current is not None and not line.startswith("-"):
        lineno += 1
untracked = subprocess.run(
    ["git", "-C", "/app", "ls-files", "--others", "--exclude-standard",
     "--", "Lib/packagenamespaces"],
    capture_output=True, text=True, check=True).stdout.split()
for path in untracked:
    if not path.endswith(".py"):
        continue
    lines = set()
    with open("/app/" + path, encoding="utf-8") as handle:
        for number, text in enumerate(handle, 1):
            code = text.strip()
            if code and not code.startswith("#"):
                lines.add(number)
    added[path] = lines

sys.path.insert(0, "/app/Lib/test")
modules = ["test_pep752_naming", "test_pep752_semantics", "test_pep752_uploads",
           "test_pep752_metadata", "test_pep752_policy", "test_pep752_tooling"]

def run_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(m) for m in modules)
    with open("/dev/null", "w") as devnull:
        unittest.TextTestRunner(stream=devnull, verbosity=0).run(suite)

tracer = trace.Trace(count=1, trace=0)
tracer.runfunc(run_suite)
counts = tracer.results().counts

import dis

def executable_lines(path):
    with open("/app/" + path, encoding="utf-8") as handle:
        tree = compile(handle.read(), path, "exec")
    seen = set()
    stack = [tree]
    while stack:
        code = stack.pop()
        for _offset, lineno in dis.findlinestarts(code):
            seen.add(lineno)
        stack.extend(c for c in code.co_consts if hasattr(c, "co_code"))
    return seen

covered = 0
total = 0
for path, lines in sorted(added.items()):
    full = "/app/" + path
    hit = {n for (f, n) in counts if f == full}
    runnable = lines & executable_lines(path)
    got = runnable & hit
    covered += len(got)
    total += len(runnable)
    missing = sorted(runnable - hit)
    print(f"coverage: {path}: {len(got)}/{len(runnable)}"
          + (f" missing={missing[:12]}" if missing else ""), file=sys.stderr)

pct = (100.0 * covered / total) if total else 0.0
print(f"COVERAGE {unit} {pct:.1f}")
PY
