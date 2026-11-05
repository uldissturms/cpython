#!/bin/bash
# status: task-specific (ss007-pep752-implicit-namespaces) — stdlib-trace LCOV backend.
# In: task dir + output dir. Out: coverage.lcov + warnings.txt + suite.txt.
#
# Shape: repo-based CPython task. Golden = steps/1_pep752/solution/solve.sh
# applied onto the base commit in /app; grader = six Lib/test/test_pep752_*.py
# modules installed from config.json test_patch, run under the Joules-built
# /app/python. No network inside the measurement container: stdlib `trace`
# only (coverage.py would need a pip install the box cannot do).
#
# Known undercount (documented, not hidden): tests that shell out to
# `python -m packagenamespaces` run outside the traced process, so entrypoint
# lines read 0 even when the entrypoint test passes. Listed in warnings.txt.
#
# v2 (2026-11-04 review): runs steps/1_pep752/tests/test.sh before the traced
# suite (mirror of build/run_coverage.sh) so the InstallTests see the DESTDIR
# install. Without it the suite reads 99/101 and the 2 failures are backend
# environment, not golden defects.
set -uo pipefail

TASKDIR="${1:?task dir}"; OUT="${2:?output dir}"
STEP=1_pep752
IMG=ss007-pep752-coverage:v1
LIMITS="--cpus=4 --memory=8192m --memory-swap=8192m"

mkdir -p "$OUT"
: > "$OUT/warnings.txt"

if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  echo "backend: image $IMG missing; cannot measure" >&2
  exit 1
fi

# shellcheck disable=SC2086
CID="$(docker run -d --rm $LIMITS "$IMG" sleep 3600)" || {
  echo "backend: cannot start container" >&2; exit 1
}
cleanup() { docker rm -f "$CID" >/dev/null 2>&1; }
trap cleanup EXIT

docker exec "$CID" bash -c 'rm -rf /solution && mkdir -p /solution' >/dev/null 2>&1
docker cp "$TASKDIR/steps/$STEP/solution/." "$CID:/solution/" >/dev/null 2>&1
docker cp "$TASKDIR/steps/$STEP/tests/." "$CID:/tests/" >/dev/null 2>&1
docker exec "$CID" bash /solution/solve.sh >/dev/null 2>&1 || {
  echo "backend: solve.sh failed" >&2; exit 1
}
# Run the real test.sh first (mirror of build/run_coverage.sh): it performs the
# DESTDIR install the InstallTests assert on. Non-fatal; the traced suite below
# is the pass/fail signal.
docker exec "$CID" bash /tests/test.sh >/dev/null 2>&1 || {
  echo "backend: test.sh rc=$? (continuing)" >&2
}
# Ensure the graded tests are present (test.sh installs them idempotently).
if ! docker exec "$CID" test -f /app/Lib/test/test_pep752_naming.py >/dev/null 2>&1; then
python3 - "$TASKDIR/steps/$STEP/tests/config.json" > "$OUT/test_patch.diff" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1], encoding="utf-8"))
sys.stdout.write(cfg.get("test_patch") or "")
PY
docker cp "$OUT/test_patch.diff" "$CID:/tmp/test_patch.diff" >/dev/null 2>&1
docker exec "$CID" bash -c 'git -C /app apply --verbose - < /tmp/test_patch.diff' >/dev/null 2>&1 || {
  echo "backend: test_patch does not apply" >&2; exit 1
}
fi

docker exec -i "$CID" ./python - <<'PY' > "$OUT/trace.json"
import json, sys, trace, unittest
sys.path.insert(0, "/app/Lib/test")
modules = ["test_pep752_naming", "test_pep752_semantics", "test_pep752_uploads",
           "test_pep752_metadata", "test_pep752_policy", "test_pep752_tooling"]
result = {}
def run_suite():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite(loader.loadTestsFromName(m) for m in modules)
    with open("/dev/null", "w") as devnull:
        res = unittest.TextTestRunner(stream=devnull, verbosity=0).run(suite)
    result["ran"] = res.testsRun
    result["failures"] = len(res.failures)
    result["errors"] = len(res.errors)
    result["skipped"] = len(res.skipped)
tracer = trace.Trace(count=1, trace=0)
tracer.runfunc(run_suite)
counts = tracer.results().counts
out = {"result": result, "counts": [
    {"file": f, "line": n, "hits": c} for (f, n), c in counts.items()]}
json.dump(out, sys.stdout)
PY

# Convert trace counts to LCOV on the host (needs the golden sources).
rm -rf "$OUT/src" && mkdir -p "$OUT/src"
docker cp "$CID:/app/Lib/packagenamespaces/." "$OUT/src/" >/dev/null 2>&1
python3 - "$OUT/trace.json" "$OUT/src" "$OUT/coverage.lcov" "$OUT/suite.txt" <<'PY'
import dis, json, os, sys

trace_path, srcdir, lcov_path, suite_path = sys.argv[1:5]
data = json.load(open(trace_path, encoding="utf-8"))
res = data["result"]
with open(suite_path, "w", encoding="utf-8") as fh:
    fh.write(json.dumps(res, indent=2) + "\n")

hits = {}
for entry in data["counts"]:
    hits.setdefault(entry["file"], {})[entry["line"]] = entry["hits"]

def executable_lines(path):
    with open(path, encoding="utf-8") as handle:
        tree = compile(handle.read(), path, "exec")
    seen = set()
    stack = [tree]
    while stack:
        code = stack.pop()
        for _offset, lineno in dis.findlinestarts(code):
            seen.add(lineno)
        stack.extend(c for c in code.co_consts if hasattr(c, "co_code"))
    return seen

total_hit = total_lines = 0
with open(lcov_path, "w", encoding="utf-8") as lcov:
    lcov.write("TN:ss007-covreview\n")
    for name in sorted(os.listdir(srcdir)):
        if not name.endswith(".py"):
            continue
        full = "/app/Lib/packagenamespaces/" + name
        exe = executable_lines(os.path.join(srcdir, name))
        file_hits = hits.get(full, {})
        covered = sum(1 for n in exe if file_hits.get(n, 0) > 0)
        total_hit += covered
        total_lines += len(exe)
        lcov.write(f"SF:{full}\n")
        for n in sorted(exe):
            lcov.write(f"DA:{n},{file_hits.get(n, 0)}\n")
        lcov.write(f"LF:{len(exe)}\nLH:{covered}\nend_of_record\n")
print(f"lcov: files emitted, lines={total_lines} covered={total_hit}")
print(f"suite: ran={res['ran']} failures={res['failures']} "
      f"errors={res['errors']} skipped={res.get('skipped', 0)}")
PY

{
  echo "entrypoint blind spot: tests shell out to 'python -m packagenamespaces' in a"
  echo "subprocess the stdlib trace module cannot follow, so __main__.py lines read 0"
  echo "even when the entrypoint test passes. Line-only backend: branch % n/a."
} >> "$OUT/warnings.txt"
echo "backend done: $OUT/coverage.lcov"
