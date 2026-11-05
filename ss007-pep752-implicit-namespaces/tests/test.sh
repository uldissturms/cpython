#!/bin/bash
# Grade one trial: install test_patch, run the suite, derive reward from data.
#
# The reward is computed from TWO data channels: the parser's per-test
# verdicts compared against this unit's fail_to_pass/pass_to_pass lists,
# AND the independent probe's pass/fail payload -- never from a process
# exit status, which agent code running inside the suite could forge.  A
# zero reward is written BEFORE the parser runs, so a parser that dies
# leaves a zero rather than nothing.
REPO=/app
[ -d "$REPO" ] || REPO=/testbed
TESTS_DIR=/tests
LOG_DIR=/logs/verifier
PY=/usr/bin/python3

mkdir -p "$LOG_DIR"
printf '0' > "$LOG_DIR/reward.txt"
printf '{"reward": 0.0}' > "$LOG_DIR/reward.json"

CONFIG="$TESTS_DIR/config.json"
if [ ! -f "$CONFIG" ]; then
    echo "test.sh: $CONFIG missing" >&2
    exit 0
fi

# 1. Install the graded tests idempotently (MSL may also apply test_patch;
#    applying twice must not fail the run).
"$PY" -I -S - "$CONFIG" "$REPO" <<'PY' 2>"$LOG_DIR/testpatch.err" || true
import json, subprocess, sys

config_path, repo = sys.argv[1], sys.argv[2]
try:
    cfg = json.load(open(config_path, encoding="utf-8"))
except Exception as exc:
    print(f"test_patch: cannot read config: {exc}", file=sys.stderr)
    sys.exit(1)
patch = cfg.get("test_patch") or ""
if not patch.strip():
    print("test_patch: empty, nothing to install", file=sys.stderr)
    sys.exit(0)
proc = subprocess.run(
    ["git", "apply", "--check", "--verbose", "-"],
    input=patch.encode(), cwd=repo,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
if proc.returncode == 0:
    proc = subprocess.run(
        ["git", "apply", "--verbose", "-"],
        input=patch.encode(), cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sys.stdout.write(proc.stdout.decode("utf-8", "replace"))
    sys.exit(proc.returncode)
sentinel = "Lib/test/test_pep752_naming.py"
import os
if os.path.exists(os.path.join(repo, sentinel)):
    print("test_patch: already applied (sentinel present)", file=sys.stderr)
    sys.exit(0)
print("test_patch: does not apply and sentinel is missing", file=sys.stderr)
sys.exit(1)
PY

# 2. Run the suite; the runner's exit status is data, not a verdict.
SELECTED="$("$PY" -I -S - "$CONFIG" <<'PY' 2>/dev/null || true
import json, sys
try:
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception:
    sys.exit(0)
files = cfg.get("selected_test_files_to_run") or []
if isinstance(files, str):
    files = [files]
print(" ".join(f for f in files if isinstance(f, str)))
PY
)"
# shellcheck disable=SC2086
bash "$TESTS_DIR/run_script.sh" $SELECTED \
    >"$LOG_DIR/test-stdout.txt" 2>"$LOG_DIR/test-stderr.txt" || true

# Keep the runner-written report next to the logs for forensics; the parser
# reads the original, never this copy.
cp -f "${LAMBO_JUNIT_XML:-/tmp/lambo-junit.xml}" "$LOG_DIR/junit.xml" 2>/dev/null || true

# 2.5. Independent behavioral probe: the second reward channel. The suite
# above runs agent code in-process, which can rewrite the JUnit report
# after a genuine failing run (an atexit hook suffices), so a report-only
# grader scores a forgery. The probe re-checks the specified behaviors and
# never reads the report; reward needs the probe AND every required suite
# id. The probe itself splits in two: a child runs the checks in the
# assured tree interpreter (absolute path, -I -S, neutral cwd, scrubbed
# environment; run_script.sh relinked it when it was not an ELF binary)
# from the verifier-owned /tests tree and prints one marked result line,
# while the parent -- which never imports agent code and itself runs under
# the verifier-owned $PY, never the tree's binary -- writes the verdict
# file after the child has exited, so a shutdown hook the child armed
# cannot rewrite it afterwards. A missing, unreadable, or parent-rejected
# probe payload fails closed in step 4.
rm -f "$LOG_DIR/probe.json"
(cd / && env -u PYTHONPATH PYTHONSAFEPATH=1 "$PY" -I -S \
    "$TESTS_DIR/probe.py" "$REPO" "$LOG_DIR/probe.json" \
    2>"$LOG_DIR/probe.err") || true

# 3. Parse the raw output with the grader's interpreter (never the repo's:
#    the agent owns that tree).  -I -S drops PYTHONPATH, cwd and site so a
#    sitecustomize shim cannot silence the parser.
"$PY" -I -S "$TESTS_DIR/parser.py" \
    "$LOG_DIR/test-stdout.txt" "$LOG_DIR/test-stderr.txt" \
    "$LOG_DIR/output.json" 2>"$LOG_DIR/parser.err" || true

# 4. Reward 1 iff every required id is present with status PASSED AND the
# independent probe passed. Either channel alone is insufficient: a forged
# JUnit report fails the probe, and a suite failure fails the id check.
"$PY" -I -S - "$CONFIG" "$LOG_DIR" <<'PY' 2>"$LOG_DIR/reward.err" || true
import json, os, sys

config_path, log_dir = sys.argv[1], sys.argv[2]

def load(path, default):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        print(f"reward: cannot read {path}: {exc}", file=sys.stderr)
        return default

cfg = load(config_path, {})
required = list(cfg.get("fail_to_pass") or []) + list(cfg.get("pass_to_pass") or [])
got = load(os.path.join(log_dir, "output.json"), {})
status = {t.get("name"): t.get("status") for t in got.get("tests", [])}
probe = load(os.path.join(log_dir, "probe.json"), {})
probe_passed = probe.get("passed") is True
if not probe_passed:
    print(f"reward: probe did not pass: {probe.get('failed', '?')}",
          file=sys.stderr)

reward = 0.0
if required and probe_passed and all(status.get(t) == "PASSED" for t in required):
    reward = 1.0

with open(os.path.join(log_dir, "reward.txt"), "w", encoding="utf-8") as handle:
    handle.write(str(int(reward)))
with open(os.path.join(log_dir, "reward.json"), "w", encoding="utf-8") as handle:
    json.dump({"reward": reward}, handle)

def ctrf_status(s):
    return {"PASSED": "passed", "FAILED": "failed", "ERROR": "failed",
            "SKIPPED": "skipped"}.get(s, "other")

results = [
    {"name": t, "status": ctrf_status(status.get(t, "other")),
     "required": True}
    for t in required
]
passed = sum(1 for r in results if r["status"] == "passed")
failed = sum(1 for r in results if r["status"] == "failed")
other = len(results) - passed - failed
with open(os.path.join(log_dir, "ctrf.json"), "w", encoding="utf-8") as handle:
    json.dump({"results": {"summary": {"tests": len(results), "passed": passed,
                                       "failed": failed, "skipped": 0,
                                       "pending": 0, "other": other},
                             "tests": results}}, handle, indent=2)
print(f"reward: {reward} ({passed}/{len(required)} required passing)")
PY

exit 0
