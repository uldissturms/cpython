"""Repository metadata for namespaces (PEP 752, Repository Metadata).

Repositories that support this PEP serve version 1.5 of the JSON Simple
API: the project detail gains a ``namespaces`` key, and the
``/namespaces`` list and ``/namespace/<namespace>`` detail endpoints
appear.  Repositories that do not support the PEP stay on version 1.4
and emit none of this, so consumers can tell the two apart.  The HTML
Simple API is deliberately untouched.
"""

from __future__ import annotations

import html

from .grants import GrantStore, UnknownGrantError
from .normalize import normalize_name
from .uploads import GrandfatheredRegistry

__all__ = [
    "API_VERSION",
    "LEGACY_API_VERSION",
    "NotSupportedError",
    "RepositoryIndex",
]

#: JSON Simple API version of a repository that supports PEP 752.
API_VERSION = "1.5"

#: JSON Simple API version of a repository that does not.
LEGACY_API_VERSION = "1.4"


class NotSupportedError(Exception):
    """A namespace endpoint was queried on a repository without PEP 752."""


class RepositoryIndex:
    """One package repository's namespace metadata (PEP 691, version 1.5)."""

    def __init__(
        self, store: GrantStore | None = None, *, supports_namespaces: bool = True
    ) -> None:
        """Create an index over *store* (a fresh one if omitted).

        Pass ``supports_namespaces=False`` for a legacy repository that
        does not implement this PEP.
        """
        self.store = store if store is not None else GrantStore()
        self.supports_namespaces = supports_namespaces
        self.grandfathered = GrandfatheredRegistry()
        self._owners: dict[str, str] = {}

    @property
    def api_version(self) -> str:
        """``"1.5"`` on a supporting repository, ``"1.4"`` on a legacy one."""
        return API_VERSION if self.supports_namespaces else LEGACY_API_VERSION

    def register_project(self, project: str, owner: str) -> None:
        """Record that *owner* owns *project*."""
        if not isinstance(owner, str) or not owner:
            raise ValueError("owner must be a non-empty string")
        self._owners[normalize_name(project)] = owner

    def project_owner(self, project: str) -> str | None:
        """Return the recorded owner of *project*, or None if unknown."""
        return self._owners.get(normalize_name(project))

    def projects(self) -> list[str]:
        """Return every registered project, sorted."""
        return sorted(self._owners)

    def project_detail(self, project: str) -> dict:
        """Return the project-detail mapping for *project*.

        The ``namespaces`` key is None when the project matches no active
        grant, and otherwise an array of ``{"name", "owned"}`` mappings,
        one per matching namespace, sorted by name.  ``owned`` is True
        when the project's recorded owner holds that grant -- a
        grandfathered project that kept uploading reports False.  Legacy
        repositories omit the ``namespaces`` key entirely.
        """
        normalized = normalize_name(project)
        detail: dict = {"name": normalized}
        if not self.supports_namespaces:
            return detail
        matches = self.store.matching(normalized)
        if not matches:
            detail["namespaces"] = None
            return detail
        owner = self._owners.get(normalized)
        detail["namespaces"] = [
            {"name": grant.name, "owned": owner == grant.owner}
            for grant in matches
        ]
        return detail

    def list_namespaces(self) -> list[dict]:
        """Return the ``/namespaces`` list: one ``{"name"}`` per grant."""
        if not self.supports_namespaces:
            raise NotSupportedError(
                "this repository does not support PEP 752 namespaces"
            )
        return [{"name": name} for name in self.store.namespaces()]

    def namespace_detail(self, namespace: str) -> dict:
        """Return the ``/namespace/<namespace>`` detail mapping.

        The mapping carries ``name``, ``parent`` (the granted parent or
        None), ``children`` (granted direct children) and ``owner``.
        """
        if not self.supports_namespaces:
            raise NotSupportedError(
                "this repository does not support PEP 752 namespaces"
            )
        normalized = normalize_name(namespace)
        grant = self.store.get(normalized)
        if grant is None:
            raise UnknownGrantError(f"no active grant for {normalized!r}")
        return {
            "name": grant.name,
            "parent": self.store.parent(normalized),
            "children": self.store.children(normalized),
            "owner": grant.owner,
        }

    def simple_html(self, project: str, files: list[dict]) -> str:
        """Render the HTML Simple index page for *project*.

        *files* maps each artifact to its ``filename`` and ``url``.  The
        page carries no namespace metadata at all: exposing it here was
        rejected, and this output must stay byte-identical with or
        without namespace grants in place.
        """
        # ALTERNATE renderer (pos control): a different but equally valid
        # page. Other title/heading wording that still names the project,
        # a list layout instead of <br/> separators, an extra anchor
        # attribute, single-string join instead of indented lines. The
        # graded HTML test must accept this, not just the reference bytes.
        normalized = normalize_name(project)
        parts = [
            "<!doctype HTML>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">'
            f"<title>{html.escape(normalized)} - package files</title>",
            "</head>",
            "<body>",
            f"<h1>Files for {html.escape(normalized)}</h1>",
            "<ul>",
        ]
        for entry in files:
            filename = html.escape(entry["filename"], quote=True)
            url = html.escape(entry["url"], quote=True)
            parts.append(
                f'<li><a class="artifact" '
                f'href="{url}">{filename}</a></li>'
            )
        parts.extend(["</ul>", "</body>", "</html>"])
        return "".join(parts)
