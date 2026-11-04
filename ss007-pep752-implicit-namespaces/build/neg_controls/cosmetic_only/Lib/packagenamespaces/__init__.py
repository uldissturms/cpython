"""NEG cosmetic control: every public name exists, nothing works."""

from __future__ import annotations

__all__ = [
    "normalize_name",
    "is_valid_namespace",
    "hyphen_depth",
    "namespace_matches",
    "DEFAULT_DEPTH_LIMIT",
    "Grant",
    "GrantError",
    "InvalidNamespaceError",
    "OverlapError",
    "DepthLimitError",
    "UnknownGrantError",
    "grants_overlap",
    "GrantStore",
    "CONFLICT_STATUS",
    "UploadConflictError",
    "GrandfatheredRegistry",
    "authorize_upload",
    "API_VERSION",
    "LEGACY_API_VERSION",
    "NotSupportedError",
    "RepositoryIndex",
    "SecurityPolicy",
    "CONFLICT_EXIT",
    "main",
]

DEFAULT_DEPTH_LIMIT = 3
CONFLICT_STATUS = 409
API_VERSION = "1.5"
LEGACY_API_VERSION = "1.4"
CONFLICT_EXIT = 3


class GrantError(Exception):
    pass


class InvalidNamespaceError(GrantError, ValueError):
    pass


class OverlapError(GrantError):
    pass


class DepthLimitError(GrantError):
    pass


class UnknownGrantError(GrantError):
    pass


class UploadConflictError(Exception):
    status_code = CONFLICT_STATUS


class NotSupportedError(Exception):
    pass


class Grant:
    def __init__(self, name=None, owner=None):
        raise NotImplementedError


def _stub(*args, **kwargs):
    raise NotImplementedError


normalize_name = _stub
is_valid_namespace = _stub
hyphen_depth = _stub
namespace_matches = _stub
grants_overlap = _stub
authorize_upload = _stub
main = _stub


class GrantStore:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError


class GrandfatheredRegistry:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError


class RepositoryIndex:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError


class SecurityPolicy:
    def __init__(self, *args, **kwargs):
        raise NotImplementedError
