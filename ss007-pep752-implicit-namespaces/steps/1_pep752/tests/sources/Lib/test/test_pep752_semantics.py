try:
    from packagenamespaces import (
        DEFAULT_DEPTH_LIMIT,
        DepthLimitError,
        GrantStore,
        InvalidNamespaceError,
        OverlapError,
        UnknownGrantError,
        grants_overlap,
        namespace_matches,
    )
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

import unittest


class _ImplementationTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot import packagenamespaces: {_IMPORT_ERROR}")


class MatchingTests(_ImplementationTests):
    def test_unrelated_does_not_match(self):
        self.require_impl()
        for namespace, project in (
            ("foo", "bar"),
            ("foo", "bar-foo"),
            ("foo-bar", "foo"),
        ):
            with self.subTest(namespace=namespace, project=project):
                self.assertFalse(namespace_matches(namespace, project))

    def test_exact_match(self):
        self.require_impl()
        for name in ("foo", "acme-widgets"):
            with self.subTest(name=name):
                self.assertTrue(namespace_matches(name, name))

    def test_match_normalizes_inputs(self):
        self.require_impl()
        for namespace, project in (
            ("Foo", "foo-bar"),
            ("foo.bar", "foo-bar-baz"),
            ("foo_bar", "FOO-BAR"),
        ):
            with self.subTest(namespace=namespace, project=project):
                self.assertTrue(namespace_matches(namespace, project))

    def test_missing_hyphen_does_not_match(self):
        self.require_impl()
        for namespace, project in (("foo", "foobar"), ("acme", "acmewidget")):
            with self.subTest(namespace=namespace, project=project):
                self.assertFalse(namespace_matches(namespace, project))

    def test_prefix_hyphen_match(self):
        self.require_impl()
        for namespace, project in (
            ("foo", "foo-bar"),
            ("acme", "acme-widgets-sprocket"),
        ):
            with self.subTest(namespace=namespace, project=project):
                self.assertTrue(namespace_matches(namespace, project))


class GrantStoreTests(_ImplementationTests):
    def test_reserve_and_get(self):
        self.require_impl()
        store = GrantStore()
        grant = store.reserve("acme", "acme-corp")
        self.assertEqual(grant.owner, "acme-corp")
        self.assertEqual(grant.name, "acme")
        self.assertEqual(store.get("acme"), grant)
        self.assertIn("acme", store)
        self.assertIn("Acme", store)
        self.assertIn("ACME", store)
        self.assertNotIn("other", store)
        self.assertEqual(len(store), 1)
        self.assertIsNone(store.get("other"))

    def test_remove(self):
        self.require_impl()
        store = GrantStore()
        grant = store.reserve("foo", "owner-a")
        self.assertEqual(store.remove("foo"), grant)
        self.assertEqual(len(store), 0)
        self.assertIsNone(store.get("foo"))

    def test_remove_unknown_raises(self):
        self.require_impl()
        store = GrantStore()
        with self.assertRaises(UnknownGrantError):
            store.remove("foo")

    def test_transfer(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        store.transfer("foo", "owner-b")
        self.assertEqual(store.get("foo").owner, "owner-b")

    def test_transfer_unknown_raises(self):
        self.require_impl()
        store = GrantStore()
        with self.assertRaises(UnknownGrantError):
            store.transfer("foo", "owner-b")

    def test_transfer_conflicting_raises(self):
        self.require_impl()
        for names, transferred in (
            (("foo", "foo-bar"), "foo-bar"),
            (("foo-bar", "foo"), "foo"),
        ):
            with self.subTest(names=names, transferred=transferred):
                store = GrantStore()
                for name in names:
                    store.reserve(name, "owner-a")
                with self.assertRaises(OverlapError):
                    store.transfer(transferred, "owner-b")
                for name in names:
                    self.assertEqual(store.get(name).owner, "owner-a")
                for name in names:
                    store.transfer(name, "owner-a")
                    self.assertEqual(store.get(name).owner, "owner-a")

    def test_reserve_normalizes(self):
        self.require_impl()
        store = GrantStore()
        self.assertEqual(
            store.reserve("Acme.Widgets", "acme-corp").name, "acme-widgets"
        )
        for name in ("acme-widgets", "Acme.Widgets", "ACME_WIDGETS", "acme.widgets"):
            with self.subTest(name=name):
                self.assertIn(name, store)

    def test_reserve_rejects_empty_owner(self):
        self.require_impl()
        store = GrantStore()
        for owner in ("", None, 123):
            with self.subTest(owner=owner):
                with self.assertRaises(ValueError):
                    store.reserve("acme", owner)

    def test_reserve_rejects_invalid(self):
        self.require_impl()
        store = GrantStore()
        for name in ("", "-foo", "foo-", "foo!", "foo bar", "foo\n"):
            with self.subTest(name=name):
                with self.assertRaises(InvalidNamespaceError):
                    store.reserve(name, "owner-a")

    def test_default_depth_limit_is_three(self):
        self.require_impl()
        self.assertEqual(DEFAULT_DEPTH_LIMIT, 3)
        store = GrantStore()
        self.assertEqual(store.depth_limit, 3)
        self.assertEqual(store.reserve("a-b-c-d", "owner-a").name, "a-b-c-d")
        with self.assertRaises(DepthLimitError):
            store.reserve("a-b-c-d-e", "owner-a")
        unlimited = GrantStore(depth_limit=None)
        self.assertEqual(
            unlimited.reserve("a-b-c-d-e-f", "owner-a").name, "a-b-c-d-e-f"
        )

    def test_depth_limit_enforced(self):
        self.require_impl()
        store = GrantStore(depth_limit=1)
        self.assertEqual(store.reserve("foo-bar", "owner-a").name, "foo-bar")
        with self.assertRaises(DepthLimitError):
            store.reserve("foo-bar-baz", "owner-a")

    def test_grants_overlap_both_directions(self):
        self.require_impl()
        for left, right in (
            ("foo", "foo-bar"),
            ("foo-bar", "foo"),
            ("foo", "foo"),
            ("Foo", "foo-bar"),
        ):
            with self.subTest(left=left, right=right):
                self.assertTrue(grants_overlap(left, right))
        for left, right in (
            ("foo", "foobar"),
            ("foobar", "foo"),
            ("foo", "bar"),
            ("bar", "foo"),
        ):
            with self.subTest(left=left, right=right):
                self.assertFalse(grants_overlap(left, right))

    def test_overlap_hyphen_boundary_not_overlapping(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        store.reserve("foobar", "owner-b")
        self.assertEqual(store.get("foo").owner, "owner-a")
        self.assertEqual(store.get("foobar").owner, "owner-b")

    def test_overlap_exact_duplicate_rejected(self):
        self.require_impl()
        store = GrantStore()
        grant = store.reserve("foo", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo", "owner-b")
        self.assertEqual(store.reserve("foo", "owner-a"), grant)
        self.assertEqual(len(store), 1)

    def test_overlap_longer_under_shorter_rejected(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo-bar", "owner-b")

    def test_overlap_shorter_over_longer_rejected(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo-bar", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo", "owner-b")

    def test_overlap_same_owner_nesting_allowed(self):
        self.require_impl()
        names = ("foo", "foo-bar", "foo-bar-baz")
        store = GrantStore()
        for name in names:
            store.reserve(name, "owner-a")
        self.assertEqual(len(store), 3)
        for name in names:
            self.assertEqual(store.get(name).owner, "owner-a")
        reverse_store = GrantStore()
        for name in reversed(names):
            reverse_store.reserve(name, "owner-a")
        self.assertEqual(len(reverse_store), 3)
        for name in names:
            self.assertEqual(reverse_store.get(name).owner, "owner-a")

    def test_matching_returns_sorted_grants(self):
        self.require_impl()
        store = GrantStore()
        for name in ("acme-widgets", "acme", "other"):
            store.reserve(name, "acme-corp")
        self.assertEqual(
            [grant.name for grant in store.matching("acme-widgets-sprocket")],
            ["acme", "acme-widgets"],
        )
        self.assertEqual(store.matching("unrelated"), [])

    def test_namespaces_sorted(self):
        self.require_impl()
        store = GrantStore()
        for name in ("zeta", "mid-way", "acme"):
            store.reserve(name, "owner-a")
        self.assertEqual(store.namespaces(), ["acme", "mid-way", "zeta"])

    def test_children_direct_only(self):
        self.require_impl()
        store = GrantStore()
        for name in ("foo", "foo-bar", "foo-bar-baz", "foo-qux"):
            store.reserve(name, "owner-a")
        self.assertEqual(store.children("foo"), ["foo-bar", "foo-qux"])
        self.assertEqual(store.children("foo-bar"), ["foo-bar-baz"])
        self.assertEqual(store.children("foo-bar-baz"), [])

    def test_children_sparse_chain_skips_gap(self):
        self.require_impl()
        store = GrantStore()
        for name in ("foo", "foo-bar-baz"):
            store.reserve(name, "owner-a")
        self.assertEqual(store.children("foo"), [])
        self.assertEqual(store.children("foo-bar-baz"), [])

    def test_parent_without_grant_is_none(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo-bar-baz", "owner-a")
        self.assertIsNone(store.parent("foo-bar-baz"))
        self.assertIsNone(store.parent("foo"))

    def test_parent_sparse_chain_is_none(self):
        self.require_impl()
        store = GrantStore()
        for name in ("foo", "foo-bar-baz"):
            store.reserve(name, "owner-a")
        self.assertIsNone(store.parent("foo-bar-baz"))
        self.assertIsNone(store.parent("foo"))

    def test_parent_with_grant(self):
        self.require_impl()
        store = GrantStore()
        for name in ("foo", "foo-bar", "foo-bar-baz"):
            store.reserve(name, "owner-a")
        self.assertEqual(store.parent("foo-bar"), "foo")
        self.assertEqual(store.parent("foo-bar-baz"), "foo-bar")


if __name__ == "__main__":
    unittest.main()
