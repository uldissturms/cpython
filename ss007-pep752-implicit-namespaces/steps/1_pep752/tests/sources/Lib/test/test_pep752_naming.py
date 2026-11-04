import unittest

try:
    from packagenamespaces.normalize import (
        hyphen_depth,
        is_valid_namespace,
        normalize_name,
    )
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class NamingTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot import packagenamespaces.normalize: {_IMPORT_ERROR}")

    def test_valid_names_accepted(self):
        self.require_impl()
        for name in ("a", "acme2", "foo-bar", "A1", "X" * 64, "foo"):
            with self.subTest(name=name):
                self.assertIs(is_valid_namespace(name), True)

    def test_invalid_names_reject_non_string(self):
        self.require_impl()
        for value in (["foo"], b"foo", 123, None):
            with self.subTest(value=value):
                self.assertIs(is_valid_namespace(value), False)

    def test_valid_names_with_separators(self):
        self.require_impl()
        for name in ("a1.b2_c3-d4", "foo_bar", "foo-bar", "foo.bar"):
            with self.subTest(name=name):
                self.assertIs(is_valid_namespace(name), True)

    def test_invalid_names_rejected(self):
        self.require_impl()
        for name in (
            "foo/bar", "foo@bar", "foo bar", "foo!",
            "_foo", "foo_", ".foo", "foo.", "-foo", "foo-",
            ".", "-", "",
        ):
            with self.subTest(name=name):
                self.assertIs(is_valid_namespace(name), False)

    def test_normalize_leaves_clean_names_alone(self):
        self.require_impl()
        for name in ("acme-widgets-2", "foo-bar", "foo"):
            with self.subTest(name=name):
                self.assertEqual(normalize_name(name), name)

    def test_normalize_rejects_non_string(self):
        self.require_impl()
        for value in (123, ["foo"], None, b"foo"):
            with self.subTest(value=value):
                with self.assertRaises(TypeError):
                    normalize_name(value)

    def test_normalize_lowercases_and_folds_separators(self):
        self.require_impl()
        cases = (
            ("Foo.Bar_BAZ", "foo-bar-baz"),
            ("foo_bar", "foo-bar"),
            ("Foo", "foo"),
            ("foo.bar", "foo-bar"),
        )
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(normalize_name(name), expected)

    def test_hyphen_depth_counts(self):
        self.require_impl()
        cases = (
            ("Foo.bar_BAZ", 2),
            ("foo-bar", 1),
            ("foo", 0),
            ("foo-bar-baz", 2),
        )
        for name, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(hyphen_depth(name), expected)

    def test_normalize_collapses_separator_runs(self):
        self.require_impl()
        for name in ("foo___bar", "foo...bar", "foo._-bar", "foo---bar"):
            with self.subTest(name=name):
                self.assertEqual(normalize_name(name), "foo-bar")


if __name__ == "__main__":
    unittest.main()
