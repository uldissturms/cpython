"""Project matching via component split (alternate correct implementation)."""

from __future__ import annotations

from .normalize import normalize_name

__all__ = ["namespace_matches"]


def namespace_matches(namespace: str, project: str) -> bool:
    wanted = normalize_name(namespace).split("-")
    candidate = normalize_name(project).split("-")
    if len(candidate) < len(wanted):
        return False
    for left, right in zip(wanted, candidate):
        if left != right:
            return False
    return True
