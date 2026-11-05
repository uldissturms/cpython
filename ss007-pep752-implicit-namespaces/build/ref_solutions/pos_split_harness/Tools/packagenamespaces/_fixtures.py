"""Shared fixture data for the PEP 752 offline harness.

Split-layout control: the two shell entrypoints delegate to this sibling
helper instead of embedding the fixture documents. A grader that copies
only the two ``.sh`` files into a fresh tools tree breaks both scripts
(the helper is missing); a grader that copies the whole directory keeps
them working. Pure local computation; no network.
"""

import json
import os
import sys

FIXTURES = {
    "grants.json": {
        "grants": [
            {"name": "acme", "owner": "acme-corp"},
            {"name": "acme-widgets", "owner": "acme-corp"},
            {"name": "airflow", "owner": "apache"},
        ]
    },
    "projects.json": {
        "projects": {
            "acme-widgets-sprocket": "acme-corp",
            "acme-legacy": "mallory",
            "airflow-httphook": "mallory",
            "requests": "psf",
        }
    },
    "grandfathered.json": {"grandfathered": ["acme-legacy"]},
    "second-index.json": {
        "grants": [],
        "projects": {"acme-widgets-sprocket": "acme-corp"},
    },
}


def write_fixtures(outdir):
    os.makedirs(outdir, exist_ok=True)
    for name, document in FIXTURES.items():
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle)


def load_fixture(fixturedir, name):
    with open(os.path.join(fixturedir, name), encoding="utf-8") as handle:
        return json.load(handle)


if __name__ == "__main__":
    write_fixtures(sys.argv[1])
