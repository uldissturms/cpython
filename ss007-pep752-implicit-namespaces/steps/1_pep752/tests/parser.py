#!/usr/bin/env python3
"""Parse the runner-written JUnit XML report into the MSL verdict shape.

Usage: parser.py <stdout-file> <stderr-file> <output-json>

The console streams exist for logs only and are NEVER grading input: agent
code running inside the suite can print arbitrary text, so verdicts come
exclusively from the XML file regrtest itself wrote at the end of a genuine
run (``--junit-xml``). A run that never got there -- crashed, ``os._exit``'d
out of ``sitecustomize``, killed -- leaves no report and grades zero tests.

Writes::

    {"tests": [{"name": "<dotted id>", "status": "PASSED|FAILED|SKIPPED|ERROR"}]}

The dotted id is the testcase ``name`` attribute (``test.id()``), identical
to the id the console channel used to emit. When one id appears more than
once (regrtest reruns) the worst status wins, so a later pass can never
mask a real failure.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET

JUNIT_XML = os.environ.get("LAMBO_JUNIT_XML", "/tmp/lambo-junit.xml")

# Worst first: a later pass never outranks a real failure.
SEVERITY = {"ERROR": 4, "FAILED": 3, "PASSED": 2, "SKIPPED": 1}

VALID = frozenset(SEVERITY)


def classify(case):
    """Map a JUnit testcase element to an MSL status."""
    for child in case:
        tag = child.tag
        if tag == "error":
            return "ERROR"
        if tag == "failure":
            return "FAILED"
        if tag == "skipped":
            return "SKIPPED"
        if tag == "output":
            # Expected failure: ran, failed as anticipated. Counts as
            # skipped, matching the old console channel's mapping.
            return "SKIPPED"
        if tag == "outcome" and (child.text or "").strip() == "UNEXPECTED_SUCCESS":
            return "FAILED"
    return "PASSED"


def parse_report(path, verdicts):
    """Fold testcase verdicts from one JUnit file into the verdict map."""
    try:
        root = ET.parse(path).getroot()
    except FileNotFoundError:
        sys.stderr.write(f"parser: no JUnit report at {path} (run crashed?)\n")
        return
    except ET.ParseError as exc:
        sys.stderr.write(f"parser: cannot parse {path}: {exc}\n")
        return
    except OSError as exc:
        sys.stderr.write(f"parser: cannot read {path}: {exc}\n")
        return
    for case in root.iter("testcase"):
        name = case.get("name")
        if not name:
            continue
        status = classify(case)
        current = verdicts.get(name)
        if current is None or SEVERITY[status] > SEVERITY[current]:
            verdicts[name] = status


def validate_contract(payload):
    """Exit non-zero unless the payload is the exact MSL shape."""
    if not isinstance(payload, dict):
        sys.stderr.write("parser: output is not a JSON object\n")
        return False
    tests = payload.get("tests")
    if not isinstance(tests, list):
        sys.stderr.write("parser: output has no `tests` list\n")
        return False
    seen = set()
    for entry in tests:
        if not isinstance(entry, dict):
            sys.stderr.write("parser: test entry is not an object\n")
            return False
        name = entry.get("name")
        status = entry.get("status")
        if not isinstance(name, str) or not name:
            sys.stderr.write("parser: test entry has a bad name\n")
            return False
        if status not in VALID:
            sys.stderr.write(f"parser: status {status!r} for {name} is invalid\n")
            return False
        if name in seen:
            sys.stderr.write(f"parser: duplicate verdict for {name}\n")
            return False
        seen.add(name)
    return True


def main(argv):
    if len(argv) != 4:
        sys.stderr.write("usage: parser.py <stdout> <stderr> <output-json>\n")
        return 2
    output_path = argv[3]
    verdicts = {}
    parse_report(JUNIT_XML, verdicts)
    payload = {
        "tests": [
            {"name": name, "status": status}
            for name, status in sorted(verdicts.items())
        ]
    }
    if not validate_contract(payload):
        return 2
    if not payload["tests"]:
        sys.stderr.write("parser: warning: no test verdicts parsed\n")
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        sys.stderr.write(f"parser: cannot write {output_path}: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
