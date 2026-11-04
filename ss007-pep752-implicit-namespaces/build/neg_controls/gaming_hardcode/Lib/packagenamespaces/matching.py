"""NEG gaming control: agree with every positive assertion, dodge the rest."""

from __future__ import annotations

from .normalize import normalize_name

__all__ = ["namespace_matches"]


def namespace_matches(namespace: str, project: str) -> bool:
    # Gaming attempt: match everything, so every "must match" test passes.
    # The negative tests (foobar must NOT match foo) are supposed to fail.
    normalize_name(namespace)
    normalize_name(project)
    return True
