#!/bin/bash
set -euo pipefail
cd /app 2>/dev/null || cd /testbed 2>/dev/null

cat > solution_patch.diff << '__SOLUTION__'
diff --git a/Doc/library/distribution.rst b/Doc/library/distribution.rst
index bec1ca3..a2f227a 100644
--- a/Doc/library/distribution.rst
+++ b/Doc/library/distribution.rst
@@ -10,5 +10,6 @@ with a local index server, or without any index server at all.
 .. toctree::
 
    ensurepip.rst
+   packagenamespaces.rst
    venv.rst
    zipapp.rst
diff --git a/Doc/library/packagenamespaces.rst b/Doc/library/packagenamespaces.rst
new file mode 100644
index 0000000..3641b64
--- /dev/null
+++ b/Doc/library/packagenamespaces.rst
@@ -0,0 +1,235 @@
+:mod:`packagenamespaces` --- Implicit namespaces for package repositories
+============================================================================
+
+.. module:: packagenamespaces
+   :synopsis:: Reserve and enforce package-name prefixes (PEP 752).
+
+.. versionadded:: 3.16
+
+**Source code:** :source:`Lib/packagenamespaces/__init__.py`
+
+--------------
+
+This module implements :pep:`752`, which lets organizations reserve
+package-name prefixes ("namespaces") on a package repository.  A grant
+bestows ownership over the project that exactly matches the namespace and
+over every project starting with the namespace followed by a hyphen, so
+the namespace ``acme`` covers ``acme`` and ``acme-widget`` but not
+``acme corp`` or ``acmewidget``.  Uploads under a reserved prefix require
+an active grant, repositories expose the grants through version 1.5 of
+the JSON Simple API, and installers can admit only dependencies inside
+granted namespaces.
+
+All names are :ref:`normalized <packagenamespaces-naming>` before they
+are compared, and grants never cross repositories: a grant on one index
+confers nothing on a mirror.
+
+.. _packagenamespaces-naming:
+
+Naming
+------
+
+.. function:: normalize_name(name)
+
+   Return the normalized form of *name*: every run of ``-``, ``_`` and
+   ``.`` becomes a single ``-`` and the result is lowercased.
+
+.. function:: is_valid_namespace(name)
+
+   Return true if *name* is a valid namespace: a non-empty string with
+   ASCII letters or digits at both ends.
+
+.. function:: hyphen_depth(name)
+
+   Return the number of hyphens in the normalized form of *name*.
+
+.. function:: namespace_matches(namespace, project)
+
+   Return true if *project* exactly matches *namespace* or starts with
+   it followed by a hyphen, after normalizing both.
+
+Semantics
+---------
+
+.. data:: DEFAULT_DEPTH_LIMIT
+
+   The default cap on hyphens per namespace: ``3``.  ``None`` disables
+   the limit.
+
+.. function:: grants_overlap(first, second)
+
+   Return true if two namespaces overlap.  Both are normalized, a hyphen
+   is appended to each, and the comparison runs in both directions.
+
+.. class:: GrantStore(depth_limit=DEFAULT_DEPTH_LIMIT)
+
+   The active grants of one repository.
+
+   .. method:: reserve(namespace, owner)
+
+      Reserve *namespace* for *owner*.  Raises
+      :exc:`InvalidNamespaceError`, :exc:`DepthLimitError` or
+      :exc:`OverlapError`.  A namespace overlapping an existing grant
+      may only be reserved by that grant's owner.
+
+   .. method:: transfer(namespace, new_owner)
+
+      Move a grant to a new owner.
+
+   .. method:: remove(namespace)
+
+      Remove a grant and return it.
+
+   .. method:: get(namespace)
+
+      Return the grant for *namespace*, or None.
+
+   .. method:: namespaces()
+
+      Return every granted namespace, sorted.
+
+   .. method:: matching(project)
+
+      Return the grants matching *project*, sorted by name.
+
+   .. method:: parent(namespace)
+
+      Return the granted parent of *namespace*, or None.
+
+   .. method:: children(namespace)
+
+      Return the granted direct children of *namespace*, sorted.
+
+.. class:: Grant
+
+   A reservation with :attr:`name` and :attr:`owner` attributes.
+
+.. exception:: GrantError
+
+   Base class for grant-store errors.
+
+.. exception:: InvalidNamespaceError
+
+   A namespace is not a valid project name.
+
+.. exception:: OverlapError
+
+   A namespace overlaps a grant held by another owner.
+
+.. exception:: DepthLimitError
+
+   A namespace exceeds the hyphen depth limit.
+
+.. exception:: UnknownGrantError
+
+   No active grant exists for a namespace.
+
+Uploads
+-------
+
+.. data:: CONFLICT_STATUS
+
+   The HTTP status for a refused upload: ``409``.
+
+.. exception:: UploadConflictError
+
+   An upload matched a reserved namespace without a grant.  Carries the
+   normalized :attr:`project`, the matching :attr:`namespace` and the
+   :attr:`owner`, with :attr:`status_code` 409.
+
+.. class:: GrandfatheredRegistry
+
+   Projects that predate the reservation covering them and may keep
+   uploading.  See :meth:`add`, :meth:`covers` and :meth:`projects`.
+
+.. function:: authorize_upload(project, owner, store, *, grandfathered=None)
+
+   Return true if *owner* may upload *project*, else raise
+   :exc:`UploadConflictError`.
+
+Repository metadata
+-------------------
+
+.. data:: API_VERSION
+
+   ``"1.5"``: the JSON Simple API version with namespace metadata.
+
+.. data:: LEGACY_API_VERSION
+
+   ``"1.4"``: the version of repositories without this PEP.
+
+.. exception:: NotSupportedError
+
+   A namespace endpoint was queried on a legacy repository.
+
+.. class:: RepositoryIndex(store=None, *, supports_namespaces=True)
+
+   One repository's namespace metadata.
+
+   .. method:: register_project(project, owner)
+
+      Record that *owner* owns *project*.
+
+   .. method:: project_owner(project)
+
+      Return the recorded owner, or None.
+
+   .. method:: project_detail(project)
+
+      Return the project-detail mapping.  The ``namespaces`` key is None
+      without a matching grant, else an array of ``{"name", "owned"}``
+      mappings.  Legacy repositories omit the key entirely.
+
+   .. method:: list_namespaces()
+
+      Return the ``/namespaces`` list.
+
+   .. method:: namespace_detail(namespace)
+
+      Return the ``/namespace/<namespace>`` mapping with ``name``,
+      ``parent``, ``children`` and ``owner``.
+
+   .. method:: simple_html(project, files)
+
+      Render the HTML Simple index page.  It carries no namespace
+      metadata by design.
+
+Security policies
+-----------------
+
+.. class:: SecurityPolicy(namespaces, owner)
+
+   Admit only dependencies inside *owner*'s granted namespaces.
+
+   .. method:: allows(project, index)
+
+      Return true if *project* may be installed from *index*.
+
+   .. method:: evaluate(requirements, index)
+
+      Map each requirement to admitted-or-not.
+
+Command line
+------------
+
+.. program:: packagenamespaces
+
+Use ``python -m packagenamespaces`` to manage grants.  Global option
+:option:`--store` selects the JSON store file.  Subcommands:
+
+* ``reserve NAMESPACE --owner OWNER``
+* ``list [--json]``
+* ``show NAMESPACE [--json]``
+* ``remove NAMESPACE``
+* ``register PROJECT --owner OWNER``
+* ``grandfather PROJECT --owner OWNER``
+* ``check-upload PROJECT --owner OWNER`` (exit status 3 on 409 Conflict)
+* ``dump [--project PROJECT]``
+
+.. seealso::
+
+   :pep:`752` -- Implicit namespaces for package repositories
+      The specification this module implements.
+
+   :pep:`691` -- JSON-based Simple API for Python Package Indexes
+      Version 1.5 carries the namespace metadata.
diff --git a/Doc/whatsnew/3.16.rst b/Doc/whatsnew/3.16.rst
index dcfa9ff..23231d2 100644
--- a/Doc/whatsnew/3.16.rst
+++ b/Doc/whatsnew/3.16.rst
@@ -120,7 +120,10 @@ Default interactive shell
 New modules
 ===========
 
-* None yet.
+* :mod:`packagenamespaces`: implement :pep:`752` (implicit namespaces for
+  package repositories) -- namespace grants with overlap detection,
+  upload authorization, version 1.5 JSON Simple API metadata and
+  installer security policies.
 
 
 Improved modules
diff --git a/Lib/packagenamespaces/__init__.py b/Lib/packagenamespaces/__init__.py
new file mode 100644
index 0000000..6481620
--- /dev/null
+++ b/Lib/packagenamespaces/__init__.py
@@ -0,0 +1,65 @@
+"""Implicit namespaces for package repositories (PEP 752).
+
+This package implements PEP 752: organizations reserve package-name
+prefixes, uploads under a reserved prefix require an active grant, and
+repositories expose the grants through version 1.5 of the JSON Simple
+API so installers can enforce namespace security policies.
+"""
+
+from __future__ import annotations
+
+from .cli import CONFLICT_EXIT, build_parser, main
+from .grants import (
+    DEFAULT_DEPTH_LIMIT,
+    DepthLimitError,
+    Grant,
+    GrantError,
+    GrantStore,
+    InvalidNamespaceError,
+    OverlapError,
+    UnknownGrantError,
+    grants_overlap,
+)
+from .matching import namespace_matches
+from .metadata import (
+    API_VERSION,
+    LEGACY_API_VERSION,
+    NotSupportedError,
+    RepositoryIndex,
+)
+from .normalize import hyphen_depth, is_valid_namespace, normalize_name
+from .policy import SecurityPolicy
+from .uploads import (
+    CONFLICT_STATUS,
+    GrandfatheredRegistry,
+    UploadConflictError,
+    authorize_upload,
+)
+
+__all__ = [
+    "API_VERSION",
+    "LEGACY_API_VERSION",
+    "CONFLICT_EXIT",
+    "CONFLICT_STATUS",
+    "DEFAULT_DEPTH_LIMIT",
+    "DepthLimitError",
+    "Grant",
+    "GrantError",
+    "GrantStore",
+    "GrandfatheredRegistry",
+    "InvalidNamespaceError",
+    "NotSupportedError",
+    "OverlapError",
+    "RepositoryIndex",
+    "SecurityPolicy",
+    "UnknownGrantError",
+    "UploadConflictError",
+    "authorize_upload",
+    "build_parser",
+    "grants_overlap",
+    "hyphen_depth",
+    "is_valid_namespace",
+    "main",
+    "namespace_matches",
+    "normalize_name",
+]
diff --git a/Lib/packagenamespaces/__main__.py b/Lib/packagenamespaces/__main__.py
new file mode 100644
index 0000000..eef704d
--- /dev/null
+++ b/Lib/packagenamespaces/__main__.py
@@ -0,0 +1,8 @@
+"""Run the grant-management CLI: ``python -m packagenamespaces ...``."""
+
+from __future__ import annotations
+
+from .cli import main
+
+if __name__ == "__main__":
+    raise SystemExit(main())
diff --git a/Lib/packagenamespaces/cli.py b/Lib/packagenamespaces/cli.py
new file mode 100644
index 0000000..51af654
--- /dev/null
+++ b/Lib/packagenamespaces/cli.py
@@ -0,0 +1,290 @@
+"""Grant-management command line for package namespaces (PEP 752).
+
+State lives in a JSON store file (see ``--store``)::
+
+    {"grants": {"acme": "acme-corp"},
+     "projects": {"acme-widget": "acme-corp"},
+     "grandfathered": ["acme-legacy"]}
+"""
+
+from __future__ import annotations
+
+import argparse
+import json
+import os
+import sys
+
+from .grants import GrantError, GrantStore, UnknownGrantError
+from .metadata import RepositoryIndex
+from .normalize import normalize_name
+from .uploads import CONFLICT_STATUS, UploadConflictError, authorize_upload
+
+__all__ = ["main", "build_parser"]
+
+#: Exit status when check-upload refuses an upload (a 409 Conflict).
+CONFLICT_EXIT = 3
+
+DEFAULT_STORE = os.path.expanduser("~/.packagenamespaces.json")
+
+
+def build_parser() -> argparse.ArgumentParser:
+    """Build the ``packagenamespaces`` argument parser."""
+    parser = argparse.ArgumentParser(
+        prog="packagenamespaces",
+        description="Manage PEP 752 package-namespace grants.",
+    )
+    parser.add_argument(
+        "--store",
+        default=DEFAULT_STORE,
+        help="JSON file holding grants, projects and exemptions "
+        f"(default: {DEFAULT_STORE})",
+    )
+    sub = parser.add_subparsers(dest="command", required=True)
+
+    reserve = sub.add_parser("reserve", help="Reserve a namespace for an owner.")
+    reserve.add_argument("namespace", help="Namespace to reserve.")
+    reserve.add_argument("--owner", required=True, help="Grant owner.")
+
+    sub.add_parser("list", help="List every active grant.").add_argument(
+        "--json", action="store_true", help="Emit JSON instead of text."
+    )
+
+    show = sub.add_parser("show", help="Show one grant in detail.")
+    show.add_argument("namespace", help="Namespace to show.")
+    show.add_argument("--json", action="store_true", help="Emit JSON.")
+
+    remove = sub.add_parser("remove", help="Remove a grant.")
+    remove.add_argument("namespace", help="Namespace to release.")
+
+    register = sub.add_parser(
+        "register", help="Record a project's owner."
+    )
+    register.add_argument("project", help="Project name.")
+    register.add_argument("--owner", required=True, help="Project owner.")
+
+    grandfather = sub.add_parser(
+        "grandfather",
+        help="Exempt a pre-existing project from later reservations.",
+    )
+    grandfather.add_argument("project", help="Project name.")
+    grandfather.add_argument("--owner", required=True, help="Project owner.")
+
+    check = sub.add_parser(
+        "check-upload", help="Check whether an upload would be allowed."
+    )
+    check.add_argument("project", help="Project name.")
+    check.add_argument("--owner", required=True, help="Uploading owner.")
+
+    dump = sub.add_parser("dump", help="Dump repository metadata as JSON.")
+    dump.add_argument(
+        "--project",
+        default=None,
+        help="Dump one project-detail mapping instead of the index.",
+    )
+    return parser
+
+
+def _load_index(path: str) -> RepositoryIndex:
+    index = RepositoryIndex(store=GrantStore())
+    try:
+        with open(path, encoding="utf-8") as handle:
+            state = json.load(handle)
+    except FileNotFoundError:
+        return index
+    except (OSError, ValueError) as exc:
+        raise GrantError(f"cannot read store {path!r}: {exc}") from exc
+    if not isinstance(state, dict):
+        raise GrantError(f"store {path!r} does not hold a JSON object")
+    grants = state.get("grants", {})
+    if not isinstance(grants, dict):
+        raise GrantError(f"store {path!r} has a non-object 'grants' key")
+    try:
+        for namespace, owner in grants.items():
+            index.store.reserve(namespace, owner)
+    except GrantError:
+        raise
+    except (ValueError, TypeError) as exc:
+        raise GrantError(
+            f"store {path!r} holds an invalid grant entry: {exc}"
+        ) from exc
+    projects = state.get("projects", {})
+    if not isinstance(projects, dict):
+        raise GrantError(f"store {path!r} has a non-object 'projects' key")
+    try:
+        for project, owner in projects.items():
+            index.register_project(project, owner)
+    except GrantError:
+        raise
+    except (ValueError, TypeError) as exc:
+        raise GrantError(
+            f"store {path!r} holds an invalid project entry: {exc}"
+        ) from exc
+    grandfathered = state.get("grandfathered", [])
+    if not isinstance(grandfathered, list):
+        raise GrantError(
+            f"store {path!r} has a non-array 'grandfathered' key"
+        )
+    try:
+        for project in grandfathered:
+            index.grandfathered.add(project)
+    except GrantError:
+        raise
+    except (ValueError, TypeError) as exc:
+        raise GrantError(
+            f"store {path!r} holds an invalid grandfathered entry: {exc}"
+        ) from exc
+    return index
+
+
+def _save_index(path: str, index: RepositoryIndex) -> None:
+    state = {
+        "grants": {
+            name: index.store.get(name).owner
+            for name in index.store.namespaces()
+        },
+        "projects": {
+            project: index.project_owner(project)
+            for project in index.projects()
+        },
+        "grandfathered": index.grandfathered.projects(),
+    }
+    directory = os.path.dirname(os.path.abspath(path))
+    os.makedirs(directory, exist_ok=True)
+    with open(path, "w", encoding="utf-8") as handle:
+        json.dump(state, handle, indent=2, sort_keys=True)
+        handle.write("\n")
+
+
+def _cmd_reserve(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    grant = index.store.reserve(args.namespace, args.owner)
+    print(f"reserved {grant.name} for {grant.owner}")
+    return 0
+
+
+def _cmd_list(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    if args.json:
+        print(
+            json.dumps(
+                [
+                    {"name": name, "owner": index.store.get(name).owner}
+                    for name in index.store.namespaces()
+                ]
+            )
+        )
+    else:
+        for name in index.store.namespaces():
+            print(f"{name} {index.store.get(name).owner}")
+    return 0
+
+
+def _cmd_show(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    detail = index.namespace_detail(args.namespace)
+    if args.json:
+        print(json.dumps(detail, sort_keys=True))
+    else:
+        print(f"name: {detail['name']}")
+        print(f"owner: {detail['owner']}")
+        parent = detail["parent"]
+        print(f"parent: {parent if parent is not None else 'none'}")
+        children = detail["children"]
+        print(f"children: {','.join(children) if children else 'none'}")
+    return 0
+
+
+def _cmd_remove(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    grant = index.store.remove(args.namespace)
+    print(f"removed {grant.name}")
+    return 0
+
+
+def _cmd_register(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    index.register_project(args.project, args.owner)
+    print(f"registered {normalize_name(args.project)} for {args.owner}")
+    return 0
+
+
+def _cmd_grandfather(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    index.register_project(args.project, args.owner)
+    normalized = normalize_name(args.project)
+    index.grandfathered.add(normalized)
+    print(f"grandfathered {normalized}")
+    return 0
+
+
+def _cmd_check_upload(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    try:
+        authorize_upload(
+            args.project,
+            args.owner,
+            index.store,
+            grandfathered=index.grandfathered,
+        )
+    except UploadConflictError as exc:
+        print(
+            f"{CONFLICT_STATUS} Conflict: project {exc.project!r} matches "
+            f"reserved namespace {exc.namespace!r}",
+            file=sys.stderr,
+        )
+        return CONFLICT_EXIT
+    print(f"OK {normalize_name(args.project)}")
+    return 0
+
+
+def _cmd_dump(index: RepositoryIndex, args: argparse.Namespace) -> int:
+    if args.project is not None:
+        print(json.dumps(index.project_detail(args.project), sort_keys=True))
+    else:
+        print(
+            json.dumps(
+                {
+                    "api_version": index.api_version,
+                    "namespaces": index.list_namespaces(),
+                },
+                sort_keys=True,
+            )
+        )
+    return 0
+
+
+_COMMANDS = {
+    "reserve": (_cmd_reserve, True),
+    "list": (_cmd_list, False),
+    "show": (_cmd_show, False),
+    "remove": (_cmd_remove, True),
+    "register": (_cmd_register, True),
+    "grandfather": (_cmd_grandfather, True),
+    "check-upload": (_cmd_check_upload, False),
+    "dump": (_cmd_dump, False),
+}
+
+
+def main(argv: list[str] | None = None) -> int:
+    """Run the CLI; return the process exit status."""
+    args = build_parser().parse_args(argv)
+    try:
+        index = _load_index(args.store)
+    except GrantError as exc:
+        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
+        return 1
+    command, persists = _COMMANDS[args.command]
+    try:
+        status = command(index, args)
+    except UnknownGrantError as exc:
+        print(f"packagenamespaces: error: unknown grant: {exc}", file=sys.stderr)
+        return 1
+    except GrantError as exc:
+        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
+        return 1
+    except (ValueError, UploadConflictError) as exc:
+        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
+        return 1
+    if status == 0 and persists:
+        try:
+            _save_index(args.store, index)
+        except OSError as exc:
+            print(
+                f"packagenamespaces: error: cannot write {args.store!r}: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+    return status
diff --git a/Lib/packagenamespaces/grants.py b/Lib/packagenamespaces/grants.py
new file mode 100644
index 0000000..3b62189
--- /dev/null
+++ b/Lib/packagenamespaces/grants.py
@@ -0,0 +1,222 @@
+"""Grant lifecycle for package namespaces (PEP 752, Semantics).
+
+A grant reserves a namespace for one owner on one package repository.
+Grants MUST NOT overlap ownership: a proposed namespace that overlaps an
+existing grant held by a different owner is rejected.  Overlap is
+bidirectional -- a longer namespace under an existing grant overlaps just
+as a shorter one over it does -- and is decided by appending a hyphen to
+both normalized names and comparing in both directions, so ``"foo"`` and
+``"foobar"`` never overlap.
+"""
+
+from __future__ import annotations
+
+import dataclasses
+
+from .matching import namespace_matches
+from .normalize import hyphen_depth, is_valid_namespace, normalize_name
+
+__all__ = [
+    "DEFAULT_DEPTH_LIMIT",
+    "Grant",
+    "GrantError",
+    "InvalidNamespaceError",
+    "OverlapError",
+    "DepthLimitError",
+    "UnknownGrantError",
+    "grants_overlap",
+    "GrantStore",
+]
+
+#: Default cap on the number of hyphens in a granted namespace.  ``None``
+#: disables the limit; repositories SHOULD impose one.
+DEFAULT_DEPTH_LIMIT = 3
+
+
+class GrantError(Exception):
+    """Base class for grant-store errors."""
+
+
+class InvalidNamespaceError(GrantError, ValueError):
+    """A namespace is not a valid project name."""
+
+
+class OverlapError(GrantError):
+    """A proposed namespace overlaps a grant held by another owner."""
+
+
+class DepthLimitError(GrantError):
+    """A proposed namespace exceeds the store's hyphen depth limit."""
+
+
+class UnknownGrantError(GrantError):
+    """No active grant exists for a namespace."""
+
+
+@dataclasses.dataclass(frozen=True, slots=True)
+class Grant:
+    """A reservation of *name* (normalized) for *owner*."""
+
+    name: str
+    owner: str
+
+
+def grants_overlap(first: str, second: str) -> bool:
+    """Return True if two namespaces overlap.
+
+    Both names are normalized and a hyphen is appended to each before the
+    comparison runs in both directions, so ``"foo"`` overlaps ``"foo-bar"``
+    in either argument order while ``"foo"`` and ``"foobar"`` do not.
+    """
+    first_hyphenated = normalize_name(first) + "-"
+    second_hyphenated = normalize_name(second) + "-"
+    return first_hyphenated.startswith(second_hyphenated) or (
+        second_hyphenated.startswith(first_hyphenated)
+    )
+
+
+def _check_owner(owner: str) -> str:
+    if not isinstance(owner, str) or not owner:
+        raise ValueError("owner must be a non-empty string")
+    return owner
+
+
+class GrantStore:
+    """The active namespace grants of one package repository.
+
+    Grants are per-repository and are never shared between repositories.
+    """
+
+    def __init__(self, depth_limit: int | None = DEFAULT_DEPTH_LIMIT) -> None:
+        """Create a store; *depth_limit* caps hyphens per namespace.
+
+        ``None`` disables the limit.
+        """
+        self._depth_limit = depth_limit
+        self._grants: dict[str, Grant] = {}
+
+    @property
+    def depth_limit(self) -> int | None:
+        """The configured hyphen depth limit, or None if unlimited."""
+        return self._depth_limit
+
+    def __len__(self) -> int:
+        return len(self._grants)
+
+    def __contains__(self, namespace: object) -> bool:
+        return isinstance(namespace, str) and (
+            normalize_name(namespace) in self._grants
+        )
+
+    def reserve(self, namespace: str, owner: str) -> Grant:
+        """Reserve *namespace* for *owner* and return the new grant.
+
+        The name must be valid and within the depth limit.  A namespace
+        that overlaps an existing grant may only be reserved by that
+        grant's owner; anyone else gets :exc:`OverlapError`.  Reserving
+        the exact same namespace for the same owner is idempotent.
+        """
+        if not is_valid_namespace(namespace):
+            raise InvalidNamespaceError(f"{namespace!r} is not a valid namespace")
+        normalized = normalize_name(namespace)
+        if (
+            self._depth_limit is not None
+            and hyphen_depth(normalized) > self._depth_limit
+        ):
+            raise DepthLimitError(
+                f"{normalized!r} has {hyphen_depth(normalized)} hyphens, "
+                f"above the limit of {self._depth_limit}"
+            )
+        _check_owner(owner)
+        for existing in self._grants.values():
+            if grants_overlap(normalized, existing.name) and (
+                existing.owner != owner
+            ):
+                raise OverlapError(
+                    f"{normalized!r} overlaps the grant for {existing.name!r} "
+                    f"held by {existing.owner!r}"
+                )
+        grant = Grant(name=normalized, owner=owner)
+        self._grants[normalized] = grant
+        return grant
+
+    def transfer(self, namespace: str, new_owner: str) -> Grant:
+        """Move the grant for *namespace* to *new_owner*."""
+        normalized = normalize_name(namespace)
+        try:
+            current = self._grants[normalized]
+        except KeyError:
+            raise UnknownGrantError(
+                f"no active grant for {normalized!r}"
+            ) from None
+        _check_owner(new_owner)
+        for existing in self._grants.values():
+            if (
+                existing.name != normalized
+                and grants_overlap(normalized, existing.name)
+                and existing.owner != new_owner
+            ):
+                raise OverlapError(
+                    f"transfer of {normalized!r} to {new_owner!r} overlaps "
+                    f"the grant for {existing.name!r} "
+                    f"held by {existing.owner!r}"
+                )
+        moved = Grant(name=current.name, owner=new_owner)
+        self._grants[normalized] = moved
+        return moved
+
+    def remove(self, namespace: str) -> Grant:
+        """Remove the grant for *namespace* and return it."""
+        normalized = normalize_name(namespace)
+        try:
+            return self._grants.pop(normalized)
+        except KeyError:
+            raise UnknownGrantError(
+                f"no active grant for {normalized!r}"
+            ) from None
+
+    def get(self, namespace: str) -> Grant | None:
+        """Return the grant for *namespace*, or None if there is none."""
+        return self._grants.get(normalize_name(namespace))
+
+    def namespaces(self) -> list[str]:
+        """Return every granted namespace, sorted."""
+        return sorted(self._grants)
+
+    def matching(self, project: str) -> list[Grant]:
+        """Return the grants whose namespace matches *project*, sorted."""
+        return sorted(
+            (
+                grant
+                for grant in self._grants.values()
+                if namespace_matches(grant.name, project)
+            ),
+            key=lambda grant: grant.name,
+        )
+
+    def parent(self, namespace: str) -> str | None:
+        """Return the granted parent of *namespace*, or None.
+
+        The parent is the namespace without its trailing hyphenated
+        component; it is only reported when it holds an active grant.
+        """
+        normalized = normalize_name(namespace)
+        parent, _, _ = normalized.rpartition("-")
+        if parent and parent in self._grants:
+            return parent
+        return None
+
+    def children(self, namespace: str) -> list[str]:
+        """Return the granted direct children of *namespace*, sorted.
+
+        Only single-component extensions count: with grants for ``"foo"``,
+        ``"foo-bar"`` and ``"foo-bar-baz"``, the children of ``"foo"`` are
+        ``["foo-bar"]``.
+        """
+        normalized = normalize_name(namespace)
+        prefix = normalized + "-"
+        return sorted(
+            name
+            for name in self._grants
+            if name.startswith(prefix) and "-" not in name[len(prefix):]
+        )
diff --git a/Lib/packagenamespaces/matching.py b/Lib/packagenamespaces/matching.py
new file mode 100644
index 0000000..a531389
--- /dev/null
+++ b/Lib/packagenamespaces/matching.py
@@ -0,0 +1,28 @@
+"""Project matching for namespace grants (PEP 752, Semantics).
+
+A grant bestows ownership over the project that exactly matches the
+namespace and over every project that starts with the namespace followed
+by a hyphen: ``"foo"`` matches ``"foo"`` and ``"foo-bar"`` but not
+``"foobar"``.  Both sides are normalized before they are compared.
+"""
+
+from __future__ import annotations
+
+from .normalize import normalize_name
+
+__all__ = ["namespace_matches"]
+
+
+def namespace_matches(namespace: str, project: str) -> bool:
+    """Return True if *project* falls under *namespace*.
+
+    The comparison is exact-match or namespace-plus-hyphen-prefix, after
+    normalizing both inputs.  For example ``namespace_matches("foo",
+    "foo-bar")`` is True while ``namespace_matches("foo", "foobar")`` is
+    False.
+    """
+    normalized_ns = normalize_name(namespace)
+    normalized_project = normalize_name(project)
+    return normalized_project == normalized_ns or normalized_project.startswith(
+        normalized_ns + "-"
+    )
diff --git a/Lib/packagenamespaces/metadata.py b/Lib/packagenamespaces/metadata.py
new file mode 100644
index 0000000..e155f94
--- /dev/null
+++ b/Lib/packagenamespaces/metadata.py
@@ -0,0 +1,147 @@
+"""Repository metadata for namespaces (PEP 752, Repository Metadata).
+
+Repositories that support this PEP serve version 1.5 of the JSON Simple
+API: the project detail gains a ``namespaces`` key, and the
+``/namespaces`` list and ``/namespace/<namespace>`` detail endpoints
+appear.  Repositories that do not support the PEP stay on version 1.4
+and emit none of this, so consumers can tell the two apart.  The HTML
+Simple API is deliberately untouched.
+"""
+
+from __future__ import annotations
+
+import html
+
+from .grants import GrantStore, UnknownGrantError
+from .normalize import normalize_name
+from .uploads import GrandfatheredRegistry
+
+__all__ = [
+    "API_VERSION",
+    "LEGACY_API_VERSION",
+    "NotSupportedError",
+    "RepositoryIndex",
+]
+
+#: JSON Simple API version of a repository that supports PEP 752.
+API_VERSION = "1.5"
+
+#: JSON Simple API version of a repository that does not.
+LEGACY_API_VERSION = "1.4"
+
+
+class NotSupportedError(Exception):
+    """A namespace endpoint was queried on a repository without PEP 752."""
+
+
+class RepositoryIndex:
+    """One package repository's namespace metadata (PEP 691, version 1.5)."""
+
+    def __init__(
+        self, store: GrantStore | None = None, *, supports_namespaces: bool = True
+    ) -> None:
+        """Create an index over *store* (a fresh one if omitted).
+
+        Pass ``supports_namespaces=False`` for a legacy repository that
+        does not implement this PEP.
+        """
+        self.store = store if store is not None else GrantStore()
+        self.supports_namespaces = supports_namespaces
+        self.grandfathered = GrandfatheredRegistry()
+        self._owners: dict[str, str] = {}
+
+    @property
+    def api_version(self) -> str:
+        """``"1.5"`` on a supporting repository, ``"1.4"`` on a legacy one."""
+        return API_VERSION if self.supports_namespaces else LEGACY_API_VERSION
+
+    def register_project(self, project: str, owner: str) -> None:
+        """Record that *owner* owns *project*."""
+        if not isinstance(owner, str) or not owner:
+            raise ValueError("owner must be a non-empty string")
+        self._owners[normalize_name(project)] = owner
+
+    def project_owner(self, project: str) -> str | None:
+        """Return the recorded owner of *project*, or None if unknown."""
+        return self._owners.get(normalize_name(project))
+
+    def projects(self) -> list[str]:
+        """Return every registered project, sorted."""
+        return sorted(self._owners)
+
+    def project_detail(self, project: str) -> dict:
+        """Return the project-detail mapping for *project*.
+
+        The ``namespaces`` key is None when the project matches no active
+        grant, and otherwise an array of ``{"name", "owned"}`` mappings,
+        one per matching namespace, sorted by name.  ``owned`` is True
+        when the project's recorded owner holds that grant -- a
+        grandfathered project that kept uploading reports False.  Legacy
+        repositories omit the ``namespaces`` key entirely.
+        """
+        normalized = normalize_name(project)
+        detail: dict = {"name": normalized}
+        if not self.supports_namespaces:
+            return detail
+        matches = self.store.matching(normalized)
+        if not matches:
+            detail["namespaces"] = None
+            return detail
+        owner = self._owners.get(normalized)
+        detail["namespaces"] = [
+            {"name": grant.name, "owned": owner == grant.owner}
+            for grant in matches
+        ]
+        return detail
+
+    def list_namespaces(self) -> list[dict]:
+        """Return the ``/namespaces`` list: one ``{"name"}`` per grant."""
+        if not self.supports_namespaces:
+            raise NotSupportedError(
+                "this repository does not support PEP 752 namespaces"
+            )
+        return [{"name": name} for name in self.store.namespaces()]
+
+    def namespace_detail(self, namespace: str) -> dict:
+        """Return the ``/namespace/<namespace>`` detail mapping.
+
+        The mapping carries ``name``, ``parent`` (the granted parent or
+        None), ``children`` (granted direct children) and ``owner``.
+        """
+        if not self.supports_namespaces:
+            raise NotSupportedError(
+                "this repository does not support PEP 752 namespaces"
+            )
+        normalized = normalize_name(namespace)
+        grant = self.store.get(normalized)
+        if grant is None:
+            raise UnknownGrantError(f"no active grant for {normalized!r}")
+        return {
+            "name": grant.name,
+            "parent": self.store.parent(normalized),
+            "children": self.store.children(normalized),
+            "owner": grant.owner,
+        }
+
+    def simple_html(self, project: str, files: list[dict]) -> str:
+        """Render the HTML Simple index page for *project*.
+
+        *files* maps each artifact to its ``filename`` and ``url``.  The
+        page carries no namespace metadata at all: exposing it here was
+        rejected, and this output must stay byte-identical with or
+        without namespace grants in place.
+        """
+        normalized = normalize_name(project)
+        lines = [
+            "<!DOCTYPE html>",
+            "<html>",
+            f"  <head><title>Links for {html.escape(normalized)}</title></head>",
+            "  <body>",
+            f"    <h1>Links for {html.escape(normalized)}</h1>",
+        ]
+        for entry in files:
+            filename = html.escape(entry["filename"], quote=True)
+            url = html.escape(entry["url"], quote=True)
+            lines.append(f'    <a href="{url}">{filename}</a><br/>')
+        lines.extend(["  </body>", "</html>", ""])
+        return "\n".join(lines)
diff --git a/Lib/packagenamespaces/normalize.py b/Lib/packagenamespaces/normalize.py
new file mode 100644
index 0000000..b047a63
--- /dev/null
+++ b/Lib/packagenamespaces/normalize.py
@@ -0,0 +1,58 @@
+"""Name normalization and validation for package namespaces (PEP 752).
+
+A namespace MUST be a `valid project name
+<https://packaging.python.org/en/latest/specifications/name-normalization/#name-format>`_
+and is stored and compared in `normalized
+<https://packaging.python.org/en/latest/specifications/name-normalization/#name-normalization>`_
+form.  Normalization runs before every comparison in this package.
+"""
+
+from __future__ import annotations
+
+import re
+
+__all__ = ["normalize_name", "is_valid_namespace", "hyphen_depth"]
+
+#: Matches a run of name separators; each run folds to one hyphen.
+_SEPARATORS_RE = re.compile(r"[-_.]+")
+
+#: The Name Format rule from the normalization spec: ASCII letters and digits
+#: at both ends, separators only in the middle.
+_VALID_NAME_RE = re.compile(
+    r"^([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9])$"
+)
+
+
+def normalize_name(name: str) -> str:
+    """Return the normalized form of *name*.
+
+    Every run of ``-``, ``_`` and ``.`` becomes a single ``-`` and the
+    result is lowercased, so ``"Foo.bar_baz"`` becomes ``"foo-bar-baz"``.
+
+    Raises :exc:`TypeError` if *name* is not a string.
+    """
+    if not isinstance(name, str):
+        raise TypeError(f"name must be str, not {type(name).__name__}")
+    return _SEPARATORS_RE.sub("-", name).lower()
+
+
+def is_valid_namespace(name: str) -> bool:
+    """Return True if *name* is a valid namespace.
+
+    Anything that is not a string, is empty, or does not match the Name
+    Format rule (alphanumerics at both ends) is invalid.
+    """
+    if not isinstance(name, str):
+        return False
+    # fullmatch, not match: "$" matches before a trailing newline, so
+    # match() would accept "foo\n" as valid.
+    return _VALID_NAME_RE.fullmatch(name) is not None
+
+
+def hyphen_depth(name: str) -> int:
+    """Return the number of hyphens in the normalized form of *name*.
+
+    Repositories use this to enforce a depth limit: with a limit of ``1``
+    the namespace ``"foo-bar"`` is allowed but ``"foo-bar-baz"`` is not.
+    """
+    return normalize_name(name).count("-")
diff --git a/Lib/packagenamespaces/policy.py b/Lib/packagenamespaces/policy.py
new file mode 100644
index 0000000..5eba589
--- /dev/null
+++ b/Lib/packagenamespaces/policy.py
@@ -0,0 +1,85 @@
+"""Installer security policies for namespaces (PEP 752, Security Implications).
+
+Installers may offer a policy that only admits dependencies matching a
+configured set of namespaces when the installing owner holds an active
+grant for them.  Grants never cross repositories: a grant on one index
+confers nothing on another, so every evaluation names the index it
+trusts.
+"""
+
+from __future__ import annotations
+
+from collections.abc import Iterable
+
+from .grants import InvalidNamespaceError
+from .matching import namespace_matches
+from .metadata import RepositoryIndex
+from .normalize import is_valid_namespace, normalize_name
+
+__all__ = ["SecurityPolicy"]
+
+
+class SecurityPolicy:
+    """Admit only dependencies inside *owner*'s granted namespaces."""
+
+    def __init__(self, namespaces: Iterable[str], owner: str) -> None:
+        """Create a policy over *namespaces* for the installing *owner*.
+
+        Every namespace must be valid; the owner must be a non-empty
+        string.
+        """
+        allowed = []
+        for namespace in namespaces:
+            if not is_valid_namespace(namespace):
+                raise InvalidNamespaceError(
+                    f"{namespace!r} is not a valid namespace"
+                )
+            allowed.append(normalize_name(namespace))
+        if not isinstance(owner, str) or not owner:
+            raise ValueError("owner must be a non-empty string")
+        self._namespaces = tuple(allowed)
+        self._owner = owner
+
+    @property
+    def namespaces(self) -> tuple[str, ...]:
+        """The policy's namespaces, normalized, in configured order."""
+        return self._namespaces
+
+    @property
+    def owner(self) -> str:
+        """The installing owner this policy admits dependencies for."""
+        return self._owner
+
+    def allows(self, project: str, index: RepositoryIndex) -> bool:
+        """Return True if *project* may be installed from *index*.
+
+        The project's recorded owner must be this policy's owner, and
+        the project must match a policy namespace with an active grant
+        for that same owner on this index.  Unknown owners, ungranted
+        namespaces and grants on any other index all deny.
+        """
+        normalized = normalize_name(project)
+        if index.project_owner(normalized) != self._owner:
+            return False
+        for namespace in self._namespaces:
+            if not namespace_matches(namespace, normalized):
+                continue
+            grant = index.store.get(namespace)
+            if grant is not None and grant.owner == self._owner:
+                return True
+        return False
+
+    def evaluate(
+        self, requirements: Iterable[str], index: RepositoryIndex
+    ) -> dict[str, bool]:
+        """Evaluate every requirement against *index*.
+
+        Returns a mapping of normalized project name to admitted-or-not,
+        in requirement order.
+        """
+        verdicts: dict[str, bool] = {}
+        for requirement in requirements:
+            verdicts[normalize_name(requirement)] = self.allows(
+                requirement, index
+            )
+        return verdicts
diff --git a/Lib/packagenamespaces/uploads.py b/Lib/packagenamespaces/uploads.py
new file mode 100644
index 0000000..b01afd4
--- /dev/null
+++ b/Lib/packagenamespaces/uploads.py
@@ -0,0 +1,101 @@
+"""Upload authorization for reserved namespaces (PEP 752, Uploads).
+
+An upload MUST fail with a 409 Conflict status when the project name
+matches a reserved namespace and the uploader holds no active grant for
+it.  Repositories SHOULD exempt projects that existed before the
+namespace was reserved; :class:`GrandfatheredRegistry` records those.
+"""
+
+from __future__ import annotations
+
+from .grants import GrantStore
+from .normalize import normalize_name
+
+__all__ = [
+    "CONFLICT_STATUS",
+    "UploadConflictError",
+    "GrandfatheredRegistry",
+    "authorize_upload",
+]
+
+#: HTTP status for an upload that violates a namespace grant.
+CONFLICT_STATUS = 409
+
+
+class UploadConflictError(Exception):
+    """An upload was refused because of a namespace grant.
+
+    Carries the normalized *project* name, the first matching reserved
+    *namespace*, and the *owner* that attempted the upload.
+    """
+
+    status_code = CONFLICT_STATUS
+
+    def __init__(self, project: str, namespace: str, owner: str) -> None:
+        super().__init__(
+            f"409 Conflict: project {project!r} matches reserved namespace "
+            f"{namespace!r} and owner {owner!r} holds no active grant for it"
+        )
+        self.project = project
+        self.namespace = namespace
+        self.owner = owner
+
+
+class GrandfatheredRegistry:
+    """Projects that predate the namespace reservation covering them."""
+
+    def __init__(self) -> None:
+        self._projects: set[str] = set()
+
+    def __len__(self) -> int:
+        return len(self._projects)
+
+    def __contains__(self, project: object) -> bool:
+        return isinstance(project, str) and (
+            normalize_name(project) in self._projects
+        )
+
+    def add(self, project: str) -> None:
+        """Record *project* as exempt from later reservations."""
+        self._projects.add(normalize_name(project))
+
+    def discard(self, project: str) -> None:
+        """Drop any exemption for *project*."""
+        self._projects.discard(normalize_name(project))
+
+    def covers(self, project: str) -> bool:
+        """Return True if *project* holds a grandfathered exemption."""
+        return normalize_name(project) in self._projects
+
+    def projects(self) -> list[str]:
+        """Return every exempt project, sorted."""
+        return sorted(self._projects)
+
+
+def authorize_upload(
+    project: str,
+    owner: str,
+    store: GrantStore,
+    *,
+    grandfathered: GrandfatheredRegistry | None = None,
+) -> bool:
+    """Authorize an upload of *project* by *owner* against *store*.
+
+    Returns True when the upload may proceed: the project matches no
+    reserved namespace, the owner holds one of the matching grants, or
+    the project is grandfathered.  Otherwise raises
+    :exc:`UploadConflictError`, whose :attr:`status_code` is 409.
+    The *owner* must be a non-empty string; anything else raises
+    :exc:`ValueError` before any grant is consulted.
+    """
+    if not isinstance(owner, str) or not owner:
+        raise ValueError("owner must be a non-empty string")
+    normalized = normalize_name(project)
+    matches = store.matching(normalized)
+    if not matches:
+        return True
+    if any(grant.owner == owner for grant in matches):
+        return True
+    if grandfathered is not None and grandfathered.covers(normalized):
+        return True
+    raise UploadConflictError(normalized, matches[0].name, owner)
diff --git a/Makefile.pre.in b/Makefile.pre.in
index e74deee..dc2a80d 100644
--- a/Makefile.pre.in
+++ b/Makefile.pre.in
@@ -2630,6 +2630,7 @@ LIBSUBDIRS=	asyncio \
 		json \
 		logging \
 		multiprocessing multiprocessing/dummy \
+		packagenamespaces \
 		pathlib \
 		profile \
 		profiling profiling/sampling profiling/tracing \
diff --git a/Misc/NEWS.d/next/Library/2026-11-04-12-00-00.pep-752.ss007.rst b/Misc/NEWS.d/next/Library/2026-11-04-12-00-00.pep-752.ss007.rst
new file mode 100644
index 0000000..932d41c
--- /dev/null
+++ b/Misc/NEWS.d/next/Library/2026-11-04-12-00-00.pep-752.ss007.rst
@@ -0,0 +1,3 @@
+Add :mod:`packagenamespaces`, implementing :pep:`752` (implicit namespaces
+for package repositories): namespace grants, upload authorization, JSON
+Simple API v1.5 metadata and installer security policies.
diff --git a/Python/stdlib_module_names.h b/Python/stdlib_module_names.h
index 565be27..78c082b 100644
--- a/Python/stdlib_module_names.h
+++ b/Python/stdlib_module_names.h
@@ -205,6 +205,7 @@ static const char* _Py_stdlib_module_names[] = {
 "operator",
 "optparse",
 "os",
+"packagenamespaces",
 "pathlib",
 "pdb",
 "pickle",
diff --git a/Tools/packagenamespaces/gen_fixtures.sh b/Tools/packagenamespaces/gen_fixtures.sh
new file mode 100755
index 0000000..d5ae0d4
--- /dev/null
+++ b/Tools/packagenamespaces/gen_fixtures.sh
@@ -0,0 +1,36 @@
+#!/bin/bash
+# Generate offline fixture indexes for PEP 752 namespace verification.
+#
+# Usage: gen_fixtures.sh <outdir>
+#
+# Writes four static JSON files describing a multi-grant repository, its
+# projects, its grandfathered exemptions and a second repository that
+# shares nothing with the first.  The files are embedded below so the
+# script needs no network and no tooling beyond a POSIX shell.
+set -euo pipefail
+
+if [ "$#" -ne 1 ]; then
+    echo "usage: gen_fixtures.sh <outdir>" >&2
+    exit 2
+fi
+
+OUTDIR="$1"
+mkdir -p "$OUTDIR"
+
+cat > "$OUTDIR/grants.json" <<'EOF'
+{"grants": [{"name": "acme", "owner": "acme-corp"}, {"name": "acme-widgets", "owner": "acme-corp"}, {"name": "airflow", "owner": "apache"}]}
+EOF
+
+cat > "$OUTDIR/projects.json" <<'EOF'
+{"projects": {"acme-widgets-sprocket": "acme-corp", "acme-legacy": "mallory", "airflow-httphook": "mallory", "requests": "psf"}}
+EOF
+
+cat > "$OUTDIR/grandfathered.json" <<'EOF'
+{"grandfathered": ["acme-legacy"]}
+EOF
+
+cat > "$OUTDIR/second-index.json" <<'EOF'
+{"grants": [], "projects": {"acme-widgets-sprocket": "acme-corp"}}
+EOF
+
+echo "wrote fixtures to $OUTDIR"
diff --git a/Tools/packagenamespaces/verify_offline.sh b/Tools/packagenamespaces/verify_offline.sh
new file mode 100755
index 0000000..fbcfc4c1166e0316abe5436520ac11580c733b64
--- /dev/null
+++ b/Tools/packagenamespaces/verify_offline.sh
@@ -0,0 +1,165 @@
+#!/bin/bash
+# Re-verify PEP 752 namespace fixtures with no network.
+#
+# Usage: verify_offline.sh <fixturedir>
+#
+# Loads the indexes written by gen_fixtures.sh and checks grant
+# overlap, upload authorization, installer policy and metadata
+# behavior, including that a grant on one index confers nothing on
+# another.  Pure local computation; safe under --network=none.
+set -euo pipefail
+
+if [ "$#" -ne 1 ]; then
+    echo "usage: verify_offline.sh <fixturedir>" >&2
+    exit 2
+fi
+
+FIXTUREDIR="$1"
+for needed in grants.json projects.json grandfathered.json second-index.json; do
+    if [ ! -f "$FIXTUREDIR/$needed" ]; then
+        echo "verify: FAIL missing fixture $needed" >&2
+        exit 1
+    fi
+done
+
+ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
+STAGE="$(mktemp -d)"
+trap 'rm -rf "$STAGE"' EXIT
+cp -r "$ROOT/Lib/packagenamespaces" "$STAGE/"
+
+PYTHON="${PYTHON:-python3}"
+FIXTUREDIR="$FIXTUREDIR" PYTHONPATH="$STAGE" "$PYTHON" - <<'PY'
+import json
+import os
+import sys
+
+sys.path.insert(0, os.environ["PYTHONPATH"])
+from packagenamespaces import (
+    GrantStore,
+    OverlapError,
+    RepositoryIndex,
+    SecurityPolicy,
+    UploadConflictError,
+    authorize_upload,
+)
+
+fixturedir = os.environ["FIXTUREDIR"]
+
+def load(name):
+    with open(os.path.join(fixturedir, name), encoding="utf-8") as handle:
+        return json.load(handle)
+
+def shape_fail(message):
+    print(f"verify: FAIL {message}", file=sys.stderr)
+    sys.exit(1)
+
+grants_doc = load("grants.json")
+projects_doc = load("projects.json")
+grandfathered_doc = load("grandfathered.json")
+second = load("second-index.json")
+
+grants = grants_doc.get("grants") if isinstance(grants_doc, dict) else None
+if not isinstance(grants, list) or any(
+    not isinstance(entry, dict)
+    or not isinstance(entry.get("name"), str)
+    or not isinstance(entry.get("owner"), str)
+    for entry in grants
+):
+    shape_fail("grants.json holds no valid grants list")
+projects = projects_doc.get("projects") if isinstance(projects_doc, dict) else None
+if not isinstance(projects, dict) or any(
+    not isinstance(project, str) or not isinstance(owner, str)
+    for project, owner in projects.items()
+):
+    shape_fail("projects.json holds no valid projects mapping")
+grandfathered = (
+    grandfathered_doc.get("grandfathered")
+    if isinstance(grandfathered_doc, dict)
+    else None
+)
+if not isinstance(grandfathered, list) or any(
+    not isinstance(project, str) for project in grandfathered
+):
+    shape_fail("grandfathered.json holds no valid exemptions list")
+second_grants = second.get("grants") if isinstance(second, dict) else None
+second_projects = second.get("projects") if isinstance(second, dict) else None
+if not isinstance(second_grants, list) or any(
+    not isinstance(entry, dict)
+    or not isinstance(entry.get("name"), str)
+    or not isinstance(entry.get("owner"), str)
+    for entry in second_grants
+):
+    shape_fail("second-index.json holds no valid grants list")
+if not isinstance(second_projects, dict) or any(
+    not isinstance(project, str) or not isinstance(owner, str)
+    for project, owner in second_projects.items()
+):
+    shape_fail("second-index.json holds no valid projects mapping")
+
+failures = []
+
+def check(label, condition):
+    print(f"verify: {label} {'ok' if condition else 'FAIL'}")
+    if not condition:
+        failures.append(label)
+
+store = GrantStore()
+for entry in grants:
+    store.reserve(entry["name"], entry["owner"])
+
+try:
+    store.reserve("acme-sneaky", "mallory")
+    check("overlap-rejected", False)
+except OverlapError:
+    check("overlap-rejected", True)
+
+index = RepositoryIndex(store)
+for project, owner in projects.items():
+    index.register_project(project, owner)
+for project in grandfathered:
+    index.grandfathered.add(project)
+
+check("upload-owner-allowed",
+      authorize_upload("acme-fresh", "acme-corp", store,
+                       grandfathered=index.grandfathered) is True)
+try:
+    authorize_upload("airflow-evil", "mallory", store,
+                     grandfathered=index.grandfathered)
+    check("upload-stranger-denied", False)
+except UploadConflictError as exc:
+    check("upload-stranger-denied", exc.status_code == 409)
+check("upload-grandfathered-allowed",
+      authorize_upload("acme-legacy", "mallory", store,
+                       grandfathered=index.grandfathered) is True)
+
+policy = SecurityPolicy(["acme"], "acme-corp")
+verdicts = policy.evaluate(
+    ["acme-widgets-sprocket", "acme-legacy", "requests"], index)
+check("policy-admits-granted", verdicts == {
+    "acme-widgets-sprocket": True,
+    "acme-legacy": False,
+    "requests": False,
+})
+
+mirror = RepositoryIndex(GrantStore())
+for project, owner in second["projects"].items():
+    mirror.register_project(project, owner)
+check("multirepo-not-shared",
+      policy.evaluate(["acme-widgets-sprocket"], mirror)
+      == {"acme-widgets-sprocket": False})
+
+check("api-version", index.api_version == "1.5")
+detail = index.project_detail("acme-widgets-sprocket")
+check("detail-namespaces",
+      detail["namespaces"] == [{"name": "acme", "owned": True},
+                               {"name": "acme-widgets", "owned": True}])
+index.store.remove("acme")
+index.store.remove("acme-widgets")
+check("removal-nulls",
+      index.project_detail("acme-widgets-sprocket")["namespaces"] is None)
+
+if failures:
+    print(f"verify: {len(failures)} check(s) failed", file=sys.stderr)
+    sys.exit(1)
+print("verify: all checks passed")
+PY
__SOLUTION__

# Idempotent apply: Eval-GT replays solve.sh under `set -e` on the already
# patched tree, where both `git apply` and `patch` refuse and exit non-zero.
# Gate on --check; a present sentinel means "already applied", anything else
# is a genuine conflict and still fails loud.
if git apply --check solution_patch.diff >/dev/null 2>&1; then
  git apply --verbose solution_patch.diff || patch --fuzz=5 -p1 -i solution_patch.diff
elif [ -f Lib/packagenamespaces/__init__.py ]; then
  echo "solve.sh: solution already applied (sentinel present); skipping" >&2
else
  echo "solve.sh: solution patch does not apply and sentinel is missing" >&2
  exit 1
fi
rm -f solution_patch.diff
