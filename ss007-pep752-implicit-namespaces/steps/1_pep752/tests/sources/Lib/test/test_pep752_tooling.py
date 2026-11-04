import contextlib
import glob
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

try:
    from packagenamespaces.cli import CONFLICT_EXIT, main
except Exception as exc:
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


class CliTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = os.path.join(directory.name, "store.json")

    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"Cannot import the CLI: {_IMPORT_ERROR!r}")

    def invoke(self, *arguments):
        self.require_impl()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = main(["--store", self.store, *arguments])
        return status, stdout.getvalue(), stderr.getvalue()

    def reserve_acme(self):
        status, _, error = self.invoke("reserve", "acme", "--owner", "acme-corp")
        self.assertEqual(status, 0, error)

    def test_cli_module_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "-m", "packagenamespaces", "--help"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage", result.stdout.lower())

    def test_cli_corrupt_store_fails(self):
        self.require_impl()
        with open(self.store, "w", encoding="utf-8") as stream:
            stream.write("{not valid json")
        status, _, error = self.invoke("list")
        self.assertEqual(status, 1)
        self.assertIn("error", error.lower())
        for document in (
            {"grants": {"acme": 123}},
            {"grants": {"acme": None}},
            {"grants": {"acme": ""}},
            {"projects": {"acme-new": 123}},
            {"grandfathered": [123]},
            {"grants": {"bad name!": "acme-corp"}},
        ):
            with self.subTest(document=document):
                with open(self.store, "w", encoding="utf-8") as stream:
                    json.dump(document, stream)
                status, _, error = self.invoke("list")
                self.assertEqual(status, 1)
                self.assertIn("error", error.lower())

    def test_cli_reserve_and_list(self):
        self.require_impl()
        status, output, error = self.invoke(
            "reserve", "acme", "--owner", "acme-corp",
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "reserved acme for acme-corp")
        status, output, error = self.invoke("list")
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "acme acme-corp")
        status, output, error = self.invoke("list", "--json")
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), [{"name": "acme", "owner": "acme-corp"}])

    def test_cli_show_unknown_fails(self):
        self.require_impl()
        status, _, error = self.invoke("show", "acme")
        self.assertEqual(status, 1)
        self.assertIn("unknown grant", error.lower())

    def test_cli_show(self):
        self.require_impl()
        self.reserve_acme()
        status, _, error = self.invoke(
            "reserve", "acme-widgets", "--owner", "acme-corp",
        )
        self.assertEqual(status, 0, error)
        status, output, error = self.invoke("show", "acme")
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip().splitlines(), [
            "name: acme",
            "owner: acme-corp",
            "parent: none",
            "children: acme-widgets",
        ])
        status, output, error = self.invoke("show", "acme", "--json")
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), {
            "children": ["acme-widgets"],
            "parent": None,
            "owner": "acme-corp",
            "name": "acme",
        })

    def test_cli_reserve_overlap_fails(self):
        self.require_impl()
        self.reserve_acme()
        status, _, error = self.invoke(
            "reserve", "acme-evil", "--owner", "mallory",
        )
        self.assertEqual(status, 1)
        self.assertIn("overlaps the grant", error.lower())

    def test_cli_remove(self):
        self.require_impl()
        self.reserve_acme()
        status, output, error = self.invoke("remove", "acme")
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "removed acme")
        status, output, error = self.invoke("list")
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "")

    def test_cli_register_rejects_empty_owner(self):
        self.require_impl()
        status, _, error = self.invoke("register", "acme-new", "--owner", "")
        self.assertEqual(status, 1)
        self.assertIn("error", error.lower())

    def test_cli_register_and_grandfather(self):
        self.require_impl()
        status, output, error = self.invoke(
            "register", "acme-new", "--owner", "acme-corp",
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "registered acme-new for acme-corp")
        status, output, error = self.invoke(
            "grandfather", "acme-legacy", "--owner", "mallory",
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "grandfathered acme-legacy")

    def test_cli_dump_project(self):
        self.require_impl()
        self.reserve_acme()
        status, _, error = self.invoke(
            "register", "acme-new", "--owner", "acme-corp",
        )
        self.assertEqual(status, 0, error)
        status, output, error = self.invoke("dump", "--project", "acme-new")
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), {
            "namespaces": [{"owned": True, "name": "acme"}],
            "name": "acme-new",
        })

    def test_cli_dump(self):
        self.require_impl()
        self.reserve_acme()
        status, output, error = self.invoke("dump")
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), {
            "namespaces": [{"name": "acme"}],
            "api_version": "1.5",
        })

    def test_cli_check_upload_grandfathered_allowed(self):
        self.require_impl()
        self.reserve_acme()
        status, _, error = self.invoke(
            "grandfather", "acme-legacy", "--owner", "mallory",
        )
        self.assertEqual(status, 0, error)
        status, output, error = self.invoke(
            "check-upload", "acme-legacy", "--owner", "mallory",
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "OK acme-legacy")

    def test_cli_check_upload_denied(self):
        self.require_impl()
        self.assertEqual(CONFLICT_EXIT, 3)
        self.reserve_acme()
        status, _, error = self.invoke(
            "check-upload", "acme-new", "--owner", "mallory",
        )
        self.assertEqual(status, 3)
        self.assertIn("409", error)
        self.assertIn("Conflict", error)

    def test_cli_check_upload_allowed(self):
        self.require_impl()
        self.reserve_acme()
        status, output, error = self.invoke(
            "check-upload", "acme-new", "--owner", "acme-corp",
        )
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip(), "OK acme-new")


class HarnessTests(unittest.TestCase):
    def run_script(self, script, directory, *, env=None):
        result = subprocess.run(
            ["bash", os.path.join(REPO_ROOT, "Tools", "packagenamespaces", script),
             directory],
            cwd=REPO_ROOT, capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_verify_offline_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_script("gen_fixtures.sh", directory)
            result = self.run_script("verify_offline.sh", directory)
        self.assertIn("verify: all checks passed", result.stdout)

    def test_gen_fixtures_writes_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            self.run_script("gen_fixtures.sh", directory)
            documents = {}
            for filename in (
                "projects.json", "second-index.json", "grants.json", "grandfathered.json",
            ):
                with self.subTest(filename=filename):
                    path = os.path.join(directory, filename)
                    self.assertTrue(os.path.isfile(path), filename)
                    with open(path, encoding="utf-8") as stream:
                        document = json.load(stream)
                    self.assertIsInstance(document, dict)
                    documents[filename] = document

            grants = documents["grants.json"]["grants"]
            self.assertIsInstance(grants, list)
            self.assertGreaterEqual(len(grants), 2)
            for grant in grants:
                self.assertIsInstance(grant, dict)
                self.assertIsInstance(grant["owner"], str)
                self.assertIsInstance(grant["name"], str)
            projects = documents["projects.json"]["projects"]
            self.assertIsInstance(projects, dict)
            for project, owner in projects.items():
                self.assertIsInstance(project, str)
                self.assertIsInstance(owner, str)
            self.assertIsInstance(documents["grandfathered.json"]["grandfathered"], list)
            self.assertIsInstance(documents["second-index.json"]["projects"], dict)
            self.assertIsInstance(documents["second-index.json"]["grants"], list)

    def test_verify_offline_rejects_missing_fixtures(self):
        script = os.path.join(REPO_ROOT, "Tools", "packagenamespaces",
                              "verify_offline.sh")
        self.assertTrue(os.path.isfile(script))
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                ["bash", script, directory], cwd=REPO_ROOT,
                capture_output=True, text=True,
            )
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("verify: all checks passed", result.stdout)

    def test_verify_offline_rejects_damaged_fixtures(self):
        tools = os.path.join(REPO_ROOT, "Tools", "packagenamespaces")
        verifier = os.path.join(tools, "verify_offline.sh")
        self.assertTrue(os.path.isfile(verifier))
        self.assertTrue(os.path.isfile(os.path.join(tools, "gen_fixtures.sh")))
        for filename, replacement in (
            ("projects.json", "{}"),
            ("grants.json", "{not valid json"),
        ):
            with self.subTest(filename=filename):
                with tempfile.TemporaryDirectory() as directory:
                    self.run_script("gen_fixtures.sh", directory)
                    with open(os.path.join(directory, filename), "w",
                              encoding="utf-8") as stream:
                        stream.write(replacement)
                    result = subprocess.run(
                        ["bash", verifier, directory], cwd=REPO_ROOT,
                        capture_output=True, text=True,
                    )
                self.assertNotEqual(result.returncode, 0,
                                    result.stdout + result.stderr)
                self.assertNotIn("verify: all checks passed", result.stdout)


class DocsTests(unittest.TestCase):
    def test_news_entry_exists(self):
        pattern = os.path.join(REPO_ROOT, "Misc", "NEWS.d", "next", "Library", "*.rst")
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as stream:
                content = stream.read()
            if "752" in content and "packagenamespaces" in content:
                return
        self.fail("No library news entry mentions both packagenamespaces and 752")

    def test_whatsnew_announces_module(self):
        path = os.path.join(REPO_ROOT, "Doc", "whatsnew", "3.16.rst")
        with open(path, encoding="utf-8") as stream:
            content = stream.read()
        for term in ("752", "packagenamespaces"):
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_library_page_documents_module(self):
        path = os.path.join(REPO_ROOT, "Doc", "library", "packagenamespaces.rst")
        self.assertTrue(os.path.isfile(path))
        with open(path, encoding="utf-8") as stream:
            content = stream.read()
        for term in (
            "RepositoryIndex", "SecurityPolicy", "namespaces",
            "packagenamespaces",
        ):
            with self.subTest(term=term):
                self.assertIn(term, content)
        self.assertTrue(
            "PEP 752" in content or (":pep:" in content and "752" in content),
            "The library page needs a reference to PEP 752",
        )

    def test_install_registers_package(self):
        path = os.path.join(REPO_ROOT, "Python", "stdlib_module_names.h")
        with open(path, encoding="utf-8") as stream:
            self.assertIn('"packagenamespaces"', stream.read())
        path = os.path.join(REPO_ROOT, "Makefile.pre.in")
        with open(path, encoding="utf-8") as stream:
            content = stream.read()
        self.assertRegex(
            content,
            r"(?m)^LIBSUBDIRS[ \t]*="
            r"(?:(?!^TESTSUBDIRS[ \t]*=)[\s\S])*?"
            r"\bpackagenamespaces\b"
            r"(?:(?!^TESTSUBDIRS[ \t]*=)[\s\S])*"
            r"^TESTSUBDIRS[ \t]*=",
        )


class InstallTests(unittest.TestCase):
    DESTDIR = "/tmp/lambo-destdir"

    @classmethod
    def setUpClass(cls):
        cls.repo_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        cls.python = os.path.join(cls.repo_root, "python")
        result = subprocess.run(
            [cls.python, "-c",
             "import sysconfig; print(sysconfig.get_path('stdlib'))"],
            cwd=cls.repo_root, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
        cls.stdlib = result.stdout.strip()
        cls.installed_stdlib = os.path.join(cls.DESTDIR, cls.stdlib.lstrip(os.sep))

    def test_stdlib_module_names_contains_package(self):
        result = subprocess.run(
            [self.python, "-c",
             "import sys; print('packagenamespaces' in sys.stdlib_module_names)"],
            cwd=self.repo_root, capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "True")

    def test_installed_tree_contains_package(self):
        path = os.path.join(self.installed_stdlib, "packagenamespaces", "__init__.py")
        self.assertTrue(os.path.isfile(path), path)


if __name__ == "__main__":
    unittest.main()
