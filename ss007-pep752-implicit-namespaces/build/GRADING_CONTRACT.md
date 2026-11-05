# GRADING_CONTRACT — ss007-pep752-implicit-namespaces

The graded suite is six conformance files installed at `Lib/test/` by
`test_patch` and run under CPython regrtest (`./python -m test -v ...`)
in the task image. Every id below is the exact `fail_to_pass` string the
parser emits (`test.<module>.<Class>.<method>`); the author must use
these class and method names verbatim.

## Shared rules for every target (read first)

- Imports use only the standard library (`unittest`, `os`, `sys`,
  `json`, `subprocess`, `tempfile`, `contextlib`, `io`, `glob`, `re`,
  `html`, `html.parser`, `argparse`) plus `packagenamespaces`. No
  `test.support`, no third-party packages, no network.
- Guarded import (MANDATORY in every file that touches the package): at
  base the package does not exist, so an unguarded import breaks
  collection and every id goes missing instead of failing. Each such
  file starts with
  `try: from packagenamespaces... import ... except Exception as exc:`
  recording `_IMPORT_ERROR`, and every test that touches the
  implementation calls `self.require_impl()` first, which fails with the
  recorded error. Tests that only use `subprocess` or the filesystem
  need no guard; they fail naturally at base.
- Test methods take no docstrings: regrtest verbose prints a docstring
  instead of the dotted id, and an id-less line can never grade.
- Deterministic only: no randomness, no wall-clock, no absolute paths
  in ids. Temp state goes under `tempfile.TemporaryDirectory`.
- The repo root is derived from `__file__` (three levels up from
  `Lib/test/`); never hardcode `/app`.

## test_pep752_naming — NamingTests (packagenamespaces.normalize)

File `Lib/test/test_pep752_naming.py`, class `NamingTests`, guarded
imports of `normalize_name`, `is_valid_namespace`, `hyphen_depth`.

- `test.test_pep752_naming.NamingTests.test_normalize_lowercases_and_folds_separators`:
  `normalize_name("Foo")=="foo"`, `("foo.bar")=="foo-bar"`,
  `("foo_bar")=="foo-bar"`, `("Foo.Bar_BAZ")=="foo-bar-baz"`.
- `test.test_pep752_naming.NamingTests.test_normalize_collapses_separator_runs`:
  `"foo---bar"`, `"foo._-bar"`, `"foo...bar"`, `"foo___bar"` all become
  `"foo-bar"`.
- `test.test_pep752_naming.NamingTests.test_normalize_leaves_clean_names_alone`:
  `"foo"`, `"foo-bar"`, `"acme-widgets-2"` unchanged.
- `test.test_pep752_naming.NamingTests.test_normalize_rejects_non_string`:
  `None`, `123`, `b"foo"`, `["foo"]` each raise `TypeError`.
- `test.test_pep752_naming.NamingTests.test_valid_names_accepted`:
  `"foo"`, `"a"`, `"A1"`, `"foo-bar"`, `"acme2"`, `"X"*64` are valid.
- `test.test_pep752_naming.NamingTests.test_valid_names_with_separators`:
  `"foo.bar"`, `"foo_bar"`, `"foo-bar"`, `"a1.b2_c3-d4"` are valid.
- `test.test_pep752_naming.NamingTests.test_invalid_names_rejected`:
  `""`, `"-foo"`, `"foo-"`, `".foo"`, `"foo."`, `"_foo"`, `"foo_"`,
  `"-"`, `"."`, `"foo!"`, `"foo bar"`, `"foo/bar"`, `"foo@bar"`,
  `"foo\n"`, `"foo\nbar"`, `"\tfoo"` invalid (a trailing or embedded
  newline or tab never validates, even though the ends look alphanumeric).
- `test.test_pep752_naming.NamingTests.test_invalid_names_reject_non_string`:
  `None`, `123`, `b"foo"`, `["foo"]` are invalid (False, no raise).
- `test.test_pep752_naming.NamingTests.test_hyphen_depth_counts`:
  depths of `"foo"`/`"foo-bar"`/`"foo-bar-baz"`/`"Foo.bar_BAZ"` are
  0/1/2/2.

## test_pep752_semantics — MatchingTests, GrantStoreTests

File `Lib/test/test_pep752_semantics.py`, guarded imports of
`namespace_matches`, `GrantStore`, `DEFAULT_DEPTH_LIMIT`,
`DepthLimitError`, `InvalidNamespaceError`, `OverlapError`,
`UnknownGrantError`, `grants_overlap`.

MatchingTests (`namespace_matches`):

- `test.test_pep752_semantics.MatchingTests.test_exact_match`: true for
  `("foo","foo")` and `("acme-widgets","acme-widgets")`.
- `test.test_pep752_semantics.MatchingTests.test_prefix_hyphen_match`:
  true for `("foo","foo-bar")` and `("acme","acme-widgets-sprocket")`.
- `test.test_pep752_semantics.MatchingTests.test_missing_hyphen_does_not_match`:
  false for `("foo","foobar")` and `("acme","acmewidget")`.
- `test.test_pep752_semantics.MatchingTests.test_match_normalizes_inputs`:
  true for `("Foo","foo-bar")`, `("foo.bar","foo-bar-baz")`,
  `("foo_bar","FOO-BAR")`.
- `test.test_pep752_semantics.MatchingTests.test_unrelated_does_not_match`:
  false for `("foo","bar")`, `("foo","bar-foo")`, `("foo-bar","foo")`.

GrantStoreTests (fresh `GrantStore()` per test unless noted):

- `test.test_pep752_semantics.GrantStoreTests.test_reserve_and_get`:
  `reserve("acme","acme-corp")` returns a grant with that name/owner;
  `get("acme")` equals it; `"acme" in store`; `len(store)==1`;
  `get("other")` is None. Membership normalizes its query: `"Acme"`
  and `"ACME"` are also `in` the store (a raw unnormalized lookup
  fails these), while `"other"` is not.
- `test.test_pep752_semantics.GrantStoreTests.test_reserve_normalizes`:
  `reserve("Acme.Widgets","acme-corp").name=="acme-widgets"`, and the
  grant answers every spelling of its name: `"acme-widgets"`,
  `"Acme.Widgets"`, `"ACME_WIDGETS"` and `"acme.widgets"` are all
  `in` the store.
- `test.test_pep752_semantics.GrantStoreTests.test_reserve_rejects_invalid`:
  `"", "-foo", "foo-", "foo!", "foo bar", "foo\n"` raise
  `InvalidNamespaceError`.
- `test.test_pep752_semantics.GrantStoreTests.test_reserve_rejects_empty_owner`:
  `"", None, 123` as owner raise `ValueError`.
- `test.test_pep752_semantics.GrantStoreTests.test_depth_limit_enforced`:
  with `GrantStore(depth_limit=1)`, `"foo-bar"` reserves but
  `"foo-bar-baz"` raises `DepthLimitError`.
- `test.test_pep752_semantics.GrantStoreTests.test_default_depth_limit_is_three`:
  `DEFAULT_DEPTH_LIMIT==3`, default store limit is 3, `"a-b-c-d"`
  reserves, `"a-b-c-d-e"` raises, and `GrantStore(depth_limit=None)`
  reserves `"a-b-c-d-e-f"`.
- `test.test_pep752_semantics.GrantStoreTests.test_overlap_shorter_over_longer_rejected`:
  grant `"foo-bar"` to owner-a, then `reserve("foo","owner-b")` raises
  `OverlapError`.
- `test.test_pep752_semantics.GrantStoreTests.test_overlap_longer_under_shorter_rejected`:
  grant `"foo"` to owner-a, then `reserve("foo-bar","owner-b")` raises
  `OverlapError` (bidirectional: this is the direction the spec text
  reads as silent).
- `test.test_pep752_semantics.GrantStoreTests.test_overlap_exact_duplicate_rejected`:
  grant `"foo"` to owner-a; `reserve("foo","owner-b")` raises; re-
  reserving to owner-a is idempotent (`len==1`).
- `test.test_pep752_semantics.GrantStoreTests.test_overlap_same_owner_nesting_allowed`:
  owner-a nests `"foo"`, `"foo-bar"`, `"foo-bar-baz"` (3 grants), and a
  second store nests bottom-up from `"foo-bar-baz"` to `"foo"`.
- `test.test_pep752_semantics.GrantStoreTests.test_overlap_hyphen_boundary_not_overlapping`:
  `"foo"` (owner-a) and `"foobar"` (owner-b) coexist.
- `test.test_pep752_semantics.GrantStoreTests.test_grants_overlap_both_directions`:
  true both orders for `("foo","foo-bar")`, true for `("foo","foo")`
  and `("Foo","foo-bar")`; false both orders for `("foo","foobar")`
  and for `("foo","bar")`.
- `test.test_pep752_semantics.GrantStoreTests.test_transfer`: grant to
  owner-a, `transfer` to owner-b, `get` shows owner-b.
- `test.test_pep752_semantics.GrantStoreTests.test_transfer_unknown_raises`:
  `UnknownGrantError`.
- `test.test_pep752_semantics.GrantStoreTests.test_transfer_conflicting_raises`:
  grant `"foo"` then `"foo-bar"` to owner-a; `transfer("foo-bar",
  "owner-b")` raises `OverlapError`, and both grants still show owner-a
  afterwards. A second store grants `"foo-bar"` then `"foo"` to owner-a;
  `transfer("foo", "owner-b")` raises `OverlapError` too. Transferring
  either grant back to owner-a succeeds.
- `test.test_pep752_semantics.GrantStoreTests.test_remove`: grant then
  `remove` returns it; store empty; `get` is None.
- `test.test_pep752_semantics.GrantStoreTests.test_remove_unknown_raises`:
  `UnknownGrantError`.
- `test.test_pep752_semantics.GrantStoreTests.test_namespaces_sorted`:
  reserves out of order read back `["acme","mid-way","zeta"]`.
- `test.test_pep752_semantics.GrantStoreTests.test_parent_with_grant`:
  with `"foo"`, `"foo-bar"`, `"foo-bar-baz"` granted, parents are
  `"foo"` and `"foo-bar"` respectively.
- `test.test_pep752_semantics.GrantStoreTests.test_parent_without_grant_is_none`:
  only `"foo-bar-baz"` granted: its parent is None, as is `"foo"`'s.
- `test.test_pep752_semantics.GrantStoreTests.test_children_direct_only`:
  with `"foo"`, `"foo-bar"`, `"foo-bar-baz"`, `"foo-qux"` granted,
  `children("foo")==["foo-bar","foo-qux"]`,
  `children("foo-bar")==["foo-bar-baz"]`, `children("foo-bar-baz")==[]`.
- `test.test_pep752_semantics.GrantStoreTests.test_parent_sparse_chain_is_none`:
  grant only `"foo"` and `"foo-bar-baz"` (no `"foo-bar"`):
  `parent("foo-bar-baz")` is None and `parent("foo")` is None (a
  missing middle grant breaks the link; parents are direct only).
- `test.test_pep752_semantics.GrantStoreTests.test_children_sparse_chain_skips_gap`:
  same two grants: `children("foo")==[]` and
  `children("foo-bar-baz")==[]` (children are direct only).
- `test.test_pep752_semantics.GrantStoreTests.test_matching_returns_sorted_grants`:
  grants `"acme-widgets"`, `"acme"`, `"other"`;
  `matching("acme-widgets-sprocket")` names are `["acme","acme-widgets"]`;
  `matching("unrelated")` is empty.

## test_pep752_uploads — UploadTests (packagenamespaces.uploads)

File `Lib/test/test_pep752_uploads.py`, class `UploadTests`, guarded
imports of `GrantStore`, `CONFLICT_STATUS`, `GrandfatheredRegistry`,
`UploadConflictError`, `authorize_upload`. `GrantStore` and
`GrandfatheredRegistry` import from the package ROOT
(`from packagenamespaces import GrantStore, GrandfatheredRegistry` --
the instruction requires the root to re-export every public symbol,
so a tree that drops the root `GrandfatheredRegistry` import fails
the guarded import and every test below with it);
`CONFLICT_STATUS`, `UploadConflictError` and `authorize_upload`
import from `packagenamespaces.uploads` as before. Class and method
names are unchanged (no id changes). Helper builds a store with
`"acme"` granted to `"acme-corp"`.

- `test.test_pep752_uploads.UploadTests.test_unreserved_upload_allowed`:
  `authorize_upload("requests","anyone",store)` is True.
- `test.test_pep752_uploads.UploadTests.test_owner_upload_allowed`:
  `"acme-new"` and `"acme"` by `"acme-corp"` are True.
- `test.test_pep752_uploads.UploadTests.test_stranger_upload_conflicts`:
  `authorize_upload("acme-evil","mallory",store)` raises
  `UploadConflictError` with `status_code==409`,
  `project=="acme-evil"`, `namespace=="acme"`, `owner=="mallory"`
  (`owner` is the attempted uploader from the call, not the grant
  holder `acme-corp`).
- `test.test_pep752_uploads.UploadTests.test_conflict_status_constant`:
  `CONFLICT_STATUS==409` and `UploadConflictError.status_code==409`.
- `test.test_pep752_uploads.UploadTests.test_exact_namespace_project_gated`:
  `authorize_upload("acme","mallory",store)` raises.
- `test.test_pep752_uploads.UploadTests.test_hyphen_boundary_not_gated`:
  `authorize_upload("acmewidget","mallory",store)` is True.
- `test.test_pep752_uploads.UploadTests.test_grandfathered_stranger_allowed`:
  registry with `"acme-legacy"` added;
  `authorize_upload("acme-legacy","mallory",store,grandfathered=...)`
  is True.
- `test.test_pep752_uploads.UploadTests.test_grandfathered_registry_tracks_projects`:
  `add("Acme.Legacy")`; `covers("acme-legacy")`; `"acme-legacy" in
  registry`; `projects()==["acme-legacy"]`; `len==1`;
  `discard` clears coverage. Both membership probes normalize their
  query: `covers("Acme.Legacy")` and `covers("ACME_LEGACY")` hold,
  as do `"Acme.Legacy" in registry` and `"acme.legacy" in
  registry` (a raw unnormalized lookup fails these); after
  `discard("acme-legacy")`, `covers("ACME-LEGACY")` is false too.
- `test.test_pep752_uploads.UploadTests.test_nongrandfathered_stranger_denied`:
  registry holding only `"acme-legacy"`;
  `authorize_upload("acme-other","mallory",store,...)` raises.
- `test.test_pep752_uploads.UploadTests.test_normalization_applied_before_check`:
  `"Acme.Evil"` by mallory raises, by `"acme-corp"` is True.
- `test.test_pep752_uploads.UploadTests.test_authorize_upload_rejects_empty_owner`:
  `"", None, 123` as owner each raise `ValueError`, both for a
  reserved-prefix project (`"acme-new"`) and for an unreserved one
  (`"requests"`): owner validation runs before any grant is consulted.

## test_pep752_metadata — MetadataTests (packagenamespaces.metadata)

File `Lib/test/test_pep752_metadata.py`, class `MetadataTests`,
guarded imports of `GrantStore`, `UnknownGrantError`, `API_VERSION`,
`LEGACY_API_VERSION`, `NotSupportedError`, `RepositoryIndex`. Helper
builds an index with `"acme"` and `"acme-widgets"` granted to
`"acme-corp"`.

- `test.test_pep752_metadata.MetadataTests.test_api_version_is_1_5`:
  `API_VERSION=="1.5"` and fresh index version is `"1.5"`.
- `test.test_pep752_metadata.MetadataTests.test_register_project_validates_owner`:
  `"", None, 123` raise `ValueError`; registering `"acme-new"` to
  `"acme-corp"` reads back; unknown project owner is None.
- `test.test_pep752_metadata.MetadataTests.test_register_project_records_without_authorization`:
  with `"acme"` granted to `"acme-corp"`, registering `"acme-squat"`
  to `"mallory"` succeeds (recording is not an upload gate) and
  `project_owner("acme-squat")` reads `"mallory"`.
- `test.test_pep752_metadata.MetadataTests.test_legacy_repository_is_1_4_and_silent`:
  `LEGACY_API_VERSION=="1.4"`; legacy index version `"1.4"`;
  `project_detail("anything-at-all")=={"name":"anything-at-all"}` with
  no `namespaces` key.
- `test.test_pep752_metadata.MetadataTests.test_legacy_endpoints_raise_not_supported`:
  legacy `list_namespaces()` and `namespace_detail("acme")` raise
  `NotSupportedError`.
- `test.test_pep752_metadata.MetadataTests.test_project_detail_unmatched_is_null`:
  `project_detail("requests")` has name `"requests"` and
  `namespaces` None.
- `test.test_pep752_metadata.MetadataTests.test_project_detail_matched_owned`:
  register `"acme-widgets-sprocket"` to `"acme-corp"`; namespaces are
  `[{"name":"acme","owned":True},{"name":"acme-widgets","owned":True}]`.
- `test.test_pep752_metadata.MetadataTests.test_project_detail_grandfathered_unowned`:
  register `"acme-legacy"` to `"mallory"`, add to
  `index.grandfathered`; namespaces are
  `[{"name":"acme","owned":False}]`.
- `test.test_pep752_metadata.MetadataTests.test_project_detail_multiple_matches_sorted`:
  grants `"zeta"`/`"acme"` to `"a"`; `"acme-thing"` owned by `"a"`
  reports `[{"name":"acme","owned":True}]`; `"zeta-thing"` owned by
  `"other"` reports `[{"name":"zeta","owned":False}]`.
- `test.test_pep752_metadata.MetadataTests.test_grant_removal_nulls_detail`:
  register then remove both grants; namespaces become None.
- `test.test_pep752_metadata.MetadataTests.test_namespace_list_shape`:
  `list_namespaces()==[{"name":"acme"},{"name":"acme-widgets"}]`.
- `test.test_pep752_metadata.MetadataTests.test_namespace_list_empty`:
  fresh index lists `[]`.
- `test.test_pep752_metadata.MetadataTests.test_namespace_detail_shape`:
  detail of `"acme"` is `{"name":"acme","parent":None,
  "children":["acme-widgets"],"owner":"acme-corp"}`; of
  `"acme-widgets"` is `{"name":"acme-widgets","parent":"acme",
  "children":[],"owner":"acme-corp"}`.
- `test.test_pep752_metadata.MetadataTests.test_namespace_detail_normalizes_input`:
  `namespace_detail("Acme.Widgets")["name"]=="acme-widgets"`.
- `test.test_pep752_metadata.MetadataTests.test_namespace_detail_unknown_raises`:
  `UnknownGrantError` for `"no-such-namespace"`.
- `test.test_pep752_metadata.MetadataTests.test_namespace_detail_parent_null_without_grant`:
  only `"deep-down-namespace"` granted: its parent is None.
- `test.test_pep752_metadata.MetadataTests.test_namespace_detail_children_direct_only`:
  grants `"foo"`, `"foo-bar"`, `"foo-bar-baz"`;
  `namespace_detail("foo")["children"]==["foo-bar"]`.
- `test.test_pep752_metadata.MetadataTests.test_html_carries_no_namespace_keys`:
  page for `"acme-thing"` contains the filename but neither
  `"namespace"` nor `"namespaces"`.
- `test.test_pep752_metadata.MetadataTests.test_html_semantically_stable`:
  `simple_html("demo", [{demo-1.0.tar.gz + demo-1.0-py3-none-any.whl
  at https://example.com/...}])` renders a full HTML document, compared
  structurally so that tag case, whitespace, indentation, attribute
  order, attribute quote style, spacing around `=`, extra attributes,
  line-break markup and the title/heading wording are all free. The page
  must hold `<!doctype html>` (any case), an `<html>`, `<head>` and
  `<body>` open tag each (matched case-insensitively), and a `<title>`
  and an `<h1>` that EACH CONTAIN the project name `demo` (extract each
  element's text with a case-insensitive
  `<title\b[^>]*>([\s\S]*?)</title\s*>` and the same shape for `h1`,
  then assert `demo` is a substring; the reference `Links for demo`
  passes, and so does any other wording that names the project). In
  file order, one anchor per file whose `href` equals the file url and
  whose text equals the filename, compared by PARSING -- never by a
  lowercase-only anchor regex, which rejects equivalent uppercase
  renderers. Collect anchors with `html.parser.HTMLParser`
  (`convert_charrefs=True`): subclass it, on each start tag whose name
  lowercases to `a` record the `href` attribute (attribute names
  lowercased) and gather character data until the matching end tag,
  and assert the collected `(href, text)` pairs in document order
  equal `[(url, filename)]` for the two files (exactly two anchors --
  the ordered comparison already rejects a missing or extra one). It
  must hold neither `"namespace"` nor `"namespaces"`, and two renders
  of equal inputs must be byte-equal (deterministic).
- `test.test_pep752_metadata.MetadataTests.test_html_escapes_special_characters`:
  filename `a<b>&"c.tar.gz` with url
  `https://example.com/a?first=1&second=2` renders escaped WITHOUT
  pinning the tag case, the attribute spelling, or the entity spelling:
  collect anchors with the same HTMLParser subclass, assert exactly one
  anchor whose parsed `href` and text equal the original url and
  filename (the parser resolves the entities, whatever their spelling);
  the raw filename never appears literally and no literal `<b>`
  survives. (The old exact-entity pin rejected equivalent
  numeric-entity renderers, and the old lowercase anchor regex rejected
  equivalent uppercase renderers.)

## test_pep752_policy — PolicyTests (packagenamespaces.policy)

File `Lib/test/test_pep752_policy.py`, class `PolicyTests`, guarded
imports of `GrantStore`, `InvalidNamespaceError`, `RepositoryIndex`,
`SecurityPolicy`. Helper builds an index with `"acme"` granted to
`"acme-corp"` and projects `"acme-widget"`/`"acme-corp"`,
`"acme-legacy"`/`"mallory"`, `"requests"`/`"psf"`.

- `test.test_pep752_policy.PolicyTests.test_allows_granted_owner_dependency`:
  policy `(["acme"],"acme-corp")` allows `"acme-widget"`.
- `test.test_pep752_policy.PolicyTests.test_allows_with_multiple_namespaces`:
  policy `(["other","acme"],"acme-corp")` allows `"acme-widget"`;
  policy `(["other","ungranted"],"acme-corp")` denies it.
- `test.test_pep752_policy.PolicyTests.test_denies_ungranted_namespace`:
  policy `(["other"],"acme-corp")` denies `"other-thing"`; and after
  registering `"acme-widget-part"` to `"acme-corp"`, policy
  `(["acme-widget"],"acme-corp")` denies it (no grant for that
  namespace).
- `test.test_pep752_policy.PolicyTests.test_denies_wrong_owner`:
  policy `(["acme"],"someone-else")` denies `"acme-widget"`.
- `test.test_pep752_policy.PolicyTests.test_denies_grandfathered_foreign_project`:
  add `"acme-legacy"` to `index.grandfathered`; policy
  `(["acme"],"acme-corp")` still denies it (owned by mallory).
- `test.test_pep752_policy.PolicyTests.test_denies_unknown_project`:
  policy denies `"acme-unregistered"` (no recorded owner).
- `test.test_pep752_policy.PolicyTests.test_evaluate_reports_each_requirement`:
  `evaluate(["acme-widget","acme-legacy","requests"],index)` is
  `{"acme-widget":True,"acme-legacy":False,"requests":False}`.
- `test.test_pep752_policy.PolicyTests.test_evaluate_empty_requirements`:
  `evaluate([],index)=={}`.
- `test.test_pep752_policy.PolicyTests.test_evaluate_normalizes_names`:
  `evaluate(["Acme.Widget"],index)=={"acme-widget":True}`.
- `test.test_pep752_policy.PolicyTests.test_grant_not_shared_between_repositories`:
  a mirror index with no grants but the same registered project is
  denied while the granted index allows.
- `test.test_pep752_policy.PolicyTests.test_policy_validates_namespaces`:
  `["-bad"]` raises `InvalidNamespaceError`; `["Acme.Widgets"]`
  normalizes to `("acme-widgets",)` with owner `"acme-corp"`.
- `test.test_pep752_policy.PolicyTests.test_policy_validates_owner`:
  `"", None, 123` raise `ValueError`.

## test_pep752_tooling — CliTests, HarnessTests, DocsTests

File `Lib/test/test_pep752_tooling.py`. `CliTests` uses the guarded
import of `main` and `CONFLICT_EXIT` from `packagenamespaces.cli`,
drives `main(["--store", tmp, ...])` with stdout/stderr captured, and
derives the repo root from `__file__`. Every `main` call below passes
`--store <tmp-store>` first; the argv shown is what follows it, exact
words in exact order (options the CLI requires, like `--owner`, are
always present). `HarnessTests` shells out to
the `Tools/packagenamespaces/` scripts. `DocsTests` reads doc files.

- `test.test_pep752_tooling.CliTests.test_cli_reserve_and_list`:
  `reserve acme --owner acme-corp` prints `reserved acme for
  acme-corp` (exit 0); `list` prints `acme acme-corp`; `list --json`
  parses to `[{"name":"acme","owner":"acme-corp"}]`.
- `test.test_pep752_tooling.CliTests.test_cli_reserve_overlap_fails`:
  after `reserve acme --owner acme-corp`,
  `reserve acme-evil --owner mallory` exits 1 with the full phrase
  `overlaps the grant` (case-insensitive) on stderr.
- `test.test_pep752_tooling.CliTests.test_cli_show`: after
  `reserve acme --owner acme-corp` and
  `reserve acme-widgets --owner acme-corp`, `show acme` prints
  exactly the lines `name: acme` / `owner: acme-corp` /
  `parent: none` / `children: acme-widgets`; `show acme --json`
  parses to the matching mapping.
- `test.test_pep752_tooling.CliTests.test_cli_show_unknown_fails`:
  `show acme` on an empty store exits 1 with the full phrase
  `unknown grant` (case-insensitive) on stderr.
- `test.test_pep752_tooling.CliTests.test_cli_remove`: after
  `reserve acme --owner acme-corp`, `remove acme` prints
  `removed acme` (exit 0); `list` is then empty.
- `test.test_pep752_tooling.CliTests.test_cli_register_and_grandfather`:
  `register acme-new --owner acme-corp` prints
  `registered acme-new for acme-corp` (exit 0);
  `grandfather acme-legacy --owner mallory` prints
  `grandfathered acme-legacy` (exit 0).
- `test.test_pep752_tooling.CliTests.test_cli_check_upload_allowed`:
  after `reserve acme --owner acme-corp`,
  `check-upload acme-new --owner acme-corp` exits 0 printing
  `OK acme-new`.
- `test.test_pep752_tooling.CliTests.test_cli_check_upload_denied`:
  `CONFLICT_EXIT==3`; after `reserve acme --owner acme-corp`,
  `check-upload acme-new --owner mallory` exits 3 with `409` and
  `Conflict` on stderr.
- `test.test_pep752_tooling.CliTests.test_cli_check_upload_grandfathered_allowed`:
  after `reserve acme --owner acme-corp` and
  `grandfather acme-legacy --owner mallory`,
  `check-upload acme-legacy --owner mallory` exits 0 printing
  `OK acme-legacy`.
- `test.test_pep752_tooling.CliTests.test_cli_dump`: after
  `reserve acme --owner acme-corp`, `dump` parses to
  `{"api_version":"1.5","namespaces":[{"name":"acme"}]}` (bare `dump`
  prints the versioned envelope; `list --json` prints the
  name-and-owner entries instead).
- `test.test_pep752_tooling.CliTests.test_cli_dump_project`: after
  `reserve acme --owner acme-corp` and
  `register acme-new --owner acme-corp`,
  `dump --project acme-new` parses to `{"name":"acme-new",
  "namespaces":[{"name":"acme","owned":True}]}`.
- `test.test_pep752_tooling.CliTests.test_cli_corrupt_store_fails`:
  a store holding `{not valid json` makes `list` exit 1 with
  `error` on stderr, and so does every value-level corruption below
  (`main` returns 1 in each case; it never raises):
  `{"grants": {"acme": 123}}`, `{"grants": {"acme": null}}`,
  `{"grants": {"acme": ""}}`, `{"projects": {"acme-new": 123}}`,
  `{"grandfathered": [123]}`, `{"grants": {"bad name!": "acme-corp"}}`.
- `test.test_pep752_tooling.CliTests.test_cli_register_rejects_empty_owner`:
  `register acme-new --owner ""` exits 1 with `error` on stderr.
- `test.test_pep752_tooling.CliTests.test_cli_persists_documented_store_schema`:
  after `reserve acme --owner acme-corp`,
  `register acme-new --owner acme-corp` and
  `grandfather acme-legacy --owner mallory`, the store file parses to
  exactly `{"grants": {"acme": "acme-corp"}, "projects":
  {"acme-new": "acme-corp", "acme-legacy": "mallory"},
  "grandfathered": ["acme-legacy"]}` -- the documented keys only, no
  envelope, no extra keys. (Grandfathering records the project's owner
  as well as exempting it.)
- `test.test_pep752_tooling.CliTests.test_cli_loads_documented_store_schema`:
  write that same documented document by hand; `list` then prints
  `acme acme-corp`, `check-upload acme-new --owner mallory` exits 3,
  and `check-upload acme-legacy --owner mallory` exits 0 printing
  `OK acme-legacy`.
- `test.test_pep752_tooling.CliTests.test_cli_check_upload_rejects_empty_owner`:
  `check-upload unreserved --owner ""` on an empty store exits 1 with
  `error` on stderr, and so does
  `check-upload acme-new --owner ""` after `reserve acme --owner
  acme-corp`: empty owners are rejected even where no grant applies.
- `test.test_pep752_tooling.CliTests.test_cli_module_entrypoint`:
  `sys.executable -m packagenamespaces --help` exits 0 with
  `usage` on stdout (no package import in this test).
- `test.test_pep752_tooling.CliTests.test_cli_package_root_reexports_build_parser`:
  the package root re-exports `build_parser` (guarded import of the
  name from `packagenamespaces` itself, following the file's existing
  guarded-import pattern, plus the `packagenamespaces.cli` module for
  identity): `callable(build_parser)`; it IS the CLI submodule's own
  object (`packagenamespaces.build_parser is
  packagenamespaces.cli.build_parser`); calling it with no arguments
  returns an `argparse.ArgumentParser`; and that parser parses
  `["reserve", "acme", "--owner", "acme-corp"]` without raising
  `SystemExit` (a tree that drops the root import fails here although
  every other test still passes). Parsed destinations are NOT pinned,
  and `__all__` is NOT consulted (neither its presence nor its
  spelling is specified).
- `test.test_pep752_tooling.HarnessTests.test_gen_fixtures_writes_indexes`:
  `bash gen_fixtures.sh <tmp>` exits 0; `grants.json`,
  `projects.json`, `grandfathered.json`, `second-index.json` exist and
  parse as JSON objects with these shapes: `grants.json["grants"]` is a
  list of >=2 mappings each carrying string `name` and `owner` keys;
  `projects.json["projects"]` is a project-to-owner mapping;
  `grandfathered.json["grandfathered"]` is a list;
  `second-index.json` carries a `grants` list and a `projects` mapping.
- `test.test_pep752_tooling.HarnessTests.test_verify_offline_passes`:
  `bash verify_offline.sh <fixtures>` exits 0 printing
  `verify: all checks passed`.
- `test.test_pep752_tooling.HarnessTests.test_verify_offline_rejects_missing_fixtures`:
  fails unless `verify_offline.sh` exists; `bash verify_offline.sh
  <empty-tmpdir>` then exits nonzero and `verify: all checks passed`
  is absent from its stdout.
- `test.test_pep752_tooling.HarnessTests.test_verify_offline_rejects_damaged_fixtures`:
  fails unless both scripts exist; generates fixtures, then corrupts
  them five ways -- `grants.json` replaced by `{not valid json`,
  `projects.json` replaced by `{}`, `second-index.json` replaced
  by `{"grants": "acme", "projects": {"x": "y"}}` (grants no longer
  an array), `second-index.json` replaced by
  `{"grants": [123], "projects": {"x": "y"}}` (a list whose entry
  is no grant mapping), and `second-index.json` replaced by
  `{"grants": [{"name": "acme"}], "projects": {"x": "y"}}` (an
  entry with no owner) -- and each corrupted tree makes
  `verify_offline.sh` exit nonzero with `verify: all checks passed`
  absent from its stdout. A verifier that checks only that
  second-index `grants` is a list fails the last two.
- `test.test_pep752_tooling.HarnessTests.test_scripts_use_no_network`:
  BEHAVIORAL, never textual: the test matches no word in either
  script file. Instead it creates a stub directory holding `curl`,
  `wget`, `ssh`, `scp`, `sftp`, `ftp`, `lftp`, `telnet`, `nc`, `ncat`,
  `socat`, `httpx` commands that log their invocation and exit 1,
  then runs `bash gen_fixtures.sh <tmp>` and
  `bash verify_offline.sh <tmp>` with that directory first on PATH:
  both succeed (`verify: all checks passed` for the verifier) and the
  log shows zero invocations. Then it copies the WHOLE
  `Tools/packagenamespaces/` directory into a mirrored `Tools/`
  layout with `Lib` linked back to the repo (entrypoints plus every
  sibling helper the implementation ships -- the instruction never
  requires the two scripts to be self-contained, so a helper they
  source or import must keep working after the move), appends comment
  lines naming network words to the two copied entrypoints only
  (`# ... curl wget ... urllib http.client httpx`), and runs the
  copies the same way (the mirror layout matters because the scripts
  derive their root from their own path): both still succeed. A
  script that shells out to a network command fails (the stub's
  exit 1 under `set -e`, or the empty-log assertion); a comment
  merely mentioning one passes. Copying only the two `.sh` files
  would reject a legitimate split layout and is NOT what this test
  does.
- `test.test_pep752_tooling.DocsTests.test_library_page_documents_module`:
  `Doc/library/packagenamespaces.rst` exists and contains
  `packagenamespaces`, `namespaces`, `SecurityPolicy`,
  `RepositoryIndex`, and either the literal `PEP 752` or the
  documentation role `:pep:` together with `752`.
- `test.test_pep752_tooling.DocsTests.test_distribution_lists_new_page`:
  `Doc/library/distribution.rst` contains `packagenamespaces`.
- `test.test_pep752_tooling.DocsTests.test_install_registers_package`:
  `Makefile.pre.in` names `packagenamespaces` between the `LIBSUBDIRS`
  and `TESTSUBDIRS` assignments, and
  `Python/stdlib_module_names.h` holds the `"packagenamespaces"` entry.
- `test.test_pep752_tooling.InstallTests.test_installed_tree_contains_package`:
  new class `InstallTests` with `DESTDIR = "/tmp/lambo-destdir"`;
  `setUpClass` derives the repo root from `__file__`, records the
  installed stdlib path from the repo's own `./python -c "import
  sysconfig..."` (subprocess timeout 300, asserts returncode 0), and
  joins it under `DESTDIR`. The class spawns NO `make` itself: the
  runner builds and stages the DESTDIR install before the suite starts
  (rebuilding from inside the suite relinks the running interpreter,
  which segfaults it). This test asserts
  `<DESTDIR>/<stdlib>/packagenamespaces/__init__.py` is a file.
- `test.test_pep752_tooling.InstallTests.test_stdlib_module_names_contains_package`:
  runs the repo's own `./python` (path joined from the derived root,
  never `sys.executable`) with `-c "import sys"` and asserts
  `packagenamespaces` is a member of `sys.stdlib_module_names`.
- `test.test_pep752_tooling.DocsTests.test_whatsnew_announces_module`:
  `Doc/whatsnew/3.16.rst` contains `packagenamespaces` and `752`.
- `test.test_pep752_tooling.DocsTests.test_news_entry_exists`: some
  `Misc/NEWS.d/next/Library/*.rst` contains both
  `packagenamespaces` and `752`.
