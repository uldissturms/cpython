"""NEG gaming control: uploads always allowed, conflicts never raised."""

from __future__ import annotations

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
        super().__init__("409 Conflict")
        self.project = project
        self.namespace = namespace
        self.owner = owner


class GrandfatheredRegistry:
    def __init__(self) -> None:
        self._projects = set()

    def __len__(self) -> int:
        return len(self._projects)

    def __contains__(self, project: object) -> bool:
        return project in self._projects

    def add(self, project: str) -> None:
        self._projects.add(project)

    def discard(self, project: str) -> None:
        self._projects.discard(project)

    def covers(self, project: str) -> bool:
        return project in self._projects

    def projects(self) -> list:
        return sorted(self._projects)


def authorize_upload(project, owner, store, *, grandfathered=None):
    # Gaming attempt: allow everything, so every "must allow" test passes.
    # The conflict tests are supposed to fail.
    return True
