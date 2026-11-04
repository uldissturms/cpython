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
# twice: one solved container graded twice.
run_twice "$STEP"
