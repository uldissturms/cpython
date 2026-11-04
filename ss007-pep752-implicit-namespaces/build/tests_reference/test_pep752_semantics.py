"""Conformance tests for PEP 752 semantics (matching and grants)."""

import unittest

try:
    from packagenamespaces.grants import (
        DEFAULT_DEPTH_LIMIT,
        DepthLimitError,
        GrantStore,
        InvalidNamespaceError,
        OverlapError,
        UnknownGrantError,
        grants_overlap,
    )
    from packagenamespaces.matching import namespace_matches
except Exception as exc:  # ImportError at base; anything else is a broken tree
    namespace_matches = None
    GrantStore = None
    DEFAULT_DEPTH_LIMIT = None
    DepthLimitError = InvalidNamespaceError = OverlapError = None
    UnknownGrantError = grants_overlap = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class MatchingTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def test_exact_match(self):
        self.require_impl()
        self.assertTrue(namespace_matches("foo", "foo"))
        self.assertTrue(namespace_matches("acme-widgets", "acme-widgets"))

    def test_prefix_hyphen_match(self):
        self.require_impl()
        self.assertTrue(namespace_matches("foo", "foo-bar"))
        self.assertTrue(namespace_matches("acme", "acme-widgets-sprocket"))

    def test_missing_hyphen_does_not_match(self):
        self.require_impl()
        self.assertFalse(namespace_matches("foo", "foobar"))
        self.assertFalse(namespace_matches("acme", "acmewidget"))

    def test_match_normalizes_inputs(self):
        self.require_impl()
        self.assertTrue(namespace_matches("Foo", "foo-bar"))
        self.assertTrue(namespace_matches("foo.bar", "foo-bar-baz"))
        self.assertTrue(namespace_matches("foo_bar", "FOO-BAR"))

    def test_unrelated_does_not_match(self):
        self.require_impl()
        self.assertFalse(namespace_matches("foo", "bar"))
        self.assertFalse(namespace_matches("foo", "bar-foo"))
        self.assertFalse(namespace_matches("foo-bar", "foo"))


class GrantStoreTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def test_reserve_and_get(self):
        self.require_impl()
        store = GrantStore()
        grant = store.reserve("acme", "acme-corp")
        self.assertEqual(grant.name, "acme")
        self.assertEqual(grant.owner, "acme-corp")
        self.assertEqual(store.get("acme"), grant)
        self.assertIn("acme", store)
        self.assertEqual(len(store), 1)
        self.assertIsNone(store.get("other"))

    def test_reserve_normalizes(self):
        self.require_impl()
        store = GrantStore()
        grant = store.reserve("Acme.Widgets", "acme-corp")
        self.assertEqual(grant.name, "acme-widgets")
        self.assertEqual(store.get("acme-widgets"), grant)

    def test_reserve_rejects_invalid(self):
        self.require_impl()
        store = GrantStore()
        for bad in ("", "-foo", "foo-", "foo!", "foo bar", "foo\n"):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidNamespaceError):
                    store.reserve(bad, "someone")

    def test_reserve_rejects_empty_owner(self):
        self.require_impl()
        store = GrantStore()
        for bad in ("", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    store.reserve("acme", bad)

    def test_depth_limit_enforced(self):
        self.require_impl()
        store = GrantStore(depth_limit=1)
        store.reserve("foo-bar", "owner")
        with self.assertRaises(DepthLimitError):
            store.reserve("foo-bar-baz", "owner")

    def test_default_depth_limit_is_three(self):
        self.require_impl()
        self.assertEqual(DEFAULT_DEPTH_LIMIT, 3)
        store = GrantStore()
        self.assertEqual(store.depth_limit, 3)
        store.reserve("a-b-c-d", "owner")
        with self.assertRaises(DepthLimitError):
            store.reserve("a-b-c-d-e", "owner")
        unlimited = GrantStore(depth_limit=None)
        unlimited.reserve("a-b-c-d-e-f", "owner")

    def test_overlap_shorter_over_longer_rejected(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo-bar", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo", "owner-b")

    def test_overlap_longer_under_shorter_rejected(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo-bar", "owner-b")

    def test_overlap_exact_duplicate_rejected(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        with self.assertRaises(OverlapError):
            store.reserve("foo", "owner-b")
        # Same owner re-reserving is idempotent.
        again = store.reserve("foo", "owner-a")
        self.assertEqual(again.owner, "owner-a")
        self.assertEqual(len(store), 1)

    def test_overlap_same_owner_nesting_allowed(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        store.reserve("foo-bar", "owner-a")
        store.reserve("foo-bar-baz", "owner-a")
        self.assertEqual(len(store), 3)
        other = GrantStore()
        other.reserve("foo-bar-baz", "owner-a")
        other.reserve("foo", "owner-a")
        self.assertEqual(len(other), 2)

    def test_overlap_hyphen_boundary_not_overlapping(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        store.reserve("foobar", "owner-b")
        self.assertEqual(len(store), 2)

    def test_grants_overlap_both_directions(self):
        self.require_impl()
        self.assertTrue(grants_overlap("foo", "foo-bar"))
        self.assertTrue(grants_overlap("foo-bar", "foo"))
        self.assertTrue(grants_overlap("foo", "foo"))
        self.assertTrue(grants_overlap("Foo", "foo-bar"))
        self.assertFalse(grants_overlap("foo", "foobar"))
        self.assertFalse(grants_overlap("foobar", "foo"))
        self.assertFalse(grants_overlap("foo", "bar"))

    def test_transfer(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        moved = store.transfer("foo", "owner-b")
        self.assertEqual(moved.owner, "owner-b")
        self.assertEqual(store.get("foo").owner, "owner-b")

    def test_transfer_unknown_raises(self):
        self.require_impl()
        store = GrantStore()
        with self.assertRaises(UnknownGrantError):
            store.transfer("foo", "owner-b")

    def test_transfer_conflicting_raises(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        store.reserve("foo-bar", "owner-a")
        with self.assertRaises(OverlapError):
            store.transfer("foo-bar", "owner-b")
        self.assertEqual(store.get("foo").owner, "owner-a")
        self.assertEqual(store.get("foo-bar").owner, "owner-a")
        other = GrantStore()
        other.reserve("foo-bar", "owner-a")
        other.reserve("foo", "owner-a")
        with self.assertRaises(OverlapError):
            other.transfer("foo", "owner-b")
        self.assertEqual(other.transfer("foo", "owner-a").owner, "owner-a")
        self.assertEqual(other.transfer("foo-bar", "owner-a").owner, "owner-a")

    def test_remove(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "owner-a")
        removed = store.remove("foo")
        self.assertEqual(removed.name, "foo")
        self.assertEqual(len(store), 0)
        self.assertIsNone(store.get("foo"))

    def test_remove_unknown_raises(self):
        self.require_impl()
        store = GrantStore()
        with self.assertRaises(UnknownGrantError):
            store.remove("foo")

    def test_namespaces_sorted(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("zeta", "a")
        store.reserve("acme", "a")
        store.reserve("mid-way", "a")
        self.assertEqual(store.namespaces(), ["acme", "mid-way", "zeta"])

    def test_parent_with_grant(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "a")
        store.reserve("foo-bar", "a")
        store.reserve("foo-bar-baz", "a")
        self.assertEqual(store.parent("foo-bar"), "foo")
        self.assertEqual(store.parent("foo-bar-baz"), "foo-bar")

    def test_parent_without_grant_is_none(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo-bar-baz", "a")
        self.assertIsNone(store.parent("foo-bar-baz"))
        self.assertIsNone(store.parent("foo"))

    def test_children_direct_only(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("foo", "a")
        store.reserve("foo-bar", "a")
        store.reserve("foo-bar-baz", "a")
        store.reserve("foo-qux", "a")
        self.assertEqual(store.children("foo"), ["foo-bar", "foo-qux"])
        self.assertEqual(store.children("foo-bar"), ["foo-bar-baz"])
        self.assertEqual(store.children("foo-bar-baz"), [])

    def test_matching_returns_sorted_grants(self):
        self.require_impl()
        store = GrantStore()
        store.reserve("acme-widgets", "a")
        store.reserve("acme", "a")
        store.reserve("other", "b")
        matches = store.matching("acme-widgets-sprocket")
        self.assertEqual([g.name for g in matches], ["acme", "acme-widgets"])
        self.assertEqual(store.matching("unrelated"), [])


if __name__ == "__main__":
    unittest.main()
