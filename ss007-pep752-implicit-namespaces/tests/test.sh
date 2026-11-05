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
# Fresh verdict files every grade: a repeat grade in one container must
# never inherit the previous run's output.json/probe.json, or a tripped
# gate below would still reward from stale verdicts instead of zero.
rm -f "$LOG_DIR/output.json" "$LOG_DIR/probe.json"

CONFIG="$TESTS_DIR/config.json"
if [ ! -f "$CONFIG" ]; then
    echo "test.sh: $CONFIG missing" >&2
    exit 0
fi

GATE=1

# 0. Tree integrity gate, FIRST -- before anything agent-owned executes.
# The artifact set stages the whole Lib/Tools/Python trees (the two
# package dirs share a basename, so the set cannot name them directly),
# which means a submission's modifications to the test framework, the
# stdlib, or planted files travel with it. This gate closes that
# boundary: every file outside the feature surface must be byte-identical
# to the base tree (hashes pinned in the verifier-owned manifest, which
# the agent's container never sees), and unexpected files are scrubbed
# rather than graded. Bytecode caches are deleted outright -- a crafted
# .pyc could otherwise shadow a verified source. Any mismatch fails
# closed: the suite never runs on a tampered tree and the reward stays 0.
if ! "$PY" -I -S - "$TESTS_DIR/tree_manifest.json" "$REPO" \
    2>"$LOG_DIR/integrity.err" <<'PY'; then
import hashlib
import json
import os
import shutil
import sys

manifest_path, repo = sys.argv[1], sys.argv[2]
try:
    manifest = json.load(open(manifest_path, encoding="utf-8"))
except Exception as exc:
    print(f"integrity: cannot read manifest: {exc}", file=sys.stderr)
    sys.exit(1)
expected = manifest.get("files") or {}
allow = tuple(manifest.get("allow") or ())
gate_dirs = manifest.get("gate_dirs") or ()


def allowed(rel):
    return rel in allow or any(
        rel.startswith(prefix) for prefix in allow
        if prefix.endswith("/"))


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# Bytecode caches first: a crafted .pyc must never shadow a source the
# gate is about to verify.
for gate in gate_dirs:
    for dirpath, dirnames, filenames in os.walk(
            os.path.join(repo, gate)):
        for name in [d for d in dirnames if d == "__pycache__"]:
            shutil.rmtree(os.path.join(dirpath, name), ignore_errors=True)
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                try:
                    os.remove(os.path.join(dirpath, name))
                except OSError:
                    pass

seen = set()
scrubbed = 0
for gate in gate_dirs:
    top = os.path.join(repo, gate)
    for dirpath, dirnames, filenames in os.walk(top):
        dirnames.sort()
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, repo)
            if rel.endswith(".o"):
                # Build product: make regenerates these after the
                # permitted header edit, so they are pinned by no hash
                # (absent from the manifest) and scrubbed by no rule.
                # Pinning them broke repeat grading: the first grade's
                # rebuild invalidated the second grade's gate.
                continue
            if allowed(rel):
                continue
            if rel not in expected:
                # Unexpected file the base tree never had: planted, not
                # graded. Removed (the feature surface is allowlisted
                # above, so nothing legitimate is lost).
                try:
                    os.remove(path)
                    scrubbed += 1
                except OSError as exc:
                    print(f"integrity: cannot scrub {rel}: {exc}",
                          file=sys.stderr)
                    sys.exit(1)
                continue
            seen.add(rel)
            if os.path.islink(path) or not os.path.isfile(path):
                print(f"integrity: {rel} is not a regular file",
                      file=sys.stderr)
                sys.exit(1)
            if sha256_of(path) != expected[rel]:
                print(f"integrity: {rel} differs from the base tree",
                      file=sys.stderr)
                sys.exit(1)
missing = sorted(set(expected) - seen)
if missing:
    print(f"integrity: {len(missing)} base file(s) missing, "
          f"e.g. {missing[0]}", file=sys.stderr)
    sys.exit(1)
print(f"integrity: {len(seen)} files verified, {scrubbed} scrubbed",
      file=sys.stderr)
PY
    echo "test.sh: tree integrity gate failed; see integrity.err" >&2
    GATE=0
fi

# 1. Install the graded tests idempotently (MSL may also apply test_patch;
#    applying twice must not fail the run). Already-applied is detected by
#    CONTENT -- the patch must reverse-apply cleanly -- never by the mere
#    existence of a sentinel file, which a planted fake would satisfy.
#    Otherwise any planted files at the patch's new-file paths are removed
#    and the genuine patch is applied fresh; a patch that still does not
#    apply fails closed.
INSTALL_OK=0
if [ "$GATE" = 1 ]; then
if "$PY" -I -S - "$CONFIG" "$REPO" <<'PY' 2>"$LOG_DIR/testpatch.err"
import json
import os
import subprocess
import sys

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


def run_git(args):
    return subprocess.run(
        ["git", *args, "-"],
        input=patch.encode(), cwd=repo,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def scrub_new_files():
    # Remove planted files at exactly the new-file paths this patch
    # creates (a `--- /dev/null` line followed by its `+++ b/...`
    # line), so a fake test file can neither satisfy the install nor
    # shadow the genuine one. Modified-file entries are never touched.
    lines = patch.splitlines()
    removed = 0
    for i, line in enumerate(lines):
        if line == "--- /dev/null" and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt.startswith("+++ b/"):
                target = os.path.join(repo, nxt[len("+++ b/"):])
                try:
                    if os.path.islink(target) or os.path.isfile(target):
                        os.remove(target)
                        removed += 1
                except OSError as exc:
                    print(f"test_patch: cannot scrub {target}: {exc}",
                          file=sys.stderr)
    return removed


proc = run_git(["apply", "--check", "--reverse", "--verbose"])
if proc.returncode == 0:
    print("test_patch: already applied (reverse-applies cleanly)",
          file=sys.stderr)
    sys.exit(0)
scrubbed = scrub_new_files()
if scrubbed:
    print(f"test_patch: scrubbed {scrubbed} planted file(s)",
          file=sys.stderr)
proc = run_git(["apply", "--verbose"])
sys.stdout.write(proc.stdout.decode("utf-8", "replace"))
if proc.returncode != 0:
    print("test_patch: does not apply after scrubbing", file=sys.stderr)
sys.exit(proc.returncode)
PY
then
    INSTALL_OK=1
fi
fi
if [ "$INSTALL_OK" != 1 ]; then
    echo "test.sh: test_patch install failed; grading zero" >&2
    GATE=0
fi

# 1.5. Privilege separation, BEFORE anything agent-owned executes. Every
# step below that touches submitted code -- the make/install in
# run_script.sh (the Makefile is agent-edited), the suite itself, and
# the probe's check grandchildren -- runs UNPRIVILEGED as nobody, while
# the verifier-owned readers stay root-owned and read-only and the
# verdict paths stay root-owned. Submitted code can read the readers it
# is graded by but never write them, so neither scoring channel's
# reader is writable by the code it grades. The repo tree (which the
# unprivileged make must rebuild and install from) is handed to nobody
# only after the integrity gate above scrubbed it as root.
HARNESS_SHA="$LOG_DIR/harness.sha256"
if [ "$GATE" = 1 ]; then
    if ! command -v setpriv >/dev/null 2>&1; then
        echo "test.sh: setpriv missing; cannot drop privileges" >&2
        GATE=0
    elif ! (cd "$TESTS_DIR" && sha256sum test.sh run_script.sh parser.py \
            probe.py config.json tree_manifest.json > "$HARNESS_SHA"); then
        echo "test.sh: cannot snapshot harness files" >&2
        GATE=0
    elif ! chmod -R a-w "$TESTS_DIR"; then
        echo "test.sh: cannot lock harness files read-only" >&2
        GATE=0
    elif ! mkdir -p /tmp/lambo-grade-home \
            || ! chown nobody:nogroup /tmp/lambo-grade-home; then
        echo "test.sh: cannot stage the unprivileged home" >&2
        GATE=0
    elif ! chown -R nobody:nogroup "$REPO"; then
        echo "test.sh: cannot hand the repo to the grade user" >&2
        GATE=0
    fi
fi

if [ "$GATE" = 1 ]; then
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
# id. The probe itself splits in three: a check child runs the checks in
# the assured tree interpreter (absolute path, -I -S, neutral cwd,
# scrubbed environment, UNPRIVILEGED via setpriv nobody; run_script.sh
# relinked it when it was not an ELF binary) from the verifier-owned
# /tests tree and prints one marked result line; an attestation
# grandchild that never imports agent code prints ground-truth check
# hashes; while the parent -- which never imports agent code and itself
# runs under the verifier-owned $PY, never the tree's binary -- demands
# the child's per-check digests equal the grandchild's (a check swapped
# for a no-op under a trace hook has different bytecode) and writes the
# verdict file after both have exited, so a shutdown hook the child
# armed cannot rewrite it afterwards. A missing, unreadable, or
# parent-rejected probe payload fails closed in step 4.
rm -f "$LOG_DIR/probe.json"
(cd / && env -u PYTHONPATH PYTHONSAFEPATH=1 "$PY" -I -S \
    "$TESTS_DIR/probe.py" "$REPO" "$LOG_DIR/probe.json" \
    2>"$LOG_DIR/probe.err") || true

# 2.6. Reader re-verification: the suite and the probe grandchildren
# just ran submitted code. The uid boundary above already makes the
# readers unwritable by it; this snapshot comparison is the second
# layer, so a drift through any unforeseen path fails closed instead
# of parsing or rewarding from tampered code. (The verdict files were
# removed up front, so a trip here grades from no verdicts: zero.)
if ! (cd "$TESTS_DIR" && sha256sum -c "$HARNESS_SHA" \
        >/dev/null 2>"$LOG_DIR/harness.err"); then
    echo "test.sh: harness files drifted during grading; see harness.err" >&2
    GATE=0
fi

if [ "$GATE" = 1 ]; then
# 3. Parse the raw output with the grader's interpreter (never the repo's:
#    the agent owns that tree).  -I -S drops PYTHONPATH, cwd and site so a
#    sitecustomize shim cannot silence the parser.
"$PY" -I -S "$TESTS_DIR/parser.py" \
    "$LOG_DIR/test-stdout.txt" "$LOG_DIR/test-stderr.txt" \
    "$LOG_DIR/output.json" 2>"$LOG_DIR/parser.err" || true
fi
fi

# 4. Reward 1 iff every required id is present with status PASSED AND the
# independent probe passed. Either channel alone is insufficient: a forged
# JUnit report fails the probe, and a suite failure fails the id check.
# A tripped integrity gate or a failed test install skips straight here
# with no verdicts, which grades 0.
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
