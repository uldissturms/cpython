#!/bin/bash
# Re-verify PEP 752 namespace fixtures with no network.
#
# Usage: verify_offline.sh <fixturedir>
#
# Loads the indexes written by gen_fixtures.sh and checks grant
# overlap, upload authorization, installer policy and metadata
# behavior, including that a grant on one index confers nothing on
# another.  Pure local computation; safe under --network=none.
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: verify_offline.sh <fixturedir>" >&2
    exit 2
fi

FIXTUREDIR="$1"
for needed in grants.json projects.json grandfathered.json second-index.json; do
    if [ ! -f "$FIXTUREDIR/$needed" ]; then
        echo "verify: FAIL missing fixture $needed" >&2
        exit 1
    fi
done

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -r "$ROOT/Lib/packagenamespaces" "$STAGE/"
# Split layout: fixture loading lives in the sibling _fixtures.py helper,
# reached through the entrypoint's own directory (never the caller's cwd).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON="${PYTHON:-python3}"
FIXTUREDIR="$FIXTUREDIR" FIXTURELIB="$SCRIPT_DIR" PYTHONPATH="$STAGE" "$PYTHON" - <<'PY'
import json
import os
import sys

sys.path.insert(0, os.environ["PYTHONPATH"])
sys.path.insert(0, os.environ["FIXTURELIB"])
from _fixtures import load_fixture
from packagenamespaces import (
    GrantStore,
    OverlapError,
    RepositoryIndex,
    SecurityPolicy,
    UploadConflictError,
    authorize_upload,
)

fixturedir = os.environ["FIXTUREDIR"]

def shape_fail(message):
    print(f"verify: FAIL {message}", file=sys.stderr)
    sys.exit(1)

grants_doc = load_fixture(fixturedir, "grants.json")
projects_doc = load_fixture(fixturedir, "projects.json")
grandfathered_doc = load_fixture(fixturedir, "grandfathered.json")
second = load_fixture(fixturedir, "second-index.json")

grants = grants_doc.get("grants") if isinstance(grants_doc, dict) else None
if not isinstance(grants, list) or any(
    not isinstance(entry, dict)
    or not isinstance(entry.get("name"), str)
    or not isinstance(entry.get("owner"), str)
    for entry in grants
):
    shape_fail("grants.json holds no valid grants list")
projects = projects_doc.get("projects") if isinstance(projects_doc, dict) else None
if not isinstance(projects, dict) or any(
    not isinstance(project, str) or not isinstance(owner, str)
    for project, owner in projects.items()
):
    shape_fail("projects.json holds no valid projects mapping")
grandfathered = (
    grandfathered_doc.get("grandfathered")
    if isinstance(grandfathered_doc, dict)
    else None
)
if not isinstance(grandfathered, list) or any(
    not isinstance(project, str) for project in grandfathered
):
    shape_fail("grandfathered.json holds no valid exemptions list")
second_grants = second.get("grants") if isinstance(second, dict) else None
second_projects = second.get("projects") if isinstance(second, dict) else None
if not isinstance(second_grants, list) or any(
    not isinstance(entry, dict)
    or not isinstance(entry.get("name"), str)
    or not isinstance(entry.get("owner"), str)
    for entry in second_grants
):
    shape_fail("second-index.json holds no valid grants list")
if not isinstance(second_projects, dict) or any(
    not isinstance(project, str) or not isinstance(owner, str)
    for project, owner in second_projects.items()
):
    shape_fail("second-index.json holds no valid projects mapping")

failures = []

def check(label, condition):
    print(f"verify: {label} {'ok' if condition else 'FAIL'}")
    if not condition:
        failures.append(label)

store = GrantStore()
for entry in grants:
    store.reserve(entry["name"], entry["owner"])

try:
    store.reserve("acme-sneaky", "mallory")
    check("overlap-rejected", False)
except OverlapError:
    check("overlap-rejected", True)

index = RepositoryIndex(store)
for project, owner in projects.items():
    index.register_project(project, owner)
for project in grandfathered:
    index.grandfathered.add(project)

check("upload-owner-allowed",
      authorize_upload("acme-fresh", "acme-corp", store,
                       grandfathered=index.grandfathered) is True)
try:
    authorize_upload("airflow-evil", "mallory", store,
                     grandfathered=index.grandfathered)
    check("upload-stranger-denied", False)
except UploadConflictError as exc:
    check("upload-stranger-denied", exc.status_code == 409)
check("upload-grandfathered-allowed",
      authorize_upload("acme-legacy", "mallory", store,
                       grandfathered=index.grandfathered) is True)

policy = SecurityPolicy(["acme"], "acme-corp")
verdicts = policy.evaluate(
    ["acme-widgets-sprocket", "acme-legacy", "requests"], index)
check("policy-admits-granted", verdicts == {
    "acme-widgets-sprocket": True,
    "acme-legacy": False,
    "requests": False,
})

mirror = RepositoryIndex(GrantStore())
for project, owner in second["projects"].items():
    mirror.register_project(project, owner)
check("multirepo-not-shared",
      policy.evaluate(["acme-widgets-sprocket"], mirror)
      == {"acme-widgets-sprocket": False})

check("api-version", index.api_version == "1.5")
detail = index.project_detail("acme-widgets-sprocket")
check("detail-namespaces",
      detail["namespaces"] == [{"name": "acme", "owned": True},
                               {"name": "acme-widgets", "owned": True}])
index.store.remove("acme")
index.store.remove("acme-widgets")
check("removal-nulls",
      index.project_detail("acme-widgets-sprocket")["namespaces"] is None)

if failures:
    print(f"verify: {len(failures)} check(s) failed", file=sys.stderr)
    sys.exit(1)
print("verify: all checks passed")
PY
