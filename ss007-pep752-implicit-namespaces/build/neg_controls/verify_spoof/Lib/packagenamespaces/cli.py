"""Grant-management command line for package namespaces (PEP 752).

State lives in a JSON store file (see ``--store``)::

    {"grants": {"acme": "acme-corp"},
     "projects": {"acme-widget": "acme-corp"},
     "grandfathered": ["acme-legacy"]}
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from .grants import GrantError, GrantStore, UnknownGrantError
from .metadata import RepositoryIndex
from .normalize import normalize_name
from .uploads import CONFLICT_STATUS, UploadConflictError, authorize_upload

__all__ = ["main", "build_parser"]

#: Exit status when check-upload refuses an upload (a 409 Conflict).
CONFLICT_EXIT = 3

DEFAULT_STORE = os.path.expanduser("~/.packagenamespaces.json")


def build_parser() -> argparse.ArgumentParser:
    """Build the ``packagenamespaces`` argument parser."""
    parser = argparse.ArgumentParser(
        prog="packagenamespaces",
        description="Manage PEP 752 package-namespace grants.",
    )
    parser.add_argument(
        "--store",
        default=DEFAULT_STORE,
        help="JSON file holding grants, projects and exemptions "
        f"(default: {DEFAULT_STORE})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    reserve = sub.add_parser("reserve", help="Reserve a namespace for an owner.")
    reserve.add_argument("namespace", help="Namespace to reserve.")
    reserve.add_argument("--owner", required=True, help="Grant owner.")

    sub.add_parser("list", help="List every active grant.").add_argument(
        "--json", action="store_true", help="Emit JSON instead of text."
    )

    show = sub.add_parser("show", help="Show one grant in detail.")
    show.add_argument("namespace", help="Namespace to show.")
    show.add_argument("--json", action="store_true", help="Emit JSON.")

    remove = sub.add_parser("remove", help="Remove a grant.")
    remove.add_argument("namespace", help="Namespace to release.")

    register = sub.add_parser(
        "register", help="Record a project's owner."
    )
    register.add_argument("project", help="Project name.")
    register.add_argument("--owner", required=True, help="Project owner.")

    grandfather = sub.add_parser(
        "grandfather",
        help="Exempt a pre-existing project from later reservations.",
    )
    grandfather.add_argument("project", help="Project name.")
    grandfather.add_argument("--owner", required=True, help="Project owner.")

    check = sub.add_parser(
        "check-upload", help="Check whether an upload would be allowed."
    )
    check.add_argument("project", help="Project name.")
    check.add_argument("--owner", required=True, help="Uploading owner.")

    dump = sub.add_parser("dump", help="Dump repository metadata as JSON.")
    dump.add_argument(
        "--project",
        default=None,
        help="Dump one project-detail mapping instead of the index.",
    )
    return parser


def _load_index(path: str) -> RepositoryIndex:
    index = RepositoryIndex(store=GrantStore())
    try:
        with open(path, encoding="utf-8") as handle:
            state = json.load(handle)
    except FileNotFoundError:
        return index
    except (OSError, ValueError) as exc:
        raise GrantError(f"cannot read store {path!r}: {exc}") from exc
    if not isinstance(state, dict):
        raise GrantError(f"store {path!r} does not hold a JSON object")
    grants = state.get("grants", {})
    if not isinstance(grants, dict):
        raise GrantError(f"store {path!r} has a non-object 'grants' key")
    try:
        for namespace, owner in grants.items():
            index.store.reserve(namespace, owner)
    except GrantError:
        raise
    except (ValueError, TypeError) as exc:
        raise GrantError(
            f"store {path!r} holds an invalid grant entry: {exc}"
        ) from exc
    projects = state.get("projects", {})
    if not isinstance(projects, dict):
        raise GrantError(f"store {path!r} has a non-object 'projects' key")
    try:
        for project, owner in projects.items():
            index.register_project(project, owner)
    except GrantError:
        raise
    except (ValueError, TypeError) as exc:
        raise GrantError(
            f"store {path!r} holds an invalid project entry: {exc}"
        ) from exc
    grandfathered = state.get("grandfathered", [])
    if not isinstance(grandfathered, list):
        raise GrantError(
            f"store {path!r} has a non-array 'grandfathered' key"
        )
    try:
        for project in grandfathered:
            index.grandfathered.add(project)
    except GrantError:
        raise
    except (ValueError, TypeError) as exc:
        raise GrantError(
            f"store {path!r} holds an invalid grandfathered entry: {exc}"
        ) from exc
    return index


def _save_index(path: str, index: RepositoryIndex) -> None:
    state = {
        "grants": {
            name: index.store.get(name).owner
            for name in index.store.namespaces()
        },
        "projects": {
            project: index.project_owner(project)
            for project in index.projects()
        },
        "grandfathered": index.grandfathered.projects(),
    }
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _cmd_reserve(index: RepositoryIndex, args: argparse.Namespace) -> int:
    grant = index.store.reserve(args.namespace, args.owner)
    print(f"reserved {grant.name} for {grant.owner}")
    return 0


def _cmd_list(index: RepositoryIndex, args: argparse.Namespace) -> int:
    if args.json:
        print(
            json.dumps(
                [
                    {"name": name, "owner": index.store.get(name).owner}
                    for name in index.store.namespaces()
                ]
            )
        )
    else:
        for name in index.store.namespaces():
            print(f"{name} {index.store.get(name).owner}")
    return 0


def _cmd_show(index: RepositoryIndex, args: argparse.Namespace) -> int:
    detail = index.namespace_detail(args.namespace)
    if args.json:
        print(json.dumps(detail, sort_keys=True))
    else:
        print(f"name: {detail['name']}")
        print(f"owner: {detail['owner']}")
        parent = detail["parent"]
        print(f"parent: {parent if parent is not None else 'none'}")
        children = detail["children"]
        print(f"children: {','.join(children) if children else 'none'}")
    return 0


def _cmd_remove(index: RepositoryIndex, args: argparse.Namespace) -> int:
    grant = index.store.remove(args.namespace)
    print(f"removed {grant.name}")
    return 0


def _cmd_register(index: RepositoryIndex, args: argparse.Namespace) -> int:
    index.register_project(args.project, args.owner)
    print(f"registered {normalize_name(args.project)} for {args.owner}")
    return 0


def _cmd_grandfather(index: RepositoryIndex, args: argparse.Namespace) -> int:
    index.register_project(args.project, args.owner)
    normalized = normalize_name(args.project)
    index.grandfathered.add(normalized)
    print(f"grandfathered {normalized}")
    return 0


def _cmd_check_upload(index: RepositoryIndex, args: argparse.Namespace) -> int:
    try:
        authorize_upload(
            args.project,
            args.owner,
            index.store,
            grandfathered=index.grandfathered,
        )
    except UploadConflictError as exc:
        print(
            f"{CONFLICT_STATUS} Conflict: project {exc.project!r} matches "
            f"reserved namespace {exc.namespace!r}",
            file=sys.stderr,
        )
        return CONFLICT_EXIT
    print(f"OK {normalize_name(args.project)}")
    return 0


def _cmd_dump(index: RepositoryIndex, args: argparse.Namespace) -> int:
    if args.project is not None:
        print(json.dumps(index.project_detail(args.project), sort_keys=True))
    else:
        print(
            json.dumps(
                {
                    "api_version": index.api_version,
                    "namespaces": index.list_namespaces(),
                },
                sort_keys=True,
            )
        )
    return 0


_COMMANDS = {
    "reserve": (_cmd_reserve, True),
    "list": (_cmd_list, False),
    "show": (_cmd_show, False),
    "remove": (_cmd_remove, True),
    "register": (_cmd_register, True),
    "grandfather": (_cmd_grandfather, True),
    "check-upload": (_cmd_check_upload, False),
    "dump": (_cmd_dump, False),
}


def main(argv: list[str] | None = None) -> int:
    """Run the CLI; return the process exit status."""
    args = build_parser().parse_args(argv)
    try:
        index = _load_index(args.store)
    except GrantError as exc:
        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
        return 1
    command, persists = _COMMANDS[args.command]
    try:
        status = command(index, args)
    except UnknownGrantError as exc:
        print(f"packagenamespaces: error: unknown namespace: {exc}", file=sys.stderr)
        return 1
    except GrantError as exc:
        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, UploadConflictError) as exc:
        print(f"packagenamespaces: error: {exc}", file=sys.stderr)
        return 1
    if status == 0 and persists:
        try:
            _save_index(args.store, index)
        except OSError as exc:
            print(
                f"packagenamespaces: error: cannot write {args.store!r}: {exc}",
                file=sys.stderr,
            )
            return 1
    return status
