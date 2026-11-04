import unittest

try:
    from packagenamespaces.grants import GrantStore, InvalidNamespaceError
    from packagenamespaces.metadata import RepositoryIndex
    from packagenamespaces.policy import SecurityPolicy
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class PolicyTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot exercise namespace policies: {_IMPORT_ERROR!r}")

    def make_index(self):
        store = GrantStore()
        store.reserve("acme", "acme-corp")
        index = RepositoryIndex(store)
        for project, owner in (
            ("acme-widget", "acme-corp"),
            ("acme-legacy", "mallory"),
            ("requests", "psf"),
        ):
            index.register_project(project, owner)
        return index

    def test_policy_validates_owner(self):
        self.require_impl()
        for owner in ("", None, 123):
            with self.subTest(owner=owner):
                with self.assertRaises(ValueError):
                    SecurityPolicy(["acme"], owner)

    def test_policy_validates_namespaces(self):
        self.require_impl()
        with self.assertRaises(InvalidNamespaceError):
            SecurityPolicy(["-bad"], "acme-corp")
        policy = SecurityPolicy(["Acme.Widgets"], "acme-corp")
        self.assertEqual(policy.namespaces, ("acme-widgets",))
        self.assertEqual(policy.owner, "acme-corp")

    def test_evaluate_empty_requirements(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertEqual(policy.evaluate([], index), {})

    def test_evaluate_normalizes_names(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertEqual(
            policy.evaluate(["Acme.Widget"], index),
            {"acme-widget": True},
        )

    def test_evaluate_reports_each_requirement(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "acme-corp")
        requirements = ["acme-widget", "acme-legacy", "requests"]
        self.assertEqual(
            policy.evaluate(requirements, index),
            {"acme-widget": True, "acme-legacy": False, "requests": False},
        )

    def test_grant_not_shared_between_repositories(self):
        self.require_impl()
        granted = self.make_index()
        mirror = RepositoryIndex(GrantStore())
        mirror.register_project("acme-widget", "acme-corp")
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertFalse(policy.allows("acme-widget", mirror))
        self.assertTrue(policy.allows("acme-widget", granted))

    def test_denies_unknown_project(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertFalse(policy.allows("acme-unregistered", index))

    def test_denies_grandfathered_foreign_project(self):
        self.require_impl()
        index = self.make_index()
        index.grandfathered.add("acme-legacy")
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertFalse(policy.allows("acme-legacy", index))

    def test_denies_wrong_owner(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "someone-else")
        self.assertFalse(policy.allows("acme-widget", index))

    def test_denies_ungranted_namespace(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["other"], "acme-corp")
        self.assertFalse(policy.allows("other-thing", index))
        index.register_project("acme-widget-part", "acme-corp")
        nested_policy = SecurityPolicy(["acme-widget"], "acme-corp")
        self.assertFalse(nested_policy.allows("acme-widget-part", index))

    def test_allows_with_multiple_namespaces(self):
        self.require_impl()
        index = self.make_index()
        policies = (
            (["other", "acme"], True),
            (["other", "ungranted"], False),
        )
        for namespaces, expected in policies:
            with self.subTest(namespaces=namespaces):
                policy = SecurityPolicy(namespaces, "acme-corp")
                self.assertIs(policy.allows("acme-widget", index), expected)

    def test_allows_granted_owner_dependency(self):
        self.require_impl()
        index = self.make_index()
        policy = SecurityPolicy(["acme"], "acme-corp")
        self.assertTrue(policy.allows("acme-widget", index))


if __name__ == "__main__":
    unittest.main()
