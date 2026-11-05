#!/bin/bash
# Control harness: probe the reward signal with known-good/known-bad trees.
#
# Prints RAW REWARDS only -- no verdicts.  The controls gate applies the
# policy itself (pos -> 1, neg -> 0, twice -> identical).
#
#   CONTROL-BEGIN <kind> <name>     before each control runs
#   CONTROL pos <name> reward=<r>   correct but differently written
#   CONTROL neg <name> reward=<r>   wrong / gaming / no-op
#   CONTROL twice <unit> reward=<a>,<b>  same state graded twice
set -uo pipefail

TASKDIR="$(cd "$(dirname "$0")/.." && pwd)"
TASK=ss007-pep752-implicit-namespaces
PLUGIN_ROOT=/home/uldis/cpython/.autopilot/portfolios/accepted-peps-cpython/runtime/62e711dad94714a3c723dc92603cc6cd5599b8859c21abdf532f0b112f43b4d9/lambo-express
IMG=ss007-pep752-controls:v1
STEP=1_pep752
# The task's declared shape (task.toml [environment]); never above 4/8192.
LIMITS="--cpus=4 --memory=8192m --memory-swap=8192m"

"$PLUGIN_ROOT/skills/lh-create-swe-single-turn/scripts/taskbuild.sh" "$TASK" \
    -t "$IMG" -f "$TASKDIR/environment/Dockerfile" "$TASKDIR/environment" \
    >"$TASKDIR/build/.controls-build.log" 2>&1 || {
    echo "run_controls: image build failed; see build/.controls-build.log" >&2
    exit 1
}

stage_and_solve() {
    # $1=cid; stages /tests and /solution, runs solve.sh unless $2 == nosolve.
    local cid="$1" mode="${2:-solve}"
    docker cp "$TASKDIR/steps/$STEP/tests/." "$cid:/tests/" >/dev/null 2>&1
    if [ "$mode" = solve ]; then
        docker exec "$cid" bash -c 'rm -rf /solution && mkdir -p /solution' >/dev/null 2>&1
        docker cp "$TASKDIR/steps/$STEP/solution/." "$cid:/solution/" >/dev/null 2>&1
        docker exec "$cid" bash /solution/solve.sh >/dev/null 2>&1 || return 1
    fi
    return 0
}

grade_once() {
    # $1=cid; runs test.sh, prints the reward (0.0 on any failure to read).
    local cid="$1" reward
    docker exec "$cid" bash /tests/test.sh >/dev/null 2>&1 || true
    reward="$(docker exec "$cid" cat /logs/verifier/reward.txt 2>/dev/null || echo 0.0)"
    if [ "$reward" = "1" ]; then reward="1.0"; fi
    if [ "$reward" = "0" ]; then reward="0.0"; fi
    printf '%s' "$reward"
}

run_control() {
    # $1=kind $2=name $3=mode(nosolve|solve) $4=overlay-dir-or-empty
    local kind="$1" name="$2" mode="$3" overlay="$4" cid reward
    echo "CONTROL-BEGIN $kind $name"
    # shellcheck disable=SC2086
    cid="$(LAMBO_CONTROL="$kind/$name" docker run -d --rm $LIMITS "$IMG" sleep 3600)" || {
        echo "CONTROL $kind $name reward=ERROR_NO_CONTAINER"
        return 0
    }
    export LAMBO_CONTROL="$kind/$name"
    if ! stage_and_solve "$cid" "$mode"; then
        echo "CONTROL $kind $name reward=ERROR_NO_SOLVE"
        docker rm -f "$cid" >/dev/null 2>&1
        return 0
    fi
    if [ -n "$overlay" ]; then
        docker cp "$overlay/." "$cid:/app/" >/dev/null 2>&1
    fi
    reward="$(grade_once "$cid")"
    echo "CONTROL $kind $name reward=$reward"
    docker rm -f "$cid" >/dev/null 2>&1
    unset LAMBO_CONTROL
    return 0
}

run_twice() {
    # $1=unit; grades the solved state twice in one container.
    local unit="$1" cid first second
    echo "CONTROL-BEGIN twice $unit"
    # shellcheck disable=SC2086
    cid="$(LAMBO_CONTROL="twice/$unit" docker run -d --rm $LIMITS "$IMG" sleep 3600)" || {
        echo "CONTROL twice $unit reward=ERROR_NO_CONTAINER"
        return 0
    }
    export LAMBO_CONTROL="twice/$unit"
    if ! stage_and_solve "$cid" solve; then
        echo "CONTROL twice $unit reward=ERROR_NO_SOLVE"
        docker rm -f "$cid" >/dev/null 2>&1
        return 0
    fi
    first="$(grade_once "$cid")"
    second="$(grade_once "$cid")"
    echo "CONTROL twice $unit reward=$first,$second"
    docker rm -f "$cid" >/dev/null 2>&1
    unset LAMBO_CONTROL
    return 0
}

# pos: correct but differently written (regex-free normalize, split-based
# matching, restructured upload checks).
run_control pos alternate_core solve "$TASKDIR/build/ref_solutions/pos_alternate"
# pos: alternate but equally valid HTML renderer (other title/heading
# wording that names the project, list layout, extra anchor attribute).
# Scores 0 on the pre-fix suite (which pins the reference `Links for`
# wording) and 1 once the HTML test compares structurally with
# project-naming title/heading.
run_control pos alternate_html solve "$TASKDIR/build/ref_solutions/pos_alternate_html"
# neg: the unsolved tree must score 0 (null/no-op control).
run_control neg null_noop nosolve ""
# neg: "always say yes" test-gaming (match-all + allow-all overlays).
run_control neg gaming_hardcode solve "$TASKDIR/build/neg_controls/gaming_hardcode"
# neg: importable names, no behavior.
run_control neg cosmetic_only solve "$TASKDIR/build/neg_controls/cosmetic_only"
# neg: the rival reading (one-directional overlap, no hyphen boundary,
# owned-always-true).
run_control neg subtly_wrong solve "$TASKDIR/build/neg_controls/subtly_wrong"
# neg: console-spoof attack (fake `... ok` lines for every required id via
# /app/test.py shadowing + /app/Lib/sitecustomize.py startup import, over a
# broken implementation). Scores 1 on a console-text grader, 0 now.
run_control neg console_spoof solve "$TASKDIR/build/neg_controls/console_spoof"
# neg: success-marker spoof (verify_offline.sh replaced by a script that only
# prints the marker, and the `unknown grant` / `overlaps the grant`
# diagnostics reworded while keeping the weak `unknown` / `overlap`
# substrings). Scores 1 on the pre-fix suite (replicates the pre-push
# reviewer's demonstrated bypass), 0 now that the suite pins the full
# phrases and probes verify_offline with missing/damaged fixtures.
run_control neg verify_spoof solve "$TASKDIR/build/neg_controls/verify_spoof"
# neg: private-envelope persistence (writes {"private_payload": {...}} and
# rejects documented store documents). Scores 1 on the suite alone
# (replicates the pre-push reviewer's demonstrated bypass), 0 once the
# persisted-schema tests and the independent probe pin the documented
# schema in both directions.
run_control neg store_spoof solve "$TASKDIR/build/neg_controls/store_spoof"
# neg: JUnit-rewrite attack (broken implementation whose package import
# arms an atexit hook overwriting the runner's report with all-PASSED).
# Scores 1 on a report-only grader, 0 once the independent probe (which
# never reads the report) joins the reward.
run_control neg junit_forge solve "$TASKDIR/build/neg_controls/junit_forge"
# neg: two-channel rewrite attack (same broken stubs, but the shutdown hook
# overwrites the probe's verdict file with a passed payload too). Scores 1
# on the single-process probe (both forgeries win at shutdown), 0 once the
# split probe's parent writes the verdict after the armed child has exited.
run_control neg probe_forge solve "$TASKDIR/build/neg_controls/probe_forge"
# neg: replaced-interpreter attack on the otherwise UNSOLVED tree (only a
# forging /app/python covering every required JUnit id plus the probe
# verdict; no feature package). Scores 1 on the pre-fix harness, whose
# make-and-install block -- the only thing that ever relinked the binary
# (a full make relinks unconditionally, measured) -- is guarded on the
# package directory and therefore skipped here, so the forged binary runs
# as suite runner and probe parent. Scores 0 once run_script.sh assures
# the interpreter unconditionally, the probe parent runs under the
# verifier-owned interpreter, and the closed artifact set stops the
# binary crossing to the separate verifier at all.
run_control neg exec_forge nosolve "$TASKDIR/build/neg_controls/exec_forge"
# neg: live two-channel forge (package ships ONLY __init__.py: no feature
# APIs; importing it replaces unittest.TestCase.run with an unconditional
# success and arms a sys.settrace hook that swaps the probe's CHECKS for
# no-ops). Scores 1 on the pre-fix harness (both forgeries win), 0 once
# the probe checks framework integrity and the parent attests the child's
# check bytecode against a grandchild that never imports agent code.
run_control neg trace_forge nosolve "$TASKDIR/build/neg_controls/trace_forge"
# neg: dropped root re-export (golden tree minus the build_parser import
# and __all__ entry at the package root). Scores 1 on the pre-fix
# harness, whose suite and probe never check the specified re-export, 0
# once the cli.root_exports probe check pins it (the suite half rides the
# next AUTHOR_1P as a new fail_to_pass id).
run_control neg exports_drop solve "$TASKDIR/build/neg_controls/exports_drop"
# pos: tuple __all__ (golden tree with the package root's __all__ spelled
# as a tuple instead of a list). Scores 0 on the pre-fix probe (which
# pins the list spelling although the spec only requires re-exports)
# and 1 once grants.exports accepts either spelling.
run_control pos tuple_all solve "$TASKDIR/build/ref_solutions/pos_tuple_all"
# pos: uppercase HTML renderer (golden tree with simple_html emitting
# uppercase tags and spaced HREF attributes). Scores 0 on the pre-fix
# probe and suite (lowercase-only anchor matching) and 1 once both
# compare anchors by parsing. The suite half rides the next AUTHOR_1P,
# so this prints 0 until the metadata re-authoring lands (probe-level
# 0-pre/1-post is proven separately); like round 7's pending ids, an
# expected 0, not a failure.
run_control pos upper_html solve "$TASKDIR/build/ref_solutions/pos_upper_html"
# neg: dropped GrandfatheredRegistry re-export (golden tree minus the
# GrandfatheredRegistry import and __all__ entry at the package root).
# Scores 1 on the pre-fix harness, whose suite and probe never check the
# specified re-export (reproduced by the pre-push review), 0 once the
# grants.exports probe check pins it (the suite half rides the next
# AUTHOR_1P as an import-from-root revise of the uploads tests; same ids).
run_control neg exports_drop_grandfathered solve "$TASKDIR/build/neg_controls/exports_drop_grandfathered"
# neg: grading-reader rewrite (golden tree whose package import overwrites
# /tests/parser.py and /tests/probe.py with forgeries emitting all-passed
# verdicts, over a genuinely broken normalize_name). Scores 1 on the
# pre-fix harness, which executes submitted code as root with /tests
# writable (reproduces the pre-push review's demonstrated bypass), 0 once
# submitted code runs unprivileged with /tests read-only and the genuine
# failures stand.
run_control neg tests_tamper solve "$TASKDIR/build/neg_controls/tests_tamper"
# pos: split shell harness (golden tree with gen_fixtures.sh and
# verify_offline.sh delegating to a sibling _fixtures.py helper). Scores 0
# on the pre-fix harness, whose suite and probe copy only the two .sh
# files into a fresh tools tree (reproduces the pre-push review's
# legitimate-decomposition failure), and 1 once both copy the whole
# directory. The suite half rides the next AUTHOR_1P, so this prints 0
# until the tooling re-authoring lands (probe-level 0-pre/1-post is
# proven separately); like round 7's pending ids, an expected 0.
run_control pos split_harness solve "$TASKDIR/build/ref_solutions/pos_split_harness"
# twice: one solved container graded twice.
run_twice "$STEP"
