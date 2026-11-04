"""Conformance tests for PEP 752 uploads (packagenamespaces.uploads)."""

import unittest

try:
    from packagenamespaces.grants import GrantStore
    from packagenamespaces.uploads import (
        CONFLICT_STATUS,
        GrandfatheredRegistry,
        UploadConflictError,
        authorize_upload,
    )
except Exception as exc:  # ImportError at base; anything else is a broken tree
    GrantStore = GrandfatheredRegistry = UploadConflictError = None
    authorize_upload = CONFLICT_STATUS = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class UploadTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def make_store(self):
        store = GrantStore()
        store.reserve("acme", "acme-corp")
        return store

    def test_unreserved_upload_allowed(self):
        self.require_impl()
        store = self.make_store()
        self.assertTrue(authorize_upload("requests", "anyone", store))

    def test_owner_upload_allowed(self):
        self.require_impl()
        store = self.make_store()
        self.assertTrue(authorize_upload("acme-new", "acme-corp", store))
        self.assertTrue(authorize_upload("acme", "acme-corp", store))

    def test_stranger_upload_conflicts(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError) as caught:
            authorize_upload("acme-evil", "mallory", store)
        exc = caught.exception
        self.assertEqual(exc.status_code, 409)
        self.assertEqual(exc.project, "acme-evil")
        self.assertEqual(exc.namespace, "acme")
        self.assertEqual(exc.owner, "mallory")

    def test_conflict_status_constant(self):
        self.require_impl()
        self.assertEqual(CONFLICT_STATUS, 409)
        self.assertEqual(UploadConflictError.status_code, 409)

    def test_exact_namespace_project_gated(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError):
            authorize_upload("acme", "mallory", store)

    def test_hyphen_boundary_not_gated(self):
        self.require_impl()
        store = self.make_store()
        self.assertTrue(authorize_upload("acmewidget", "mallory", store))

    def test_grandfathered_stranger_allowed(self):
        self.require_impl()
        store = self.make_store()
        registry = GrandfatheredRegistry()
        registry.add("acme-legacy")
        self.assertTrue(
            authorize_upload("acme-legacy", "mallory", store,
                             grandfathered=registry)
        )

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

    def test_nongrandfathered_stranger_denied(self):
        self.require_impl()
        store = self.make_store()
        registry = GrandfatheredRegistry()
        registry.add("acme-legacy")
        with self.assertRaises(UploadConflictError):
            authorize_upload("acme-other", "mallory", store,
                             grandfathered=registry)

    def test_normalization_applied_before_check(self):
        self.require_impl()
        store = self.make_store()
        with self.assertRaises(UploadConflictError):
            authorize_upload("Acme.Evil", "mallory", store)
        self.assertTrue(authorize_upload("Acme.Evil", "acme-corp", store))


if __name__ == "__main__":
    unittest.main()
