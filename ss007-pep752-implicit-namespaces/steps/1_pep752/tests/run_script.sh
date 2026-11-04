#!/bin/bash
# Run the graded CPython tests under a locked-down interpreter.
#
# MSL's sole test entrypoint: it receives the selected test files as CLI
# arguments (comma-joined or separate, relative to the repo root). Verdicts
# travel ONLY through the runner-written JUnit XML report -- console output
# is logs, never grading input, so fake `... ok` lines printed by agent code
# cannot score. A failing test is data, not an error, so the runner's exit
# status is swallowed and test.sh decides the reward.
REPO=/app
[ -d "$REPO" ] || REPO=/testbed
JUNIT_XML="${LAMBO_JUNIT_XML:-/tmp/lambo-junit.xml}"

RAW_ARGS="$*"
TESTS=""
if [ -z "$RAW_ARGS" ]; then
    # Standalone default: the task's own conformance modules.
    TESTS="test_pep752_naming test_pep752_semantics test_pep752_uploads test_pep752_metadata test_pep752_policy test_pep752_tooling"
else
    # Accept comma-joined or separate args; map Lib/test/<name>[.py] to <name>.
    NORMALIZED="$(printf '%s' "$RAW_ARGS" | tr ',' ' ')"
    for entry in $NORMALIZED; do
        name="$entry"
        name="${name#Lib/test/}"
        name="${name#test/}"
        name="${name%.py}"
        name="${name%/}"
        [ -n "$name" ] && TESTS="$TESTS $name"
    done
fi

# Drop any stale report: a crashed run must grade zero tests, not the
# previous run's verdicts.
rm -f "$JUNIT_XML"

# Build and stage a DESTDIR install when the tree has the package. The
# suite's InstallTests grade the installed tree and sys.stdlib_module_names,
# both of which read Makefile.pre.in / Python/stdlib_module_names.h THROUGH
# a build; the agent's edits (or the oracle's patch) land after the image
# build, so the binary, Makefile and install can be stale. Doing it HERE --
# from bash, before the suite's interpreter starts -- matters twice over:
# rebuilding from INSIDE the suite relinks the running ./python binary,
# which segfaults it, and even a no-op `make` spawned as a subprocess of
# this alpha interpreter segfaults the parent (both measured). The guards
# keep the common cases free: trees without the package skip everything,
# and a fresh marker skips repeat runs in one container. A failed build or
# install is data, not an error: the suite below fails naturally on a tree
# that does not build or install (and a missing marker retries next run).
DESTDIR=/tmp/lambo-destdir
MARKER="$DESTDIR/.lambo-installed"
if [ -d "$REPO/Lib/packagenamespaces" ]; then
    if [ "$REPO/Python/stdlib_module_names.h" -nt "$REPO/python" ] || \
       [ "$REPO/Makefile.pre.in" -nt "$REPO/Makefile" ] || \
       [ ! -f "$MARKER" ]; then
        make -C "$REPO" -j4 -s >/dev/null 2>&1 || true
        if rm -rf "$DESTDIR" && \
           make -C "$REPO" install DESTDIR="$DESTDIR" >/dev/null 2>&1; then
            touch "$MARKER"
        fi
    fi
fi

# Locked-down invocation, all four at once:
#   - neutral cwd (never $REPO: nothing agent-owned shadows an import),
#   - absolute interpreter path,
#   - -I (ignore PYTHONPATH/cwd/user site) + -S (no site/sitecustomize),
#   - PYTHONSAFEPATH + scrubbed PYTHONPATH as belt and braces.
# The stdlib under test still comes from the build tree via the binary's own
# prefix resolution, not from the working directory.
cd / || exit 1
# shellcheck disable=SC2086
env -u PYTHONPATH PYTHONSAFEPATH=1 "$REPO/python" -I -S -m test -v \
    --junit-xml "$JUNIT_XML" $TESTS 2>&1 || true
