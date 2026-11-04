"""Conformance tests for PEP 752 naming (packagenamespaces.normalize)."""

import unittest

try:
    from packagenamespaces.normalize import (
        hyphen_depth,
        is_valid_namespace,
        normalize_name,
    )
except Exception as exc:  # ImportError at base; anything else is a broken tree
    normalize_name = is_valid_namespace = hyphen_depth = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class NamingTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def test_normalize_lowercases_and_folds_separators(self):
        self.require_impl()
        self.assertEqual(normalize_name("Foo"), "foo")
        self.assertEqual(normalize_name("foo.bar"), "foo-bar")
        self.assertEqual(normalize_name("foo_bar"), "foo-bar")
        self.assertEqual(normalize_name("Foo.Bar_BAZ"), "foo-bar-baz")

    def test_normalize_collapses_separator_runs(self):
        self.require_impl()
        self.assertEqual(normalize_name("foo---bar"), "foo-bar")
        self.assertEqual(normalize_name("foo._-bar"), "foo-bar")
        self.assertEqual(normalize_name("foo...bar"), "foo-bar")
        self.assertEqual(normalize_name("foo___bar"), "foo-bar")

    def test_normalize_leaves_clean_names_alone(self):
        self.require_impl()
        self.assertEqual(normalize_name("foo"), "foo")
        self.assertEqual(normalize_name("foo-bar"), "foo-bar")
        self.assertEqual(normalize_name("acme-widgets-2"), "acme-widgets-2")

    def test_normalize_rejects_non_string(self):
        self.require_impl()
        for bad in (None, 123, b"foo", ["foo"]):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    normalize_name(bad)

    def test_valid_names_accepted(self):
        self.require_impl()
        for name in ("foo", "a", "A1", "foo-bar", "acme2", "X" * 64):
            with self.subTest(name=name):
                self.assertTrue(is_valid_namespace(name))

    def test_valid_names_with_separators(self):
        self.require_impl()
        for name in ("foo.bar", "foo_bar", "foo-bar", "a1.b2_c3-d4"):
            with self.subTest(name=name):
                self.assertTrue(is_valid_namespace(name))

    def test_invalid_names_rejected(self):
        self.require_impl()
        for name in (
            "",
            "-foo",
            "foo-",
            ".foo",
            "foo.",
            "_foo",
            "foo_",
            "-",
            ".",
            "foo!",
            "foo bar",
            "foo/bar",
            "foo@bar",
            "foo\n",
            "foo\nbar",
            "\tfoo",
        ):
            with self.subTest(name=name):
                self.assertFalse(is_valid_namespace(name))

    def test_invalid_names_reject_non_string(self):
        self.require_impl()
        for bad in (None, 123, b"foo", ["foo"]):
            with self.subTest(bad=bad):
                self.assertFalse(is_valid_namespace(bad))

    def test_hyphen_depth_counts(self):
        self.require_impl()
        self.assertEqual(hyphen_depth("foo"), 0)
        self.assertEqual(hyphen_depth("foo-bar"), 1)
        self.assertEqual(hyphen_depth("foo-bar-baz"), 2)
        self.assertEqual(hyphen_depth("Foo.bar_BAZ"), 2)


if __name__ == "__main__":
    unittest.main()
