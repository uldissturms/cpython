"""Conformance tests for PEP 752 installer security policies."""

import unittest

try:
    from packagenamespaces.grants import GrantStore, InvalidNamespaceError
    from packagenamespaces.metadata import RepositoryIndex
    from packagenamespaces.policy import SecurityPolicy
except Exception as exc:  # ImportError at base; anything else is a broken tree
    GrantStore = InvalidNamespaceError = RepositoryIndex = None
    SecurityPolicy = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class PolicyTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def make_index(self):
        store = GrantStore()
        store.reserve("acme", "acme-corp")
        index = RepositoryIndex(store)
        index.register_project("acme-widget", "acme-corp")
        index.register_project("acme-legacy", "mallory")
        index.register_project("requests", "psf")
        return index

    def test_allows_granted_owner_dependency(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertTrue(policy.allows("acme-widget", self.make_index()))

    def test_allows_with_multiple_namespaces(self):
        self.require_impl()
        policy = SecurityPolicy(["other", "acme"], "acme-corp")
        self.assertTrue(policy.allows("acme-widget", self.make_index()))
        policy = SecurityPolicy(["other", "ungranted"], "acme-corp")
        self.assertFalse(policy.allows("acme-widget", self.make_index()))

    def test_denies_ungranted_namespace(self):
        self.require_impl()
        policy = SecurityPolicy(["other"], "acme-corp")
        self.assertFalse(policy.allows("other-thing", self.make_index()))
        # Allowed namespace matches but no grant exists for it.
        policy = SecurityPolicy(["acme-widget"], "acme-corp")
        index = self.make_index()
        index.register_project("acme-widget-part", "acme-corp")
        self.assertFalse(policy.allows("acme-widget-part", index))

    def test_denies_wrong_owner(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "someone-else")
        self.assertFalse(policy.allows("acme-widget", self.make_index()))

    def test_denies_grandfathered_foreign_project(self):
        self.require_impl()
        index = self.make_index()
        index.grandfathered.add("acme-legacy")
        policy = SecurityPolicy(["acme"], "acme-corp")
        # Still owned by mallory: no active grant for the installer.
        self.assertFalse(policy.allows("acme-legacy", index))

    def test_denies_unknown_project(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertFalse(policy.allows("acme-unregistered", self.make_index()))

    def test_evaluate_reports_each_requirement(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        verdicts = policy.evaluate(
            ["acme-widget", "acme-legacy", "requests"], self.make_index()
        )
        self.assertEqual(
            verdicts,
            {"acme-widget": True, "acme-legacy": False, "requests": False},
        )

    def test_evaluate_empty_requirements(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertEqual(policy.evaluate([], self.make_index()), {})

    def test_evaluate_normalizes_names(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        verdicts = policy.evaluate(["Acme.Widget"], self.make_index())
        self.assertEqual(verdicts, {"acme-widget": True})

    def test_grant_not_shared_between_repositories(self):
        self.require_impl()
        policy = SecurityPolicy(["acme"], "acme-corp")
        mirror = RepositoryIndex(GrantStore())
        mirror.register_project("acme-widget", "acme-corp")
        self.assertFalse(policy.allows("acme-widget", mirror))
        self.assertTrue(policy.allows("acme-widget", self.make_index()))

    def test_policy_validates_namespaces(self):
        self.require_impl()
        with self.assertRaises(InvalidNamespaceError):
            SecurityPolicy(["-bad"], "acme-corp")
        policy = SecurityPolicy(["Acme.Widgets"], "acme-corp")
        self.assertEqual(policy.namespaces, ("acme-widgets",))
        self.assertEqual(policy.owner, "acme-corp")

    def test_policy_validates_owner(self):
        self.require_impl()
        for bad in ("", None, 123):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    SecurityPolicy(["acme"], bad)


if __name__ == "__main__":
    unittest.main()
