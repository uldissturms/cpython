import unittest

try:
    from packagenamespaces import GrantStore
    from packagenamespaces.uploads import (
        CONFLICT_STATUS,
        GrandfatheredRegistry,
        UploadConflictError,
        authorize_upload,
    )
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class UploadTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot import the upload API: {_IMPORT_ERROR!r}")

    def make_store(self):
        store = GrantStore()
        store.reserve("acme", "acme-corp")
        return store

    def test_conflict_status_constant(self):
        self.require_impl()
        self.assertEqual(CONFLICT_STATUS, 409)
        self.assertEqual(UploadConflictError.status_code, 409)

    def test_grandfathered_registry_tracks_projects(self):
        self.require_impl()
        registry = GrandfatheredRegistry()
        registry.add("Acme.Legacy")
        self.assertTrue(registry.covers("acme-legacy"))
        self.assertIn("acme-legacy", registry)
        self.assertEqual(registry.projects(), ["acme-legacy"])
        self.assertEqual(len(registry), 1)

        registry.discard("acme-legacy")
        self.assertFalse(registry.covers("acme-legacy"))

    def test_owner_upload_allowed(self):
        self.require_impl()
        store = self.make_store()
        for project in ("acme-new", "acme"):
            with self.subTest(project=project):
                self.assertIs(
                    authorize_upload(project, "acme-corp", store), True
                )

    def test_unreserved_upload_allowed(self):
        self.require_impl()
        self.assertIs(
            authorize_upload("requests", "anyone", self.make_store()), True
        )

    def test_hyphen_boundary_not_gated(self):
        self.require_impl()
        self.assertIs(
            authorize_upload("acmewidget", "mallory", self.make_store()),
            True,
        )

    def test_stranger_upload_conflicts(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError) as caught:
            authorize_upload("acme-evil", "mallory", store)
        self.assertEqual(caught.exception.status_code, 409)
        self.assertEqual(caught.exception.project, "acme-evil")
        self.assertEqual(caught.exception.namespace, "acme")
        self.assertEqual(caught.exception.owner, "mallory")

    def test_exact_namespace_project_gated(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError):
            authorize_upload("acme", "mallory", store)

    def test_normalization_applied_before_check(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError):
            authorize_upload("Acme.Evil", "mallory", store)
        self.assertIs(
            authorize_upload("Acme.Evil", "acme-corp", store), True
        )

    def test_grandfathered_stranger_allowed(self):
        self.require_impl()
        store = self.make_store()
        registry = GrandfatheredRegistry()
        registry.add("acme-legacy")
        self.assertIs(
            authorize_upload(
                "acme-legacy", "mallory", store, grandfathered=registry
            ),
            True,
        )

    def test_nongrandfathered_stranger_denied(self):
        self.require_impl()
        store = self.make_store()
        registry = GrandfatheredRegistry()
        registry.add("acme-legacy")
        with self.assertRaises(UploadConflictError):
            authorize_upload(
                "acme-other", "mallory", store, grandfathered=registry
            )


if __name__ == "__main__":
    unittest.main()
