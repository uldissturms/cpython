#!/usr/bin/env python3
"""Independent behavioral probe for the PEP 752 task (second reward channel).

Usage: probe.py <repo-root> <output-json>

Writes ``{"passed": bool, "failed": [...], "checks": N}``. ``passed`` is true
only when every check below holds. Any unexpected error fails closed
(``passed`` is false, never missing).

WHY THIS EXISTS

The graded suite's verdicts travel through the JUnit XML report, which is
written inside the same container -- and the same process -- as agent code:
the agent-owned interpreter runs the regrtest process, and the agent's own
package is imported into it. In-process code can therefore rewrite the
report after a genuine failing run (an atexit hook suffices) and a
report-only grader scores reward 1. This probe closes that route: it
re-checks the specified behaviors directly -- including negative cases --
and NEVER reads the JUnit report. The reward requires this probe AND every
required suite id, so a forged report alone can no longer score.

WHY THREE PROCESSES

An earlier single-process probe imported the submitted package in the same
process that wrote its verdict file, so a shutdown hook inside the package
could overwrite the genuine payload afterwards and the reward accepted the
forgery. Splitting off a verdict-writing parent closed that route but not
the next one: the child still imports agent code to run the checks, and
that code can patch the test framework (``unittest.TestCase.run``) or arm
a ``sys.settrace`` hook that swaps the check functions for no-ops, forging
a passing payload the parent would then faithfully write. A parent that
merely writes what the child computed authenticates nothing.

This probe therefore splits in three. The CHECK CHILD runs in a fresh
locked-down interpreter (absolute repo path, ``-I -S``, neutral cwd,
scrubbed environment, script from the verifier-owned ``/tests`` tree),
UNPRIVILEGED (setpriv nobody, so submitted code it imports cannot write
the verifier-owned readers, verdict paths, or logs), runs every check,
and prints its verdict as one marked line on stdout. The ATTEST
GRANDCHILD runs the same locked-down unprivileged way but NEVER imports
agent code: it only hashes the check functions' bytecode, giving the
parent ground truth no submission can influence. The PARENT never
imports agent-controlled code -- it spawns both, demands exactly one
well-formed result line on a zero exit from each, requires the child's
per-check code hashes to equal the grandchild's (a swapped check has
different bytecode, however its filename was faked), and only then
writes the verdict file, after both (and any hook the child armed) are
dead. Anything the child writes to the verdict path is moot: the parent
overwrites it last. Every anomaly -- crash, timeout, missing or doubled
result line, malformed payload, attestation mismatch -- fails closed.

The probe pins specified behavior only (the same contract the graded suite
is authored from), never reference-implementation internals, so any correct
alternate implementation passes it.
"""

import contextlib
import glob
import hashlib
import io
import json
import marshal
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from html.parser import HTMLParser

# The child prints its verdict as one line starting with this marker; the
# parent accepts exactly one such line. Genuine implementation code never
# prints it; extra copies fail closed.
MARKER = "LAMBO_PROBE_PAYLOAD "

_MODE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in (
    "--child", "--attest") else None
_CHILD_MODE = _MODE == "--child"
_ATTEST_MODE = _MODE == "--attest"

if _CHILD_MODE:
    try:
        from packagenamespaces import (
            API_VERSION,
            CONFLICT_EXIT,
            CONFLICT_STATUS,
            DEFAULT_DEPTH_LIMIT,
            LEGACY_API_VERSION,
            GrantStore,
            RepositoryIndex,
            SecurityPolicy,
            UploadConflictError,
            authorize_upload,
            grants_overlap,
            hyphen_depth,
            is_valid_namespace,
            namespace_matches,
            normalize_name,
        )
        from packagenamespaces.cli import main as cli_main
        from packagenamespaces.grants import (
            DepthLimitError,
            InvalidNamespaceError,
            OverlapError,
            UnknownGrantError,
        )
        from packagenamespaces.metadata import NotSupportedError
        from packagenamespaces.uploads import GrandfatheredRegistry
    except Exception as exc:  # Base tree or broken package: fail closed.
        _IMPORT_ERROR = exc
    else:
        _IMPORT_ERROR = None
else:
    # Parent mode: agent-controlled code is never imported here. The check
    # functions below are defined but never called in this process.
    _IMPORT_ERROR = None


if _MODE is not None:
    REPO_ROOT = sys.argv[2] if len(sys.argv) > 2 else "/app"
else:
    REPO_ROOT = sys.argv[1] if len(sys.argv) > 1 else "/app"
REPO_PYTHON = os.path.join(REPO_ROOT, "python")
DESTDIR = "/tmp/lambo-destdir"

_FAILURES = []
_ATTEST_PRE = {}
_ATTEST_POST = {}


def _code_hash(func):
    """Bytecode digest identifying the running check function."""
    return hashlib.sha256(func.__code__.co_code).hexdigest()


def check(name, func):
    """Run one check, recording its name on any failure.

    The check's bytecode is hashed immediately before and after it runs.
    The parent compares both against the attestation grandchild's ground
    truth, so a no-op swapped in around the call -- however briefly --
    fails closed even if the swap is undone before the verdict prints.
    """
    try:
        _ATTEST_PRE[name] = _code_hash(func)
    except Exception as exc:
        _FAILURES.append(f"{name}: cannot attest check code: {exc!r}")
        return
    try:
        func()
    except Exception as exc:
        _FAILURES.append(f"{name}: {exc!r}")
    except BaseException as exc:
        # An exiting check (argparse SystemExit, a deliberate os._exit
        # dodge) fails that check; the rest still run.
        _FAILURES.append(f"{name}: {type(exc).__name__}({exc})")
    finally:
        try:
            _ATTEST_POST[name] = _code_hash(func)
        except Exception as exc:
            _FAILURES.append(f"{name}: cannot re-attest check code: {exc!r}")


def need_impl():
    if _IMPORT_ERROR is not None:
        raise AssertionError(f"cannot import packagenamespaces: {_IMPORT_ERROR!r}")


def expect_raises(exc_types, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exc_types:
        return
    raise AssertionError(f"{func.__name__} did not raise {exc_types}")


# ------------------------------------------------------------- integrity
#
# These run first and need no implementation: they verify the child process
# itself has not been tampered with by the submission it imported. A forged
# suite report (patched ``TestCase.run``) or forged probe payload (check
# functions swapped for no-ops under a trace hook) fails here, in a process
# whose own checks are attested by a grandchild that never imports agent
# code. At base, with nothing imported, they pass.

def integrity_no_trace():
    # No trace hook may be active: swapping checks for no-ops needs one.
    trace = sys.gettrace()
    assert trace is None, f"trace hook active: {trace!r}"
    # ... and the sampler itself must be the real builtin, reached two
    # ways, so a Python-level fake cannot report a clean bill of health.
    assert type(sys.gettrace).__name__ == "builtin_function_or_method"
    assert sys.modules["sys"].gettrace is sys.gettrace


def integrity_checks_intact():
    # Every running check must be this file's own function: a no-op
    # swapped in from submission code carries its own filename.
    here = os.path.realpath(__file__)
    for name, func in CHECKS:
        code = func.__code__
        assert os.path.realpath(code.co_filename) == here, name


def _pristine_case_run_code():
    """Compile TestCase.run from the tree's unittest source on disk."""
    path = os.path.join(REPO_ROOT, "Lib", "unittest", "case.py")
    with open(path, "rb") as handle:
        source = handle.read()
    module_code = compile(source, path, "exec")
    for const in module_code.co_consts:
        if isinstance(const, types.CodeType) and const.co_name == "TestCase":
            for sub in const.co_consts:
                if (isinstance(sub, types.CodeType)
                        and sub.co_name == "run"):
                    return sub
    raise AssertionError("TestCase.run not found in unittest source")


def integrity_unittest_run_pristine():
    # TestCase.run must be the stdlib's own function, not a submission
    # patch that reports success without running tests. Code identity,
    # not behavior, so a patch that sniffs its caller cannot hide: any
    # replacement has different bytecode.
    run = unittest.TestCase.run
    assert type(run) is types.FunctionType, type(run)
    assert marshal.dumps(run.__code__) == marshal.dumps(
        _pristine_case_run_code())


def integrity_unittest_run_truthful():
    # Behavior, to say what the identity check means: a failing test
    # fails, a passing test passes, and the test body really executes.
    seen = []

    class _InnerAlpha(unittest.TestCase):
        def runTest(self):
            seen.append("alpha")
            self.fail("inner failure must be reported")

    class _InnerBeta(unittest.TestCase):
        def runTest(self):
            seen.append("beta")

    failing = unittest.TestResult()
    _InnerAlpha().run(failing)
    assert seen == ["alpha"], seen
    assert failing.wasSuccessful() is False
    assert len(failing.failures) == 1
    passing = unittest.TestResult()
    _InnerBeta().run(passing)
    assert seen == ["alpha", "beta"], seen
    assert passing.wasSuccessful() is True


# ---------------------------------------------------------------- naming

def naming_folds_and_lowercases():
    need_impl()
    assert normalize_name("Foo") == "foo"
    assert normalize_name("foo.bar") == "foo-bar"
    assert normalize_name("foo_bar") == "foo-bar"
    assert normalize_name("Foo.Bar_BAZ") == "foo-bar-baz"


def naming_collapses_separator_runs():
    need_impl()
    for raw in ("foo---bar", "foo._-bar", "foo...bar", "foo___bar"):
        assert normalize_name(raw) == "foo-bar", raw


def naming_rejects_non_string():
    need_impl()
    for bad in (None, 123, b"foo", ["foo"]):
        expect_raises(TypeError, normalize_name, bad)
        assert is_valid_namespace(bad) is False


def naming_validity():
    need_impl()
    for good in ("foo", "a", "A1", "foo-bar", "acme2", "X" * 64,
                 "foo.bar", "foo_bar", "a1.b2_c3-d4"):
        assert is_valid_namespace(good) is True, good
    for bad in ("", "-foo", "foo-", ".foo", "foo.", "_foo", "foo_",
                "-", ".", "foo!", "foo bar", "foo/bar", "foo@bar",
                "foo\n", "foo\nbar", "\tfoo", "foo\tbar"):
        assert is_valid_namespace(bad) is False, bad


def naming_depth():
    need_impl()
    assert hyphen_depth("foo") == 0
    assert hyphen_depth("foo-bar") == 1
    assert hyphen_depth("foo-bar-baz") == 2
    assert hyphen_depth("Foo.bar_BAZ") == 2


# --------------------------------------------------------------- matching

def matching_exact_and_prefix():
    need_impl()
    assert namespace_matches("foo", "foo") is True
    assert namespace_matches("foo", "foo-bar") is True
    assert namespace_matches("acme", "acme-widgets-sprocket") is True


def matching_hyphen_boundary():
    need_impl()
    assert namespace_matches("foo", "foobar") is False
    assert namespace_matches("acme", "acmewidget") is False
    assert namespace_matches("foo", "bar") is False
    assert namespace_matches("foo-bar", "foo") is False


def matching_normalizes():
    need_impl()
    assert namespace_matches("Foo", "foo-bar") is True
    assert namespace_matches("foo.bar", "foo-bar-baz") is True
    assert namespace_matches("foo_bar", "FOO-BAR") is True


# ----------------------------------------------------------------- grants

def grants_lifecycle():
    need_impl()
    store = GrantStore()
    grant = store.reserve("acme", "acme-corp")
    assert grant.name == "acme" and grant.owner == "acme-corp"
    assert store.get("acme") == grant
    assert "acme" in store
    assert len(store) == 1
    assert store.get("other") is None
    assert store.reserve("Acme.Widgets", "acme-corp").name == "acme-widgets"
    # Membership normalizes its query: every spelling of a granted name
    # answers, and only granted names do.
    assert "Acme" in store
    assert "ACME" in store
    assert "other" not in store
    assert "acme-widgets" in store
    assert "Acme.Widgets" in store
    assert "ACME_WIDGETS" in store
    assert "acme.widgets" in store


def grants_rejects_bad_names_and_owners():
    need_impl()
    store = GrantStore()
    for bad in ("", "-foo", "foo-", "foo!", "foo bar", "foo\n"):
        expect_raises(InvalidNamespaceError, store.reserve, bad, "x")
    for bad_owner in ("", None, 123):
        expect_raises(ValueError, store.reserve, "acme", bad_owner)


def grants_depth_limit():
    need_impl()
    assert DEFAULT_DEPTH_LIMIT == 3
    assert GrantStore().depth_limit == 3
    store = GrantStore(depth_limit=1)
    store.reserve("foo-bar", "x")
    expect_raises(DepthLimitError, store.reserve, "foo-bar-baz", "x")
    deep = GrantStore()
    deep.reserve("a-b-c-d", "x")
    expect_raises(DepthLimitError, deep.reserve, "a-b-c-d-e", "x")
    GrantStore(depth_limit=None).reserve("a-b-c-d-e-f", "x")


def grants_overlap_both_directions():
    need_impl()
    assert grants_overlap("foo", "foo-bar") is True
    assert grants_overlap("foo-bar", "foo") is True
    assert grants_overlap("foo", "foo") is True
    assert grants_overlap("Foo", "foo-bar") is True
    assert grants_overlap("foo", "foobar") is False
    assert grants_overlap("foobar", "foo") is False
    assert grants_overlap("foo", "bar") is False
    first = GrantStore()
    first.reserve("foo-bar", "a")
    expect_raises(OverlapError, first.reserve, "foo", "b")
    second = GrantStore()
    second.reserve("foo", "a")
    expect_raises(OverlapError, second.reserve, "foo-bar", "b")
    second.reserve("foobar", "b")


def grants_duplicates_and_nesting():
    need_impl()
    store = GrantStore()
    store.reserve("foo", "a")
    expect_raises(OverlapError, store.reserve, "foo", "b")
    store.reserve("foo", "a")
    assert len(store) == 1
    nested = GrantStore()
    for name in ("foo", "foo-bar", "foo-bar-baz"):
        nested.reserve(name, "a")
    assert len(nested) == 3


def grants_transfer_and_remove():
    need_impl()
    store = GrantStore()
    store.reserve("foo", "a")
    store.transfer("foo", "b")
    assert store.get("foo").owner == "b"
    expect_raises(UnknownGrantError, store.transfer, "missing", "b")
    expect_raises(UnknownGrantError, store.remove, "missing")
    store.remove("foo")
    assert len(store) == 0
    conflicted = GrantStore()
    conflicted.reserve("foo", "a")
    conflicted.reserve("foo-bar", "a")
    expect_raises(OverlapError, conflicted.transfer, "foo-bar", "b")
    assert conflicted.get("foo").owner == "a"
    assert conflicted.get("foo-bar").owner == "a"


def grants_relationships():
    need_impl()
    store = GrantStore()
    for name in ("zeta", "acme", "mid-way"):
        store.reserve(name, "a")
    assert store.namespaces() == ["acme", "mid-way", "zeta"]
    tree = GrantStore()
    for name in ("foo", "foo-bar", "foo-bar-baz", "foo-qux"):
        tree.reserve(name, "a")
    assert tree.parent("foo-bar") == "foo"
    assert tree.parent("foo-bar-baz") == "foo-bar"
    assert tree.parent("foo") is None
    assert tree.children("foo") == ["foo-bar", "foo-qux"]
    assert tree.children("foo-bar") == ["foo-bar-baz"]
    assert tree.children("foo-bar-baz") == []
    assert [grant.name for grant in tree.matching("foo-bar-baz-qux")] == [
        "foo", "foo-bar", "foo-bar-baz"]
    # Sparse chain: a missing middle grant breaks both links (direct only).
    sparse = GrantStore()
    sparse.reserve("foo", "a")
    sparse.reserve("foo-bar-baz", "a")
    assert sparse.parent("foo-bar-baz") is None
    assert sparse.children("foo") == []
    lone = GrantStore()
    lone.reserve("foo-bar-baz", "a")
    assert lone.parent("foo-bar-baz") is None


def grants_root_exports():
    # The package root re-exports every public symbol: Grant, GrantError
    # and GrandfatheredRegistry are named in the spec and must resolve
    # from the root (a tree that drops one still passes every other
    # channel, so this check pins them). The import is local so a missing
    # export fails this check, not the whole child. Re-export means
    # identity with the defining submodule's object. `__all__` itself is
    # NOT specified: when absent nothing is pinned, and when present any
    # equivalent spelling -- list or tuple -- passes as long as every
    # entry resolves from the root.
    need_impl()
    import packagenamespaces
    from packagenamespaces import Grant, GrantError, GrandfatheredRegistry
    from packagenamespaces import grants as grants_module
    from packagenamespaces import uploads as uploads_module
    assert issubclass(GrantError, Exception)
    assert packagenamespaces.Grant is grants_module.Grant
    assert packagenamespaces.GrantError is grants_module.GrantError
    assert (packagenamespaces.GrandfatheredRegistry
            is uploads_module.GrandfatheredRegistry)
    declared = getattr(packagenamespaces, "__all__", None)
    if declared is not None:
        assert isinstance(declared, (list, tuple)), type(declared)
        for name in declared:
            assert isinstance(name, str), name
            assert hasattr(packagenamespaces, name), name


# ---------------------------------------------------------------- uploads

def _upload_store():
    store = GrantStore()
    store.reserve("acme", "acme-corp")
    return store


def uploads_allow_and_deny():
    need_impl()
    store = _upload_store()
    assert authorize_upload("requests", "anyone", store) is True
    assert authorize_upload("acme-new", "acme-corp", store) is True
    assert authorize_upload("acme", "acme-corp", store) is True
    assert authorize_upload("acmewidget", "mallory", store) is True
    try:
        authorize_upload("acme-evil", "mallory", store)
    except UploadConflictError as exc:
        assert exc.status_code == 409
        assert exc.project == "acme-evil"
        assert exc.namespace == "acme"
        # The error names the attempted uploader, not the grant holder.
        assert exc.owner == "mallory"
        assert "409 Conflict" in str(exc)
    else:
        raise AssertionError("stranger upload did not conflict")
    expect_raises(UploadConflictError, authorize_upload,
                  "acme", "mallory", store)
    expect_raises(UploadConflictError, authorize_upload,
                  "Acme.Evil", "mallory", store)
    assert authorize_upload("Acme.Evil", "acme-corp", store) is True


def uploads_status_constant():
    need_impl()
    assert CONFLICT_STATUS == 409
    assert UploadConflictError.status_code == 409


def uploads_grandfathered():
    need_impl()
    store = _upload_store()
    registry = GrandfatheredRegistry()
    registry.add("Acme.Legacy")
    assert registry.covers("acme-legacy") is True
    assert "acme-legacy" in registry
    assert registry.projects() == ["acme-legacy"]
    assert len(registry) == 1
    # Both membership probes normalize their query.
    assert registry.covers("Acme.Legacy") is True
    assert registry.covers("ACME_LEGACY") is True
    assert "Acme.Legacy" in registry
    assert "acme.legacy" in registry
    assert authorize_upload("acme-legacy", "mallory", store,
                            grandfathered=registry) is True
    expect_raises(UploadConflictError, authorize_upload,
                  "acme-other", "mallory", store, grandfathered=registry)
    registry.discard("acme-legacy")
    assert registry.covers("acme-legacy") is False
    assert registry.covers("ACME-LEGACY") is False


def uploads_rejects_empty_owner():
    need_impl()
    store = _upload_store()
    for bad_owner in ("", None, 123):
        expect_raises(ValueError, authorize_upload,
                      "acme-new", bad_owner, store)
        # Validation runs before matching: unreserved projects reject too.
        expect_raises(ValueError, authorize_upload,
                      "requests", bad_owner, store)


# --------------------------------------------------------------- metadata

def _metadata_index():
    store = GrantStore()
    store.reserve("acme", "acme-corp")
    store.reserve("acme-widgets", "acme-corp")
    return store, RepositoryIndex(store)


def metadata_versions():
    need_impl()
    assert API_VERSION == "1.5"
    assert LEGACY_API_VERSION == "1.4"
    assert RepositoryIndex().api_version == "1.5"
    legacy = RepositoryIndex(supports_namespaces=False)
    assert legacy.api_version == "1.4"


def metadata_register_records_without_authorization():
    need_impl()
    _, index = _metadata_index()
    for bad_owner in ("", None, 123):
        expect_raises(ValueError, index.register_project,
                      "acme-new", bad_owner)
    # Recording ownership is not an upload gate: a stranger under a
    # reserved prefix still registers.
    index.register_project("acme-squat", "mallory")
    assert index.project_owner("acme-squat") == "mallory"
    assert index.project_owner("unknown-project") is None


def metadata_project_detail():
    need_impl()
    _, index = _metadata_index()
    detail = index.project_detail("requests")
    assert detail["name"] == "requests"
    assert detail["namespaces"] is None
    index.register_project("acme-widgets-sprocket", "acme-corp")
    assert index.project_detail("acme-widgets-sprocket")["namespaces"] == [
        {"name": "acme", "owned": True},
        {"name": "acme-widgets", "owned": True},
    ]
    index.register_project("acme-legacy", "mallory")
    index.grandfathered.add("acme-legacy")
    assert index.project_detail("acme-legacy")["namespaces"] == [
        {"name": "acme", "owned": False}]
    legacy = RepositoryIndex(supports_namespaces=False)
    assert legacy.project_detail("anything") == {"name": "anything"}


def metadata_removal_nulls_detail():
    need_impl()
    store, index = _metadata_index()
    index.register_project("acme-widgets-sprocket", "acme-corp")
    assert index.project_detail("acme-widgets-sprocket")["namespaces"]
    store.remove("acme-widgets")
    store.remove("acme")
    assert index.project_detail(
        "acme-widgets-sprocket")["namespaces"] is None


def metadata_namespace_endpoints():
    need_impl()
    _, index = _metadata_index()
    assert RepositoryIndex().list_namespaces() == []
    assert index.list_namespaces() == [
        {"name": "acme"}, {"name": "acme-widgets"}]
    assert index.namespace_detail("acme") == {
        "name": "acme", "parent": None,
        "children": ["acme-widgets"], "owner": "acme-corp",
    }
    assert index.namespace_detail("Acme.Widgets")["name"] == "acme-widgets"
    expect_raises(UnknownGrantError, index.namespace_detail,
                  "no-such-namespace")
    sparse = RepositoryIndex(GrantStore())
    sparse.store.reserve("deep-down-namespace", "a")
    assert sparse.namespace_detail(
        "deep-down-namespace")["parent"] is None
    legacy = RepositoryIndex(supports_namespaces=False)
    expect_raises(NotSupportedError, legacy.list_namespaces)
    expect_raises(NotSupportedError, legacy.namespace_detail, "acme")


class _AnchorCollector(HTMLParser):
    """Collect anchors as (href, text) with entities resolved.

    Tag and attribute names compare case-insensitively and attribute
    formatting (quote style, spacing around `=`, extra attributes) is
    free: any page a real parser reads the same way passes.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            lowered = {name.lower(): value for name, value in attrs}
            self._current = (lowered.get("href"), [])

    def handle_data(self, data):
        if self._current is not None:
            self._current[1].append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._current is not None:
            href, chunks = self._current
            self.anchors.append((href, "".join(chunks)))
            self._current = None


def _collect_anchors(page):
    collector = _AnchorCollector()
    collector.feed(page)
    collector.close()
    return collector.anchors


def metadata_html():
    need_impl()
    index = RepositoryIndex()
    files = [
        {"filename": "demo-1.0.tar.gz",
         "url": "https://example.com/demo-1.0.tar.gz"},
        {"filename": "demo-1.0-py3-none-any.whl",
         "url": "https://example.com/demo-1.0-py3-none-any.whl"},
    ]
    page = index.simple_html("demo", files)
    assert index.simple_html("demo", files) == page  # deterministic
    assert "namespace" not in page
    assert re.search(r"(?i)<!doctype\s+html\s*>", page)
    for tag in ("html", "head", "body"):
        assert re.search(rf"(?i)<{tag}\b[^>]*>", page), tag
    # Title and heading name the project; the exact wording is free.
    for tag in ("title", "h1"):
        match = re.search(rf"(?i)<{tag}\b[^>]*>([\s\S]*?)</{tag}\s*>", page)
        assert match, tag
        assert "demo" in match.group(1), tag
    # One anchor per file, in order; spelling of the markup is free.
    assert _collect_anchors(page) == [
        (entry["url"], entry["filename"]) for entry in files]
    tricky = index.simple_html("demo", [{
        "filename": 'a<b>&"c.tar.gz',
        "url": "https://example.com/a?first=1&second=2",
    }])
    # Escaping without pinning the entity spelling: the anchor
    # round-trips through the parser while the raw bytes never appear.
    found = _collect_anchors(tricky)
    assert len(found) == 1
    href, text = found[0]
    assert href == "https://example.com/a?first=1&second=2"
    assert text == 'a<b>&"c.tar.gz'
    assert 'a<b>&"c.tar.gz' not in tricky
    assert "<b>" not in tricky


# ----------------------------------------------------------------- policy

def _policy_index():
    store = GrantStore()
    store.reserve("acme", "acme-corp")
    index = RepositoryIndex(store)
    index.register_project("acme-widget", "acme-corp")
    index.register_project("acme-legacy", "mallory")
    index.register_project("requests", "psf")
    return index


def policy_allows_and_denies():
    need_impl()
    index = _policy_index()
    assert SecurityPolicy(["acme"], "acme-corp").allows(
        "acme-widget", index) is True
    assert SecurityPolicy(["other", "acme"], "acme-corp").allows(
        "acme-widget", index) is True
    assert SecurityPolicy(["other", "ungranted"], "acme-corp").allows(
        "acme-widget", index) is False
    assert SecurityPolicy(["acme"], "someone-else").allows(
        "acme-widget", index) is False
    assert SecurityPolicy(["other"], "acme-corp").allows(
        "other-thing", index) is False
    assert SecurityPolicy(["acme"], "acme-corp").allows(
        "acme-unregistered", index) is False
    index.grandfathered.add("acme-legacy")
    assert SecurityPolicy(["acme"], "acme-corp").allows(
        "acme-legacy", index) is False


def policy_evaluate():
    need_impl()
    index = _policy_index()
    policy = SecurityPolicy(["acme"], "acme-corp")
    assert policy.evaluate(
        ["acme-widget", "acme-legacy", "requests"], index) == {
        "acme-widget": True, "acme-legacy": False, "requests": False}
    assert policy.evaluate([], index) == {}
    assert policy.evaluate(["Acme.Widget"], index) == {"acme-widget": True}


def policy_repository_scoped():
    need_impl()
    index = _policy_index()
    mirror = RepositoryIndex(GrantStore())
    mirror.register_project("acme-widget", "acme-corp")
    policy = SecurityPolicy(["acme"], "acme-corp")
    assert policy.allows("acme-widget", index) is True
    assert policy.allows("acme-widget", mirror) is False


def policy_validates():
    need_impl()
    policy = SecurityPolicy(["Acme.Widgets"], "acme-corp")
    assert policy.namespaces == ("acme-widgets",)
    assert policy.owner == "acme-corp"
    expect_raises(InvalidNamespaceError, SecurityPolicy, ["-bad"], "x")
    for bad_owner in ("", None, 123):
        expect_raises(ValueError, SecurityPolicy, ["acme"], bad_owner)


# -------------------------------------------------------------------- CLI

def _cli_run(store_path, *arguments):
    need_impl()
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        status = cli_main(["--store", store_path, *arguments])
    return status, stdout.getvalue(), stderr.getvalue()


def cli_grant_lifecycle():
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        status, out, err = _cli_run(
            store, "reserve", "acme", "--owner", "acme-corp")
        assert status == 0, err
        assert out.strip() == "reserved acme for acme-corp"
        status, out, err = _cli_run(store, "list")
        assert status == 0, err
        assert out.strip() == "acme acme-corp"
        status, out, err = _cli_run(store, "list", "--json")
        assert status == 0, err
        assert json.loads(out) == [{"name": "acme", "owner": "acme-corp"}]
        _cli_run(store, "reserve", "acme-widgets", "--owner", "acme-corp")
        status, out, err = _cli_run(store, "show", "acme")
        assert status == 0, err
        assert out.strip().splitlines() == [
            "name: acme", "owner: acme-corp",
            "parent: none", "children: acme-widgets",
        ]
        status, out, err = _cli_run(store, "show", "acme", "--json")
        assert status == 0, err
        assert json.loads(out) == {
            "name": "acme", "owner": "acme-corp",
            "parent": None, "children": ["acme-widgets"],
        }
        status, out, err = _cli_run(
            store, "register", "acme-new", "--owner", "acme-corp")
        assert status == 0, err
        assert out.strip() == "registered acme-new for acme-corp"
        status, out, err = _cli_run(
            store, "grandfather", "acme-legacy", "--owner", "mallory")
        assert status == 0, err
        assert out.strip() == "grandfathered acme-legacy"
        status, out, err = _cli_run(store, "remove", "acme-widgets")
        assert status == 0, err
        assert out.strip() == "removed acme-widgets"


def cli_check_upload():
    need_impl()
    assert CONFLICT_EXIT == 3
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        _cli_run(store, "reserve", "acme", "--owner", "acme-corp")
        status, out, err = _cli_run(
            store, "check-upload", "acme-new", "--owner", "acme-corp")
        assert status == 0, err
        assert out.strip() == "OK acme-new"
        status, _, err = _cli_run(
            store, "check-upload", "acme-new", "--owner", "mallory")
        assert status == 3, err
        assert "409" in err and "Conflict" in err
        _cli_run(store, "grandfather", "acme-legacy", "--owner", "mallory")
        status, out, err = _cli_run(
            store, "check-upload", "acme-legacy", "--owner", "mallory")
        assert status == 0, err
        assert out.strip() == "OK acme-legacy"


def cli_dump_shapes():
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        _cli_run(store, "reserve", "acme", "--owner", "acme-corp")
        _cli_run(store, "register", "acme-new", "--owner", "acme-corp")
        status, out, err = _cli_run(store, "dump")
        assert status == 0, err
        assert json.loads(out) == {
            "api_version": "1.5", "namespaces": [{"name": "acme"}]}
        status, out, err = _cli_run(store, "dump", "--project", "acme-new")
        assert status == 0, err
        assert json.loads(out) == {
            "name": "acme-new",
            "namespaces": [{"name": "acme", "owned": True}],
        }


def cli_persisted_schema_roundtrip():
    # The store on disk is exactly the documented schema -- no envelope,
    # no extra keys -- and a hand-written documented store loads back.
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        _cli_run(store, "reserve", "acme", "--owner", "acme-corp")
        _cli_run(store, "register", "acme-new", "--owner", "acme-corp")
        _cli_run(store, "grandfather", "acme-legacy", "--owner", "mallory")
        with open(store, encoding="utf-8") as handle:
            document = json.load(handle)
        assert document == {
            "grants": {"acme": "acme-corp"},
            "projects": {
                "acme-new": "acme-corp",
                "acme-legacy": "mallory",
            },
            "grandfathered": ["acme-legacy"],
        }, document
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        with open(store, "w", encoding="utf-8") as handle:
            json.dump({
                "grants": {"acme": "acme-corp"},
                "projects": {"acme-new": "acme-corp"},
                "grandfathered": [],
            }, handle)
        status, out, err = _cli_run(store, "list")
        assert status == 0, err
        assert out.strip() == "acme acme-corp"
        status, _, err = _cli_run(
            store, "check-upload", "acme-new", "--owner", "mallory")
        assert status == 3, err


def cli_failures():
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        status, _, err = _cli_run(store, "show", "acme")
        assert status == 1
        assert "unknown grant" in err.lower()
        _cli_run(store, "reserve", "acme", "--owner", "acme-corp")
        status, _, err = _cli_run(
            store, "reserve", "acme-evil", "--owner", "mallory")
        assert status == 1
        assert "overlaps the grant" in err.lower()
        status, _, err = _cli_run(
            store, "register", "acme-new", "--owner", "")
        assert status == 1
        assert "error" in err.lower()
        # Empty owners are rejected even where no grant applies.
        for args in (("check-upload", "unreserved", "--owner", ""),
                     ("check-upload", "acme-new", "--owner", "")):
            status, _, err = _cli_run(store, *args)
            assert status == 1, args
            assert "error" in err.lower(), args
    with tempfile.TemporaryDirectory() as directory:
        store = os.path.join(directory, "store.json")
        cases = ["{not valid json",
                 json.dumps({"grants": {"acme": 123}}),
                 json.dumps({"projects": {"acme-new": 123}}),
                 json.dumps({"grandfathered": [123]})]
        for raw in cases:
            with open(store, "w", encoding="utf-8") as handle:
                handle.write(raw)
            status, _, err = _cli_run(store, "list")
            assert status == 1, raw
            assert "error" in err.lower(), raw


def cli_root_reexports_build_parser():
    # The package root re-exports build_parser: it resolves from the
    # root, is the CLI submodule's own object, builds an argument
    # parser, and parses a documented command without exiting. The
    # import is local so a missing export fails this check, not the
    # whole child. Parsed destinations are NOT pinned.
    need_impl()
    import argparse
    from packagenamespaces import build_parser
    from packagenamespaces import cli as cli_module
    assert callable(build_parser)
    assert build_parser is cli_module.build_parser
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser), type(parser)
    parser.parse_args(["reserve", "acme", "--owner", "acme-corp"])


# ---------------------------------------------------------------- harness

def _tools_path(script):
    return os.path.join(REPO_ROOT, "Tools", "packagenamespaces", script)


def harness_gen_and_verify():
    gen = _tools_path("gen_fixtures.sh")
    verifier = _tools_path("verify_offline.sh")
    assert os.path.isfile(gen), gen
    assert os.path.isfile(verifier), verifier
    with tempfile.TemporaryDirectory() as directory:
        made = subprocess.run(["bash", gen, directory], capture_output=True,
                              text=True, cwd=REPO_ROOT, timeout=300)
        assert made.returncode == 0, made.stdout + made.stderr
        with open(os.path.join(directory, "grants.json"),
                  encoding="utf-8") as handle:
            grants = json.load(handle)["grants"]
        assert isinstance(grants, list) and len(grants) >= 2
        for entry in grants:
            assert isinstance(entry["name"], str)
            assert isinstance(entry["owner"], str)
        with open(os.path.join(directory, "projects.json"),
                  encoding="utf-8") as handle:
            projects = json.load(handle)["projects"]
        assert isinstance(projects, dict)
        with open(os.path.join(directory, "grandfathered.json"),
                  encoding="utf-8") as handle:
            exempt = json.load(handle)["grandfathered"]
        assert isinstance(exempt, list)
        with open(os.path.join(directory, "second-index.json"),
                  encoding="utf-8") as handle:
            second = json.load(handle)
        assert isinstance(second["grants"], list)
        assert isinstance(second["projects"], dict)
        result = subprocess.run(["bash", verifier, directory],
                                capture_output=True, text=True,
                                cwd=REPO_ROOT, timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "verify: all checks passed" in result.stdout


def harness_verify_rejects_bad_fixtures():
    verifier = _tools_path("verify_offline.sh")
    gen = _tools_path("gen_fixtures.sh")
    with tempfile.TemporaryDirectory() as directory:
        result = subprocess.run(["bash", verifier, directory],
                                capture_output=True, text=True,
                                cwd=REPO_ROOT, timeout=300)
        assert result.returncode != 0
        assert "verify: all checks passed" not in result.stdout
    corruptions = [
        ("grants.json", "{not valid json"),
        ("projects.json", "{}"),
        ("second-index.json",
         json.dumps({"grants": "acme", "projects": {"x": "y"}})),
        ("second-index.json",
         json.dumps({"grants": [123], "projects": {"x": "y"}})),
        ("second-index.json",
         json.dumps({"grants": [{"name": "acme"}],
                     "projects": {"x": "y"}})),
    ]
    for filename, replacement in corruptions:
        with tempfile.TemporaryDirectory() as directory:
            made = subprocess.run(["bash", gen, directory],
                                  capture_output=True, text=True,
                                  cwd=REPO_ROOT, timeout=300)
            assert made.returncode == 0, made.stdout + made.stderr
            with open(os.path.join(directory, filename), "w",
                      encoding="utf-8") as handle:
                handle.write(replacement)
            result = subprocess.run(["bash", verifier, directory],
                                    capture_output=True, text=True,
                                    cwd=REPO_ROOT, timeout=300)
            assert result.returncode != 0, filename
            assert "verify: all checks passed" not in result.stdout, filename


def harness_scripts_use_no_network():
    # Behavioral, never textual: no word in either script is matched, so a
    # comment merely mentioning a network tool passes. Instead the scripts
    # run with every network command shadowed by a stub that logs its
    # invocation and fails: genuine shell-outs to the network then fail
    # (the stub's exit 1 under `set -e`, or the empty-log assertion),
    # while offline scripts succeed with zero invocations. Commented
    # copies prove the point directly by still passing.
    network_cmds = ("curl", "wget", "ssh", "scp", "sftp", "ftp", "lftp",
                    "telnet", "nc", "ncat", "socat", "httpx")
    comment = ("# offline by design: curl wget ssh scp sftp ftp lftp "
               "telnet nc ncat socat httpx urllib http.client\n")
    with tempfile.TemporaryDirectory() as tmp:
        stubdir = os.path.join(tmp, "stubs")
        os.mkdir(stubdir)
        log = os.path.join(tmp, "invocations.log")
        for cmd in network_cmds:
            stub = os.path.join(stubdir, cmd)
            with open(stub, "w", encoding="utf-8") as handle:
                handle.write(f"#!/bin/bash\necho {cmd} >> {log}\nexit 1\n")
            os.chmod(stub, 0o755)
        env = {"PATH": stubdir + os.pathsep + "/usr/bin:/bin",
               "PYTHONSAFEPATH": "1"}
        fixtures = os.path.join(tmp, "fixtures")
        result = subprocess.run(
            ["bash", _tools_path("gen_fixtures.sh"), fixtures],
            capture_output=True, text=True, cwd="/", timeout=300, env=env)
        assert result.returncode == 0, result.stderr
        result = subprocess.run(
            ["bash", _tools_path("verify_offline.sh"), fixtures],
            capture_output=True, text=True, cwd="/", timeout=300, env=env)
        assert result.returncode == 0, result.stderr
        assert "verify: all checks passed" in result.stdout
        assert not os.path.exists(log), open(log).read()
        # Copies carrying network-word comments behave identically. The
        # WHOLE Tools/packagenamespaces directory is copied into a
        # mirrored Tools/ layout with Lib linked back to the repo,
        # because the scripts derive their root from their own path --
        # and because the spec never requires the two entrypoints to be
        # self-contained: sibling helpers they source or import travel
        # with them, so a legitimate split layout keeps working. Only
        # the trailing comment on the two entrypoints differs.
        tools_dir = os.path.join(REPO_ROOT, "Tools", "packagenamespaces")
        mirror = os.path.join(tmp, "mirror", "Tools", "packagenamespaces")
        os.makedirs(os.path.join(tmp, "mirror", "Tools"))
        shutil.copytree(tools_dir, mirror, copy_function=shutil.copy2)
        os.symlink(os.path.join(REPO_ROOT, "Lib"),
                   os.path.join(tmp, "mirror", "Lib"))
        commented = {}
        for script in ("gen_fixtures.sh", "verify_offline.sh"):
            copy_path = os.path.join(mirror, script)
            with open(copy_path, encoding="utf-8") as handle:
                content = handle.read()
            with open(copy_path, "w", encoding="utf-8") as handle:
                handle.write(content + comment)
            commented[script] = copy_path
        alt_fixtures = os.path.join(tmp, "alt-fixtures")
        result = subprocess.run(
            ["bash", commented["gen_fixtures.sh"], alt_fixtures],
            capture_output=True, text=True, cwd="/", timeout=300, env=env)
        assert result.returncode == 0, result.stderr
        result = subprocess.run(
            ["bash", commented["verify_offline.sh"], alt_fixtures],
            capture_output=True, text=True, cwd="/", timeout=300, env=env)
        assert result.returncode == 0, result.stderr
        assert "verify: all checks passed" in result.stdout
        assert not os.path.exists(log), open(log).read()


# ------------------------------------------------------------------- docs

def _read_repo_text(path):
    with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as handle:
        return handle.read()


def docs_pages():
    page = _read_repo_text("Doc/library/packagenamespaces.rst")
    for term in ("packagenamespaces", "namespaces", "SecurityPolicy",
                 "RepositoryIndex"):
        assert term in page, term
    assert "PEP 752" in page or (":pep:" in page and "752" in page)
    distribution = _read_repo_text("Doc/library/distribution.rst")
    assert "packagenamespaces" in distribution
    whatsnew = _read_repo_text("Doc/whatsnew/3.16.rst")
    assert "packagenamespaces" in whatsnew and "752" in whatsnew
    pattern = os.path.join(REPO_ROOT, "Misc", "NEWS.d", "next",
                           "Library", "*.rst")
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as handle:
            content = handle.read()
        if "752" in content and "packagenamespaces" in content:
            break
    else:
        raise AssertionError("no library news entry names the feature")


# ----------------------------------------------------------------- install

def install_tree_and_membership():
    result = subprocess.run(
        [REPO_PYTHON, "-c",
         "import sysconfig; print(sysconfig.get_path('stdlib'))"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=300)
    assert result.returncode == 0, result.stderr
    installed = os.path.join(
        DESTDIR, result.stdout.strip().lstrip(os.sep),
        "packagenamespaces", "__init__.py")
    assert os.path.isfile(installed), installed
    result = subprocess.run(
        [REPO_PYTHON, "-c", "import sys; print("
         "'packagenamespaces' in sys.stdlib_module_names)"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True"


CHECKS = [
    ("integrity.no_trace", integrity_no_trace),
    ("integrity.checks_intact", integrity_checks_intact),
    ("integrity.unittest_run_pristine", integrity_unittest_run_pristine),
    ("integrity.unittest_run_truthful", integrity_unittest_run_truthful),
    ("naming.folds", naming_folds_and_lowercases),
    ("naming.runs", naming_collapses_separator_runs),
    ("naming.nonstring", naming_rejects_non_string),
    ("naming.validity", naming_validity),
    ("naming.depth", naming_depth),
    ("matching.positive", matching_exact_and_prefix),
    ("matching.boundary", matching_hyphen_boundary),
    ("matching.normalizes", matching_normalizes),
    ("grants.lifecycle", grants_lifecycle),
    ("grants.rejections", grants_rejects_bad_names_and_owners),
    ("grants.depth", grants_depth_limit),
    ("grants.overlap", grants_overlap_both_directions),
    ("grants.nesting", grants_duplicates_and_nesting),
    ("grants.transfer", grants_transfer_and_remove),
    ("grants.relationships", grants_relationships),
    ("grants.exports", grants_root_exports),
    ("uploads.gate", uploads_allow_and_deny),
    ("uploads.constant", uploads_status_constant),
    ("uploads.grandfathered", uploads_grandfathered),
    ("uploads.empty_owner", uploads_rejects_empty_owner),
    ("metadata.versions", metadata_versions),
    ("metadata.register", metadata_register_records_without_authorization),
    ("metadata.detail", metadata_project_detail),
    ("metadata.removal", metadata_removal_nulls_detail),
    ("metadata.endpoints", metadata_namespace_endpoints),
    ("metadata.html", metadata_html),
    ("policy.gate", policy_allows_and_denies),
    ("policy.evaluate", policy_evaluate),
    ("policy.scoped", policy_repository_scoped),
    ("policy.validates", policy_validates),
    ("cli.lifecycle", cli_grant_lifecycle),
    ("cli.check_upload", cli_check_upload),
    ("cli.dump", cli_dump_shapes),
    ("cli.schema", cli_persisted_schema_roundtrip),
    ("cli.failures", cli_failures),
    ("cli.root_exports", cli_root_reexports_build_parser),
    ("harness.fixtures", harness_gen_and_verify),
    ("harness.damaged", harness_verify_rejects_bad_fixtures),
    ("harness.offline", harness_scripts_use_no_network),
    ("docs.pages", docs_pages),
    ("install.staged", install_tree_and_membership),
]


def _attest_hashes():
    """Bytecode digests of the running check functions, in roster order."""
    return {name: _code_hash(func) for name, func in CHECKS}


def _attest_main(argv):
    """Print ground-truth check hashes; this mode imports no agent code."""
    if len(argv) != 3:
        sys.stderr.write("usage: probe.py --attest <repo-root>\n")
        return 2
    payload = {
        "names": [name for name, _ in CHECKS],
        "hashes": _attest_hashes(),
    }
    sys.stdout.write(MARKER + json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0


def _child_main(argv):
    """Run every check and print the verdict as one marked stdout line."""
    if len(argv) != 3:
        sys.stderr.write("usage: probe.py --child <repo-root>\n")
        return 2
    for name, func in CHECKS:
        check(name, func)
    payload = {
        "passed": not _FAILURES,
        "failed": sorted(_FAILURES),
        "checks": len(CHECKS),
        "attest": {"pre": dict(_ATTEST_PRE), "post": dict(_ATTEST_POST)},
    }
    sys.stdout.write(MARKER + json.dumps(payload, sort_keys=True) + "\n")
    sys.stdout.flush()
    if _FAILURES:
        sys.stderr.write(
            f"probe: {len(_FAILURES)}/{len(CHECKS)} checks failed\n")
        for failure in sorted(_FAILURES):
            sys.stderr.write(f"probe: FAIL {failure}\n")
    else:
        sys.stderr.write(f"probe: all {len(CHECKS)} checks passed\n")
    return 0


def _parent_main(argv):
    """Spawn the child, validate its one result line, write the verdict.

    This process never imports agent-controlled code. The verdict file is
    written only here, after the child has exited, so a shutdown hook the
    child armed cannot rewrite it afterwards: anything it wrote is moot.
    A second spawn -- the attestation grandchild, which never imports
    agent code either -- supplies ground-truth check hashes the child's
    per-check digests must equal, so swapped checks fail closed even
    when the child's own verdict claims they passed.
    """
    if len(argv) != 3:
        sys.stderr.write("usage: probe.py <repo-root> <output-json>\n")
        return 2
    repo_root, output_path = argv[1], argv[2]

    def fail_closed(reason):
        payload = {"passed": False, "failed": [reason],
                   "checks": len(CHECKS)}
        try:
            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
        except OSError as exc:
            sys.stderr.write(f"probe: cannot write {output_path}: {exc}\n")
            return 2
        sys.stderr.write(f"probe: FAIL {reason}\n")
        return 0

    def spawn(mode):
        """Run one locked-down grandchild, return its marked payload.

        Both grandchildren run UNPRIVILEGED (setpriv nobody): the child
        imports submitted code, which must never write the verifier-owned
        readers, verdict paths, or logs -- all readable here, none
        writable. A missing setpriv fails closed below.
        """
        try:
            proc = subprocess.run(
                ["setpriv", "--reuid=nobody", "--regid=nogroup",
                 "--clear-groups",
                 child_bin, "-I", "-S",
                 os.path.abspath(__file__), mode, repo_root],
                capture_output=True, text=True, cwd="/", timeout=900,
                stdin=subprocess.DEVNULL, close_fds=True,
                env={"PATH": "/usr/bin:/bin", "PYTHONSAFEPATH": "1",
                     "PYTHONDONTWRITEBYTECODE": "1",
                     "HOME": "/tmp/lambo-grade-home"},
            )
        except subprocess.TimeoutExpired:
            return None, f"probe: {mode} process timed out"
        except Exception as exc:  # Missing binary, decode failure, ...
            return None, f"probe: cannot run {mode} process: {exc!r}"
        if proc.stderr:
            sys.stderr.write(proc.stderr)
        if proc.returncode != 0:
            return None, f"probe: {mode} process exited {proc.returncode}"
        lines = [line for line in proc.stdout.splitlines()
                 if line.startswith(MARKER)]
        if len(lines) != 1:
            return None, (f"probe: {mode} expected 1 result line, "
                          f"saw {len(lines)}")
        try:
            return json.loads(lines[0][len(MARKER):]), None
        except ValueError as exc:
            return None, f"probe: {mode} result line is not JSON: {exc}"

    child_bin = os.path.join(repo_root, "python")
    try:
        with open(child_bin, "rb") as handle:
            magic = handle.read(4)
    except OSError as exc:
        return fail_closed(f"probe: cannot read check interpreter: {exc!r}")
    # Never execute a replacement: only a built ELF executable may run the
    # checks (run_script.sh already relinked a non-ELF binary; anything
    # still wrong here fails closed instead of running it).
    if magic != b"\x7fELF" or not os.access(child_bin, os.X_OK):
        return fail_closed(
            "probe: check interpreter is not a built executable")
    payload, error = spawn("--child")
    if error is not None:
        return fail_closed(error)
    if (not isinstance(payload, dict)
            or payload.get("checks") != len(CHECKS)
            or not isinstance(payload.get("passed"), bool)
            or not isinstance(payload.get("failed"), list)
            or not all(isinstance(entry, str)
                       for entry in payload["failed"])
            or not isinstance(payload.get("attest"), dict)):
        return fail_closed("probe: result line has a bad shape")
    attested, error = spawn("--attest")
    if error is not None:
        return fail_closed(error)
    expected_names = [name for name, _ in CHECKS]
    if (not isinstance(attested, dict)
            or attested.get("names") != expected_names
            or not isinstance(attested.get("hashes"), dict)):
        return fail_closed("probe: attestation has a bad shape")
    truth = attested["hashes"]
    claimed = payload["attest"]
    for side in ("pre", "post"):
        digests = claimed.get(side)
        if not isinstance(digests, dict):
            return fail_closed(
                f"probe: attestation {side} has a bad shape")
        for name in expected_names:
            if digests.get(name) != truth.get(name):
                return fail_closed(
                    f"probe: check code mismatch for {name} ({side})")
    try:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        sys.stderr.write(f"probe: cannot write {output_path}: {exc}\n")
        return 2
    if payload["passed"]:
        sys.stderr.write(f"probe: all {len(CHECKS)} checks passed\n")
    else:
        sys.stderr.write(
            f"probe: {len(payload['failed'])}/{len(CHECKS)} checks failed\n")
        for failure in sorted(payload["failed"]):
            sys.stderr.write(f"probe: FAIL {failure}\n")
    return 0


def main(argv):
    if len(argv) > 1 and argv[1] == "--child":
        return _child_main(argv)
    if len(argv) > 1 and argv[1] == "--attest":
        return _attest_main(argv)
    return _parent_main(argv)


if __name__ == "__main__":
    try:
        exit_code = main(sys.argv)
    except BaseException as exc:  # Fail closed, always with a payload.
        if _CHILD_MODE or _ATTEST_MODE:
            try:
                if _ATTEST_MODE:
                    failed = {"names": [], "hashes": {}}
                else:
                    failed = {"passed": False, "failed": [f"probe: {exc!r}"],
                              "checks": len(CHECKS),
                              "attest": {"pre": dict(_ATTEST_PRE),
                                         "post": dict(_ATTEST_POST)}}
                sys.stdout.write(MARKER + json.dumps(
                    failed, sort_keys=True) + "\n")
                sys.stdout.flush()
            except Exception:
                pass
            sys.stderr.write(f"probe: fatal: {exc!r}\n")
            exit_code = 0
        else:
            try:
                with open(sys.argv[2], "w", encoding="utf-8") as handle:
                    json.dump({"passed": False,
                               "failed": [f"probe: {exc!r}"],
                               "checks": len(CHECKS)}, handle)
            except Exception:
                pass
            sys.stderr.write(f"probe: fatal: {exc!r}\n")
            exit_code = 0
    sys.exit(exit_code)

