"""Conformance tests for PEP 752 repository metadata (v1.5)."""

import re
import unittest

try:
    from packagenamespaces.grants import GrantStore, UnknownGrantError
    from packagenamespaces.metadata import (
        API_VERSION,
        LEGACY_API_VERSION,
        NotSupportedError,
        RepositoryIndex,
    )
except Exception as exc:  # ImportError at base; anything else is a broken tree
    GrantStore = UnknownGrantError = None
    API_VERSION = LEGACY_API_VERSION = NotSupportedError = None
    RepositoryIndex = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


DEMO_FILES = [
    {
        "filename": "demo-1.0.tar.gz",
        "url": "https://example.com/demo-1.0.tar.gz",
    },
    {
        "filename": "demo-1.0-py3-none-any.whl",
        "url": "https://example.com/demo-1.0-py3-none-any.whl",
    },
]


class MetadataTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def make_index(self):
        store = GrantStore()
        store.reserve("acme", "acme-corp")
        store.reserve("acme-widgets", "acme-corp")
        return RepositoryIndex(store)

    def test_api_version_is_1_5(self):
        self.require_impl()
        self.assertEqual(API_VERSION, "1.5")
        self.assertEqual(RepositoryIndex().api_version, "1.5")

    def test_legacy_repository_is_1_4_and_silent(self):
        self.require_impl()
        index = RepositoryIndex(supports_namespaces=False)
        self.assertEqual(LEGACY_API_VERSION, "1.4")
        self.assertEqual(index.api_version, "1.4")
        detail = index.project_detail("anything-at-all")
        self.assertEqual(detail, {"name": "anything-at-all"})
        self.assertNotIn("namespaces", detail)

    def test_register_project_validates_owner(self):
        self.require_impl()
        index = RepositoryIndex()
        for bad in ("", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    index.register_project("acme-new", bad)
        index.register_project("acme-new", "acme-corp")
        self.assertEqual(index.project_owner("acme-new"), "acme-corp")
        self.assertIsNone(index.project_owner("unknown-project"))

    def test_legacy_endpoints_raise_not_supported(self):
        self.require_impl()
        index = RepositoryIndex(supports_namespaces=False)
        with self.assertRaises(NotSupportedError):
            index.list_namespaces()
        with self.assertRaises(NotSupportedError):
            index.namespace_detail("acme")

    def test_project_detail_unmatched_is_null(self):
        self.require_impl()
        index = self.make_index()
        detail = index.project_detail("requests")
        self.assertEqual(detail["name"], "requests")
        self.assertIsNone(detail["namespaces"])

    def test_project_detail_matched_owned(self):
        self.require_impl()
        index = self.make_index()
        index.register_project("acme-widgets-sprocket", "acme-corp")
        detail = index.project_detail("acme-widgets-sprocket")
        self.assertEqual(
            detail["namespaces"],
            [
                {"name": "acme", "owned": True},
                {"name": "acme-widgets", "owned": True},
            ],
        )

    def test_project_detail_grandfathered_unowned(self):
        self.require_impl()
        index = self.make_index()
        index.register_project("acme-legacy", "mallory")
        index.grandfathered.add("acme-legacy")
        detail = index.project_detail("acme-legacy")
        self.assertEqual(detail["namespaces"], [{"name": "acme", "owned": False}])

    def test_project_detail_multiple_matches_sorted(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("zeta", "a")
        store.reserve("acme", "a")
        index = RepositoryIndex(store)
        index.register_project("acme-thing", "a")
        detail = index.project_detail("acme-thing")
        self.assertEqual(detail["namespaces"], [{"name": "acme", "owned": True}])
        index.register_project("zeta-thing", "other")
        detail = index.project_detail("zeta-thing")
        self.assertEqual(detail["namespaces"], [{"name": "zeta", "owned": False}])

    def test_grant_removal_nulls_detail(self):
        self.require_impl()
        index = self.make_index()
        index.register_project("acme-widgets-sprocket", "acme-corp")
        self.assertIsNotNone(
            index.project_detail("acme-widgets-sprocket")["namespaces"]
        )
        index.store.remove("acme")
        index.store.remove("acme-widgets")
        detail = index.project_detail("acme-widgets-sprocket")
        self.assertIsNone(detail["namespaces"])

    def test_namespace_list_shape(self):
        self.require_impl()
        index = self.make_index()
        self.assertEqual(
            index.list_namespaces(),
            [{"name": "acme"}, {"name": "acme-widgets"}],
        )

    def test_namespace_list_empty(self):
        self.require_impl()
        self.assertEqual(RepositoryIndex().list_namespaces(), [])

    def test_namespace_detail_shape(self):
        self.require_impl()
        index = self.make_index()
        self.assertEqual(
            index.namespace_detail("acme"),
            {
                "name": "acme",
                "parent": None,
                "children": ["acme-widgets"],
                "owner": "acme-corp",
            },
        )
        self.assertEqual(
            index.namespace_detail("acme-widgets"),
            {
                "name": "acme-widgets",
                "parent": "acme",
                "children": [],
                "owner": "acme-corp",
            },
        )

    def test_namespace_detail_normalizes_input(self):
        self.require_impl()
        index = self.make_index()
        detail = index.namespace_detail("Acme.Widgets")
        self.assertEqual(detail["name"], "acme-widgets")

    def test_namespace_detail_unknown_raises(self):
        self.require_impl()
        index = self.make_index()
        with self.assertRaises(UnknownGrantError):
            index.namespace_detail("no-such-namespace")

    def test_namespace_detail_parent_null_without_grant(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("deep-down-namespace", "a")
        index = RepositoryIndex(store)
        detail = index.namespace_detail("deep-down-namespace")
        self.assertIsNone(detail["parent"])

    def test_namespace_detail_children_direct_only(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "a")
        store.reserve("foo-bar", "a")
        store.reserve("foo-bar-baz", "a")
        index = RepositoryIndex(store)
        self.assertEqual(index.namespace_detail("foo")["children"], ["foo-bar"])

    def test_html_carries_no_namespace_keys(self):
        self.require_impl()
        index = self.make_index()
        page = index.simple_html(
            "acme-thing",
            [{"filename": "acme-thing-1.tar.gz", "url": "https://x/y"}],
        )
        self.assertNotIn("namespace", page)
        self.assertNotIn("namespaces", page)
        self.assertIn("acme-thing-1.tar.gz", page)

    def test_html_semantically_stable(self):
        self.require_impl()
        index = RepositoryIndex()
        page = index.simple_html("demo", [dict(entry) for entry in DEMO_FILES])
        self.assertIsInstance(page, str)
        self.assertIn("<!doctype html>", page.lower())
        for tag in ("<html", "<head", "<body"):
            self.assertIn(tag, page.lower())
        self.assertRegex(page, r"<title>\s*Links for demo\s*</title>")
        self.assertRegex(page, r"<h1>\s*Links for demo\s*</h1>")
        position = 0
        for entry in DEMO_FILES:
            pattern = (
                r"<a\b[^>]*href=\""
                + re.escape(entry["url"])
                + r"\"[^>]*>"
                + re.escape(entry["filename"])
                + r"</a>"
            )
            found = re.search(pattern, page[position:])
            self.assertIsNotNone(found, entry["filename"])
            position += found.end()
        self.assertNotIn("namespace", page)
        self.assertNotIn("namespaces", page)
        again = index.simple_html("demo", [dict(entry) for entry in DEMO_FILES])
        self.assertEqual(page, again)

    def test_html_escapes_special_characters(self):
        self.require_impl()
        index = RepositoryIndex()
        page = index.simple_html(
            "demo",
            [{"filename": "a<b>&\"c.tar.gz", "url": "https://x/?a=1&b=2"}],
        )
        self.assertIn("a&lt;b&gt;&amp;&quot;c.tar.gz", page)
        self.assertIn("https://x/?a=1&amp;b=2", page)
        self.assertNotIn("<b>", page)


if __name__ == "__main__":
    unittest.main()
