Add a standard library package named `packagenamespaces` that implements PEP 752.

Place the implementation at `Lib/packagenamespaces/` with importable modules `packagenamespaces.normalize`, `packagenamespaces.matching`, `packagenamespaces.grants`, `packagenamespaces.uploads`, `packagenamespaces.metadata`, `packagenamespaces.policy`, and `packagenamespaces.cli`.
Run the command line through `python -m packagenamespaces`.

Drive the tool from `main(argv)`, which takes an argument vector and returns a status code.
Persist state in a selectable file addressed by `--store` with JSON output selected by `--json`, ownership supplied by `--owner`, and single-project output selected by `--project`.
Document every command through `--help`.
Support `reserve <namespace> --owner <owner>` for grants, `remove <namespace>` for withdrawal, `register <project> --owner <owner>` and `grandfather <project> --owner <owner>` for projects, `check-upload <project> --owner <owner>` for upload decisions, `list --json` and `dump --project <project>` for inspection, and `show <namespace>` with its `show <namespace> --json` variant.
The stored document looks like `{"grants": {"<namespace>": "<owner>"}, "projects": {"<project>": "<owner>"}, "grandfathered": ["<project>"]}` while list output looks like `[{"name": "<namespace>", "owner": "<owner>"}]`.
Reservation prints `reserved <namespace> for <owner>`, removal prints `removed <namespace>`, registration prints `registered <project> for <owner>`, grandfathering prints `grandfathered <project>`, and a permitted check prints `OK <project>`.
Human-readable lists print `<namespace> <owner>` per grant in sorted order.
Human-readable detail prints `name: <name>`, `owner: <owner>`, `parent: <parent>`, and `children: <children>`, using `parent: none` and `children: none` when no grant relationship applies.
Lookup failure means show unknown exits 1 with a message containing `unknown grant`.
An overlapping reservation means reserve overlap exits 1 with a message containing `overlaps the grant`.
A permitted upload means check-upload allowed exits 0 while a denied upload means check-upload denied exits 3 with 409 Conflict.
Name that failure signal `CONFLICT_EXIT = 3` so scripts observe exit status 3.
A damaged store means corrupt store exits 1 and a missing owner means empty owner exits 1.

Normalize every name through `normalize_name`, validate through `is_valid_namespace`, and measure nesting through `hyphen_depth`.
Runs of `-`, `_`, and `.` fold to one `-` with lowercase output so that `Foo.bar_BAZ becomes foo-bar-baz`.
Names stay valid only with an ASCII letter or digit at both ends.
Empty names, edge separators, spaces, and punctuation stay invalid.
Non-string input makes `normalize_name` raise `TypeError` and makes `is_valid_namespace` return `False`.
Depth counts hyphens after normalization.

Decide project membership with `namespace_matches`, which succeeds on an exact match or starts with the namespace followed by a hyphen.
For example `foo matches foo-bar, not foobar`.
Matching uses both inputs normalized before comparison.

Model ownership with `Grant` records held in a `GrantStore`, where `Grant.name` carries the normalized namespace and `Grant.owner` carries the holder.
Report failures through `GrantError` with `InvalidNamespaceError` for bad names, `OverlapError` for collisions, `DepthLimitError` for excess nesting, and `UnknownGrantError` for missing entries.
Judge collisions with `grants_overlap`, where overlap appends a hyphen to both normalized names and overlap is detected in both directions.
The nesting rule is a longer namespace under an existing grant overlaps while `foo and foobar do not overlap`.
Nesting stays limited since overlap allowed only for the overlapping grant's own owner, meaning same owner may nest grants.
Cap nesting with `DEFAULT_DEPTH_LIMIT = 3` exposed as `GrantStore.depth_limit`, where `depth_limit None means unlimited`.
Mutate the store through `GrantStore.reserve`, `GrantStore.transfer`, and `GrantStore.remove`, and inspect it through `GrantStore.get`, `GrantStore.namespaces`, `GrantStore.matching`, `GrantStore.parent`, and `GrantStore.children`.
Lookups report `get returns None when ungranted` and `parent returns None without a grant`.
Reservation stores the normalized form, rejects invalid names and empty owners, enforces the depth cap, and refuses exact duplicates held by another owner.
Transfer and removal of unknown namespaces raise `UnknownGrantError`, listings return sorted names and grants, and parent and child links track only direct granted relationships.

Gate uploads with `authorize_upload`, which returns `True` when allowed and raises `UploadConflictError` for a stranger under a reserved prefix.
Conflicts carry `CONFLICT_STATUS = 409` with details on `UploadConflictError.status_code`, `UploadConflictError.project`, `UploadConflictError.namespace`, and `UploadConflictError.owner`, rendering as 409 Conflict.
An owner under its own grant, an unreserved project, and a grandfathered project touched by a stranger all pass.
Track legacy exceptions in a `GrandfatheredRegistry` managed through `GrandfatheredRegistry.add`, `GrandfatheredRegistry.discard`, `GrandfatheredRegistry.covers`, and `GrandfatheredRegistry.projects`.
Upload checks apply normalization runs before the upload check.

Enforce install decisions with `SecurityPolicy`, configured through `SecurityPolicy.namespaces` and `SecurityPolicy.owner`.
Check one project with `SecurityPolicy.allows` and bulk requirements with `SecurityPolicy.evaluate`, where bulk checks follow evaluate returns normalized-name to boolean mapping.
Access requires project owner must equal the policy owner and matching policy namespace must hold an active grant for that owner.
Denials cover unknown projects denied, ungranted namespaces denied, and grandfathered foreign projects denied.
Scope follows grants are per-repository since a grant on one index confers nothing on another.
An empty policy owner raises `ValueError` while invalid policy namespaces raise `InvalidNamespaceError`.

Serve repository state through `RepositoryIndex`, reached via `RepositoryIndex.store`, `RepositoryIndex.supports_namespaces`, `RepositoryIndex.grandfathered`, and `RepositoryIndex.api_version`.
Supporting repositories report version 1.5 through `API_VERSION = 1.5` while legacy repositories report version 1.4 through `LEGACY_API_VERSION = 1.4`.
Manage projects with `RepositoryIndex.register_project`, `RepositoryIndex.project_owner`, and `RepositoryIndex.projects`, where `project_owner returns None when unknown`.
Describe one project with `RepositoryIndex.project_detail`, returning `{"name": "<project>", "namespaces": null}` when unclaimed and `{"name": "<project>", "namespaces": [{"name": "<namespace>", "owned": true}]}` with `{"name": "<namespace>", "owned": false}` entries where ownership differs.
Detail output keeps owned flags so `owned is true when the project owner holds the grant` and `owned is false for grandfathered projects`, with `matches sorted by name in project_detail` and `grant removal sets project_detail namespaces to null`.
List namespaces with `RepositoryIndex.list_namespaces` over routes `/namespaces` and `/namespace/<namespace>`, returning `{"name": "<namespace>"}` entries and `{"api_version": "1.5", "namespaces": [{"name": "<namespace>"}]}` envelopes.
Expand one entry with `RepositoryIndex.namespace_detail`, returning `{"name": "<namespace>", "parent": "<parent>", "children": ["<child>"], "owner": "<owner>"}` and using `"parent": null` without a granted parent.
Compatibility keeps `legacy repositories omit the namespaces key` with legacy list and detail raising `NotSupportedError`.
Render files with `RepositoryIndex.simple_html` from `{"filename": "<file>", "url": "<url>"}` entries, where HTML Simple API is unchanged, `simple_html output contains no namespace metadata`, and `simple_html escapes special characters`.
Namespace detail normalizes its input, raises `UnknownGrantError` when ungranted, and lists direct children only.

Ship fixture tooling at `Tools/packagenamespaces/gen_fixtures.sh` that takes an output directory and writes `grants.json`, `projects.json`, `grandfathered.json`, and `second-index.json`.
Ship verification at `Tools/packagenamespaces/verify_offline.sh` that takes a fixture directory, exits 0 on success, and prints `verify: all checks passed`.
Scripts keep no network use in either script.

Document the feature in `Doc/library/packagenamespaces.rst`, list that page from `Doc/library/distribution.rst`, note the release in `Doc/whatsnew/3.16.rst`, and add a news fragment under `Misc/NEWS.d/next/Library/`.
The library page mentions PEP 752 alongside `SecurityPolicy` and `RepositoryIndex` while the news and release notes name `packagenamespaces` and PEP 752.
