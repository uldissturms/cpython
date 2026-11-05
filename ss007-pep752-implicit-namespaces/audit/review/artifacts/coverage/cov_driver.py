#!/usr/bin/env python3
"""Line-only coverage driver for the ss007 CPython task (lh-coverage rung 2).

Runs INSIDE the task container under the built /app/python with -I -S.
Uses sys.monitoring (stdlib, no pip needed): global PY_START fans out to
local LINE events only for code objects in Lib/packagenamespaces/.

Modes:
  suite <junit-xml> <module>...   run regrtest in-process (== `python -m test`)
  probe-child <probe.py>          run probe.py --child /app in-process

Writes <out>/hits-<mode>.json {file: [lines]} and <out>/exec.json
{file: [executable lines from dis]}. Subprocesses are blind by
construction (documented caveat, same as the prior trace backend).
"""
import dis
import json
import os
import runpy
import sys

REPO = "/app"
PKG_DIR = os.path.join(REPO, "Lib", "packagenamespaces")
OUT = "/work/out"

TARGETS = sorted(
    os.path.join(PKG_DIR, f)
    for f in os.listdir(PKG_DIR)
    if f.endswith(".py")
)
TARGET_SET = {os.path.normpath(p) for p in TARGETS}
HITS = {t: set() for t in TARGET_SET}


def exec_lines(path):
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    code = compile(src, path, "exec")
    lines = set()
    stack = [code]
    while stack:
        c = stack.pop()
        for _off, ln in dis.findlinestarts(c):
            if ln:
                lines.add(ln)
        stack.extend(k for k in c.co_consts if hasattr(k, "co_code"))
    return sorted(lines)


def enable_monitoring():
    mon = sys.monitoring
    tool = mon.COVERAGE_ID
    mon.use_tool_id(tool, "lhcov")
    events = mon.events

    def on_start(code, _offset):
        if os.path.normpath(code.co_filename) in TARGET_SET:
            mon.set_local_events(tool, code, events.LINE)
        else:
            mon.set_local_events(tool, code, 0)

    def on_line(code, line_number):
        HITS[os.path.normpath(code.co_filename)].add(line_number)

    mon.register_callback(tool, events.PY_START, on_start)
    mon.register_callback(tool, events.LINE, on_line)
    mon.set_events(tool, events.PY_START)
    return mon, tool


def disable_monitoring(mon, tool):
    mon.set_events(tool, 0)
    mon.free_tool_id(tool)


def main(argv):
    assert os.path.isdir(PKG_DIR), f"golden not applied: {PKG_DIR} missing"
    mode = argv[1]
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "exec.json"), "w", encoding="utf-8") as fh:
        json.dump({t: exec_lines(t) for t in TARGETS}, fh, indent=1)
    mon, tool = enable_monitoring()
    status = 0
    try:
        if mode == "suite":
            junit_xml, modules = argv[2], argv[3:]
            sys.argv = ["test", "-v", "--junit-xml", junit_xml, *modules]
            try:
                runpy.run_module("test", run_name="__main__")
            except SystemExit as exc:
                status = exc.code or 0
        elif mode == "probe-child":
            probe_py = argv[2]
            sys.argv = [probe_py, "--child", REPO]
            try:
                runpy.run_path(probe_py, run_name="__main__")
            except SystemExit as exc:
                status = exc.code or 0
        else:
            raise SystemExit(f"unknown mode: {mode}")
    finally:
        disable_monitoring(mon, tool)
        with open(
            os.path.join(OUT, f"hits-{mode}.json"), "w", encoding="utf-8"
        ) as fh:
            json.dump(
                {t: sorted(HITS[t]) for t in TARGETS}, fh, indent=1
            )
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))
