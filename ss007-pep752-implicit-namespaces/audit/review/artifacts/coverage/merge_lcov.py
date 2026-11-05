#!/usr/bin/env python3
"""Merge per-run hit sets with dis-derived executable lines into LCOV.

Usage: merge_lcov.py <exec.json> <hits-1.json> [hits-2.json ...] <out.lcov>
SF paths are the in-container absolute paths (/app/...); analyze.py
strips --root /app. Executable set = dis lines UNION observed hits (an
observed line is executable by definition).
"""
import json
import sys


def main(argv):
    exec_path, hit_paths, out_path = argv[1], argv[2:-1], argv[-1]
    executable = json.load(open(exec_path, encoding="utf-8"))
    hits = {}
    for path in hit_paths:
        for fname, lines in json.load(open(path, encoding="utf-8")).items():
            hits.setdefault(fname, set()).update(lines)
    with open(out_path, "w", encoding="utf-8") as out:
        for fname in sorted(executable):
            hit = hits.get(fname, set())
            lines = sorted(set(executable[fname]) | hit)
            out.write(f"SF:{fname}\n")
            for ln in lines:
                out.write(f"DA:{ln},{1 if ln in hit else 0}\n")
            out.write(f"LF:{len(lines)}\n")
            out.write(f"LH:{sum(1 for ln in lines if ln in hit)}\n")
            out.write("end_of_record\n")
    total = sum(len(set(executable[f]) | hits.get(f, set())) for f in executable)
    covered = sum(len(hits.get(f, set())) for f in executable)
    print(f"LCOV: {covered}/{total} executable lines hit "
          f"({100.0 * covered / total:.1f}%)")


if __name__ == "__main__":
    main(sys.argv)
