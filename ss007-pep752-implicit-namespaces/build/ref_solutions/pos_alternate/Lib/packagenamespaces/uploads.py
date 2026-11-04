"""Upload authorization with inverted checks (alternate correct version)."""

from __future__ import annotations

from .grants import GrantStore
from .normalize import normalize_name

__all__ = [
    "CONFLICT_STATUS",
    "UploadConflictError",
    "GrandfatheredRegistry",
    "authorize_upload",
]

CONFLICT_STATUS = 409


class UploadConflictError(Exception):
    status_code = CONFLICT_STATUS

    def __init__(self, project: str, namespace: str, owner: str) -> None:
        super().__init__(
            "409 Conflict: project %r matches reserved namespace %r and "
            "owner %r holds no active grant for it"
            % (project, namespace, owner)
        )
        self.project = project
        self.namespace = namespace
        self.owner = owner


class GrandfatheredRegistry:
    def __init__(self) -> None:
        self._projects = set()

    def __len__(self) -> int:
        return len(self._projects)

    def __contains__(self, project: object) -> bool:
        if not isinstance(project, str):
            return False
        return normalize_name(project) in self._projects

    def add(self, project: str) -> None:
        self._projects.add(normalize_name(project))

    def discard(self, project: str) -> None:
        self._projects.discard(normalize_name(project))

    def covers(self, project: str) -> bool:
        return normalize_name(project) in self._projects

    def projects(self) -> list:
        names = list(self._projects)
        names.sort()
        return names


def authorize_upload(project, owner, store, *, grandfathered=None):
    target = normalize_name(project)
    if not isinstance(store, GrantStore):
        raise TypeError("store must be a GrantStore")
    held = [grant for grant in store.matching(target) if grant.owner == owner]
    if not store.matching(target) or held:
        return True
    if grandfathered is not None and target in grandfathered:
        return True
    first = sorted(store.matching(target), key=lambda g: g.name)[0]
    raise UploadConflictError(target, first.name, owner)
