"""Grant lifecycle for package namespaces (PEP 752, Semantics).

A grant reserves a namespace for one owner on one package repository.
Grants MUST NOT overlap ownership: a proposed namespace that overlaps an
existing grant held by a different owner is rejected.  Overlap is
bidirectional -- a longer namespace under an existing grant overlaps just
as a shorter one over it does -- and is decided by appending a hyphen to
both normalized names and comparing in both directions, so ``"foo"`` and
``"foobar"`` never overlap.
"""

from __future__ import annotations

import dataclasses

from .matching import namespace_matches
from .normalize import hyphen_depth, is_valid_namespace, normalize_name

__all__ = [
    "DEFAULT_DEPTH_LIMIT",
    "Grant",
    "GrantError",
    "InvalidNamespaceError",
    "OverlapError",
    "DepthLimitError",
    "UnknownGrantError",
    "grants_overlap",
    "GrantStore",
]

#: Default cap on the number of hyphens in a granted namespace.  ``None``
#: disables the limit; repositories SHOULD impose one.
DEFAULT_DEPTH_LIMIT = 3


class GrantError(Exception):
    """Base class for grant-store errors."""


class InvalidNamespaceError(GrantError, ValueError):
    """A namespace is not a valid project name."""


class OverlapError(GrantError):
    """A proposed namespace overlaps a grant held by another owner."""


class DepthLimitError(GrantError):
    """A proposed namespace exceeds the store's hyphen depth limit."""


class UnknownGrantError(GrantError):
    """No active grant exists for a namespace."""


@dataclasses.dataclass(frozen=True, slots=True)
class Grant:
    """A reservation of *name* (normalized) for *owner*."""

    name: str
    owner: str


def grants_overlap(first: str, second: str) -> bool:
    """Return True if two namespaces overlap.

    Both names are normalized and a hyphen is appended to each before the
    comparison runs in both directions, so ``"foo"`` overlaps ``"foo-bar"``
    in either argument order while ``"foo"`` and ``"foobar"`` do not.
    """
    first_hyphenated = normalize_name(first) + "-"
    second_hyphenated = normalize_name(second) + "-"
    # RIVAL DEFECT 2: one-directional overlap, read straight off the spec's
    # "any existing namespace starts with the proposed namespace" sentence.
    # Here `second` is the existing grant, so only that direction is kept:
    # a longer proposal under an existing grant slips through.
    return second_hyphenated.startswith(first_hyphenated)


def _check_owner(owner: str) -> str:
    if not isinstance(owner, str) or not owner:
        raise ValueError("owner must be a non-empty string")
    return owner


class GrantStore:
    """The active namespace grants of one package repository.

    Grants are per-repository and are never shared between repositories.
    """

    def __init__(self, depth_limit: int | None = DEFAULT_DEPTH_LIMIT) -> None:
        """Create a store; *depth_limit* caps hyphens per namespace.

        ``None`` disables the limit.
        """
        self._depth_limit = depth_limit
        self._grants: dict[str, Grant] = {}

    @property
    def depth_limit(self) -> int | None:
        """The configured hyphen depth limit, or None if unlimited."""
        return self._depth_limit

    def __len__(self) -> int:
        return len(self._grants)

    def __contains__(self, namespace: object) -> bool:
        return isinstance(namespace, str) and (
            normalize_name(namespace) in self._grants
        )

    def reserve(self, namespace: str, owner: str) -> Grant:
        """Reserve *namespace* for *owner* and return the new grant.

        The name must be valid and within the depth limit.  A namespace
        that overlaps an existing grant may only be reserved by that
        grant's owner; anyone else gets :exc:`OverlapError`.  Reserving
        the exact same namespace for the same owner is idempotent.
        """
        if not is_valid_namespace(namespace):
            raise InvalidNamespaceError(f"{namespace!r} is not a valid namespace")
        normalized = normalize_name(namespace)
        if (
            self._depth_limit is not None
            and hyphen_depth(normalized) > self._depth_limit
        ):
            raise DepthLimitError(
                f"{normalized!r} has {hyphen_depth(normalized)} hyphens, "
                f"above the limit of {self._depth_limit}"
            )
        _check_owner(owner)
        for existing in self._grants.values():
            if grants_overlap(normalized, existing.name) and (
                existing.owner != owner
            ):
                raise OverlapError(
                    f"{normalized!r} overlaps the grant for {existing.name!r} "
                    f"held by {existing.owner!r}"
                )
        grant = Grant(name=normalized, owner=owner)
        self._grants[normalized] = grant
        return grant

    def transfer(self, namespace: str, new_owner: str) -> Grant:
        """Move the grant for *namespace* to *new_owner*."""
        normalized = normalize_name(namespace)
        try:
            current = self._grants[normalized]
        except KeyError:
            raise UnknownGrantError(
                f"no active grant for {normalized!r}"
            ) from None
        _check_owner(new_owner)
        moved = Grant(name=current.name, owner=new_owner)
        self._grants[normalized] = moved
        return moved

    def remove(self, namespace: str) -> Grant:
        """Remove the grant for *namespace* and return it."""
        normalized = normalize_name(namespace)
        try:
            return self._grants.pop(normalized)
        except KeyError:
            raise UnknownGrantError(
                f"no active grant for {normalized!r}"
            ) from None

    def get(self, namespace: str) -> Grant | None:
        """Return the grant for *namespace*, or None if there is none."""
        return self._grants.get(normalize_name(namespace))

    def namespaces(self) -> list[str]:
        """Return every granted namespace, sorted."""
        return sorted(self._grants)

    def matching(self, project: str) -> list[Grant]:
        """Return the grants whose namespace matches *project*, sorted."""
        return sorted(
            (
                grant
                for grant in self._grants.values()
                if namespace_matches(grant.name, project)
            ),
            key=lambda grant: grant.name,
        )

    def parent(self, namespace: str) -> str | None:
        """Return the granted parent of *namespace*, or None.

        The parent is the namespace without its trailing hyphenated
        component; it is only reported when it holds an active grant.
        """
        normalized = normalize_name(namespace)
        parent, _, _ = normalized.rpartition("-")
        if parent and parent in self._grants:
            return parent
        return None

    def children(self, namespace: str) -> list[str]:
        """Return the granted direct children of *namespace*, sorted.

        Only single-component extensions count: with grants for ``"foo"``,
        ``"foo-bar"`` and ``"foo-bar-baz"``, the children of ``"foo"`` are
        ``["foo-bar"]``.
        """
        normalized = normalize_name(namespace)
        prefix = normalized + "-"
        return sorted(
            name
            for name in self._grants
            if name.startswith(prefix) and "-" not in name[len(prefix):]
        )
