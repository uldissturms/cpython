"""Project matching for namespace grants (PEP 752, Semantics).

A grant bestows ownership over the project that exactly matches the
namespace and over every project that starts with the namespace followed
by a hyphen: ``"foo"`` matches ``"foo"`` and ``"foo-bar"`` but not
``"foobar"``.  Both sides are normalized before they are compared.
"""

from __future__ import annotations

from .normalize import normalize_name

__all__ = ["namespace_matches"]


def namespace_matches(namespace: str, project: str) -> bool:
    """Return True if *project* falls under *namespace*.

    The comparison is exact-match or namespace-plus-hyphen-prefix, after
    normalizing both inputs.  For example ``namespace_matches("foo",
    "foo-bar")`` is True while ``namespace_matches("foo", "foobar")`` is
    False.
    """
    normalized_ns = normalize_name(namespace)
    normalized_project = normalize_name(project)
    # RIVAL DEFECT 1: prefix without the hyphen boundary, so "foo" matches
    # "foobar".  The spec's "-plus-hyphen" sentence is dropped.
    return normalized_project == normalized_ns or normalized_project.startswith(
        normalized_ns
    )
