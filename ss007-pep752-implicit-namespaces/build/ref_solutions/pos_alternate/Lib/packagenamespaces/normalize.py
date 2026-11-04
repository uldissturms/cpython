"""Name normalization without regex (alternate correct implementation)."""

from __future__ import annotations

__all__ = ["normalize_name", "is_valid_namespace", "hyphen_depth"]

_SEPARATORS = ("-", "_", ".")


def normalize_name(name: str) -> str:
    if type(name) is not str:
        raise TypeError(f"name must be str, not {type(name).__name__}")
    out = []
    in_separator = False
    for char in name:
        if char in _SEPARATORS:
            if not in_separator:
                out.append("-")
            in_separator = True
        else:
            out.append(char.lower())
            in_separator = False
    return "".join(out)


def _is_alnum_ascii(char: str) -> bool:
    return ("a" <= char <= "z") or ("A" <= char <= "Z") or ("0" <= char <= "9")


def is_valid_namespace(name: str) -> bool:
    if type(name) is not str:
        return False
    if not name:
        return False
    if not _is_alnum_ascii(name[0]) or not _is_alnum_ascii(name[-1]):
        return False
    for char in name:
        if not (_is_alnum_ascii(char) or char in _SEPARATORS):
            return False
    return True


def hyphen_depth(name: str) -> int:
    count = 0
    for char in normalize_name(name):
        if char == "-":
            count += 1
    return count
