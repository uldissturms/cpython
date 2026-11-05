"""Implicit namespaces for package repositories (PEP 752).

This package implements PEP 752: organizations reserve package-name
prefixes, uploads under a reserved prefix require an active grant, and
repositories expose the grants through version 1.5 of the JSON Simple
API so installers can enforce namespace security policies.
"""

from __future__ import annotations

from .cli import CONFLICT_EXIT, build_parser, main
from .grants import (
    DEFAULT_DEPTH_LIMIT,
    DepthLimitError,
    Grant,
    GrantError,
    GrantStore,
    InvalidNamespaceError,
    OverlapError,
    UnknownGrantError,
    grants_overlap,
)
from .matching import namespace_matches
from .metadata import (
    API_VERSION,
    LEGACY_API_VERSION,
    NotSupportedError,
    RepositoryIndex,
)
from .normalize import hyphen_depth, is_valid_namespace, normalize_name
from .policy import SecurityPolicy
from .uploads import (
    CONFLICT_STATUS,
    UploadConflictError,
    authorize_upload,
)

__all__ = [
    "API_VERSION",
    "LEGACY_API_VERSION",
    "CONFLICT_EXIT",
    "CONFLICT_STATUS",
    "DEFAULT_DEPTH_LIMIT",
    "DepthLimitError",
    "Grant",
    "GrantError",
    "GrantStore",
    "InvalidNamespaceError",
    "NotSupportedError",
    "OverlapError",
    "RepositoryIndex",
    "SecurityPolicy",
    "UnknownGrantError",
    "UploadConflictError",
    "authorize_upload",
    "build_parser",
    "grants_overlap",
    "hyphen_depth",
    "is_valid_namespace",
    "main",
    "namespace_matches",
    "normalize_name",
]
