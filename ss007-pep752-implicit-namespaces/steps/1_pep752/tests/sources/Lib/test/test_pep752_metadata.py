import html
import re
import unittest

try:
    from packagenamespaces import GrantStore, UnknownGrantError
    from packagenamespaces.metadata import (
        API_VERSION,
        LEGACY_API_VERSION,
        NotSupportedError,
        RepositoryIndex,
    )
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class MetadataTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot import the namespace API: {_IMPORT_ERROR}")

    def make_index(self):
        store = GrantStore()
        store.reserve("acme-widgets", "acme-corp")
        store.reserve("acme", "acme-corp")
        return store, RepositoryIndex(store)

    def test_namespace_list_empty(self):
        self.require_impl()
        self.assertEqual(RepositoryIndex().list_namespaces(), [])

    def test_namespace_list_shape(self):
        self.require_impl()
        _, index = self.make_index()
        self.assertEqual(
            index.list_namespaces(),
            [{"name": "acme"}, {"name": "acme-widgets"}],
        )

    def test_namespace_detail_shape(self):
        self.require_impl()
        _, index = self.make_index()
        expected = {
            "acme-widgets": {
                "owner": "acme-corp",
                "children": [],
                "parent": "acme",
                "name": "acme-widgets",
            },
            "acme": {
                "owner": "acme-corp",
                "children": ["acme-widgets"],
                "parent": None,
                "name": "acme",
            },
        }
        for name, detail in expected.items():
            with self.subTest(namespace=name):
                self.assertEqual(index.namespace_detail(name), detail)

    def test_namespace_detail_children_direct_only(self):
        self.require_impl()
        store = GrantStore()
        for name in ("foo-bar-baz", "foo-bar", "foo"):
            store.reserve(name, "acme-corp")
        index = RepositoryIndex(store)
        self.assertEqual(index.namespace_detail("foo")["children"], ["foo-bar"])

    def test_namespace_detail_parent_null_without_grant(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("deep-down-namespace", "acme-corp")
        index = RepositoryIndex(store)
        self.assertIsNone(index.namespace_detail("deep-down-namespace")["parent"])

    def test_namespace_detail_unknown_raises(self):
        self.require_impl()
        _, index = self.make_index()
        with self.assertRaises(UnknownGrantError):
            index.namespace_detail("no-such-namespace")

    def test_namespace_detail_normalizes_input(self):
        self.require_impl()
        _, index = self.make_index()
        self.assertEqual(
            index.namespace_detail("Acme.Widgets")["name"], "acme-widgets"
        )

    def test_project_detail_multiple_matches_sorted(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("zeta", "a")
        store.reserve("acme", "a")
        index = RepositoryIndex(store)
        index.register_project("zeta-thing", "other")
        index.register_project("acme-thing", "a")
        self.assertEqual(
            index.project_detail("zeta-thing")["namespaces"],
            [{"name": "zeta", "owned": False}],
        )
        self.assertEqual(
            index.project_detail("acme-thing")["namespaces"],
            [{"name": "acme", "owned": True}],
        )

    def test_project_detail_matched_owned(self):
        self.require_impl()
        _, index = self.make_index()
        index.register_project("acme-widgets-sprocket", "acme-corp")
        self.assertEqual(
            index.project_detail("acme-widgets-sprocket")["namespaces"],
            [
                {"name": "acme", "owned": True},
                {"name": "acme-widgets", "owned": True},
            ],
        )

    def test_project_detail_grandfathered_unowned(self):
        self.require_impl()
        _, index = self.make_index()
        index.register_project("acme-legacy", "mallory")
        index.grandfathered.add("acme-legacy")
        self.assertEqual(
            index.project_detail("acme-legacy")["namespaces"],
            [{"name": "acme", "owned": False}],
        )

    def test_project_detail_unmatched_is_null(self):
        self.require_impl()
        _, index = self.make_index()
        detail = index.project_detail("requests")
        self.assertEqual(detail["name"], "requests")
        self.assertIn("namespaces", detail)
        self.assertIsNone(detail["namespaces"])

    def test_grant_removal_nulls_detail(self):
        self.require_impl()
        store, index = self.make_index()
        index.register_project("acme-widgets-sprocket", "acme-corp")
        self.assertEqual(
            index.project_detail("acme-widgets-sprocket")["namespaces"],
            [
                {"name": "acme", "owned": True},
                {"name": "acme-widgets", "owned": True},
            ],
        )
        store.remove("acme-widgets")
        store.remove("acme")
        detail = index.project_detail("acme-widgets-sprocket")
        self.assertIn("namespaces", detail)
        self.assertIsNone(detail["namespaces"])

    def test_register_project_validates_owner(self):
        self.require_impl()
        _, index = self.make_index()
        for owner in (None, 123, ""):
            with self.subTest(owner=owner):
                with self.assertRaises(ValueError):
                    index.register_project("acme-new", owner)
        index.register_project("acme-new", "acme-corp")
        self.assertEqual(index.project_owner("acme-new"), "acme-corp")
        self.assertIsNone(index.project_owner("anything-at-all"))

    def test_register_project_records_without_authorization(self):
        self.require_impl()
        _, index = self.make_index()
        index.register_project("acme-squat", "mallory")
        self.assertEqual(index.project_owner("acme-squat"), "mallory")

    def test_legacy_endpoints_raise_not_supported(self):
        self.require_impl()
        store, _ = self.make_index()
        index = RepositoryIndex(store, supports_namespaces=False)
        with self.assertRaises(NotSupportedError):
            index.namespace_detail("acme")
        with self.assertRaises(NotSupportedError):
            index.list_namespaces()

    def test_legacy_repository_is_1_4_and_silent(self):
        self.require_impl()
        self.assertEqual(LEGACY_API_VERSION, "1.4")
        store, _ = self.make_index()
        index = RepositoryIndex(store, supports_namespaces=False)
        self.assertEqual(index.api_version, "1.4")
        detail = index.project_detail("anything-at-all")
        self.assertNotIn("namespaces", detail)
        self.assertEqual(detail, {"name": "anything-at-all"})

    def test_api_version_is_1_5(self):
        self.require_impl()
        self.assertEqual(RepositoryIndex().api_version, "1.5")
        self.assertEqual(API_VERSION, "1.5")

    def test_html_escapes_special_characters(self):
        self.require_impl()
        index = RepositoryIndex()
        filename = 'a<b>&"c.tar.gz'
        url = "https://example.com/a?first=1&second=2"
        page = index.simple_html(
            "demo",
            [{
                "filename": filename,
                "url": url,
            }],
        )
        anchor = re.search(
            r"""<a\b[^>]*href=(["'])([\s\S]*?)\1[^>]*>([\s\S]*?)</a>""",
            page,
        )
        self.assertIsNotNone(anchor)
        self.assertEqual(len(re.findall(r"<a\b", page)), 1)
        self.assertEqual(html.unescape(anchor.group(2)), url)
        self.assertEqual(html.unescape(anchor.group(3)), filename)
        self.assertNotIn(filename, page)
        self.assertNotIn("<b>", page)

    def test_html_carries_no_namespace_keys(self):
        self.require_impl()
        _, index = self.make_index()
        page = index.simple_html(
            "acme-thing",
            [{
                "url": "https://example.com/acme-thing-1.0.tar.gz",
                "filename": "acme-thing-1.0.tar.gz",
            }],
        )
        self.assertIn("acme-thing-1.0.tar.gz", page)
        self.assertNotIn("namespace", page)
        self.assertNotIn("namespaces", page)

    def test_html_semantically_stable(self):
        self.require_impl()
        index = RepositoryIndex()
        files = [
            {
                "filename": "demo-1.0.tar.gz",
                "url": "https://example.com/demo-1.0.tar.gz",
            },
            {
                "filename": "demo-1.0-py3-none-any.whl",
                "url": "https://example.com/demo-1.0-py3-none-any.whl",
            },
        ]
        page = index.simple_html("demo", files)
        self.assertEqual(index.simple_html("demo", files), page)
        self.assertNotIn("namespace", page)
        self.assertNotIn("namespaces", page)
        self.assertRegex(page, r"(?i)<!doctype\s+html\s*>")
        for tag in ("html", "head", "body"):
            with self.subTest(tag=tag):
                self.assertRegex(page, rf"(?i)<{tag}\b[^>]*>")
        for tag in ("title", "h1"):
            with self.subTest(tag=tag):
                element = re.search(
                    rf"(?i)<{tag}\b[^>]*>([\s\S]*?)</{tag}\s*>",
                    page,
                )
                self.assertIsNotNone(element)
                self.assertIn("demo", element.group(1))
        anchors = []
        for file in files:
            escaped = {}
            for key in ("url", "filename"):
                escaped[key] = "".join(
                    "\\" + char if char in r"\.^$*+?{}[]|()" else char
                    for char in file[key]
                )
            anchors.append(
                rf"""<a\b[^>]*href=(["']){escaped["url"]}\1[^>]*>"""
                rf'{escaped["filename"]}</a>'
            )
        position = 0
        for anchor in anchors:
            match = re.compile(anchor).search(page, position)
            self.assertIsNotNone(match)
            position = match.end()
        self.assertEqual(len(re.findall(r"<a\b", page)), 2)


if __name__ == "__main__":
    unittest.main()
