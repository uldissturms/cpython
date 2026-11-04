"""Conformance tests for the PEP 752 CLI, shell harness and docs."""

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
except Exception as exc:  # ImportError at base; anything else is a broken tree
    main = None
    CONFLICT_EXIT = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


def repo_root():
    here = os.path.abspath(__file__)
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


class CliTests(unittest.TestCase):
    def require_impl(self):
        if _IMPORT_ERROR is not None:
            self.fail(f"packagenamespaces is not importable: {_IMPORT_ERROR}")

    def run_cli(self, store, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = main(["--store", store, *argv])
        return status, out.getvalue()

    def test_cli_reserve_and_list(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            status, out = self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            self.assertEqual(status, 0)
            self.assertEqual(out, "reserved acme for acme-corp\n")
            status, out = self.run_cli(store, "list")
            self.assertEqual(status, 0)
            self.assertEqual(out, "acme acme-corp\n")
            status, out = self.run_cli(store, "list", "--json")
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(out), [{"name": "acme", "owner": "acme-corp"}]
            )

    def test_cli_reserve_overlap_fails(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                status, _ = self.run_cli(
                    store, "reserve", "acme-evil", "--owner", "mallory"
                )
            self.assertEqual(status, 1)
            self.assertIn("overlap", err.getvalue().lower())

    def test_cli_show(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            self.run_cli(store, "reserve", "acme-widgets", "--owner", "acme-corp")
            status, out = self.run_cli(store, "show", "acme")
            self.assertEqual(status, 0)
            self.assertEqual(
                out,
                "name: acme\nowner: acme-corp\nparent: none\n"
                "children: acme-widgets\n",
            )
            status, out = self.run_cli(store, "show", "acme", "--json")
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(out),
                {
                    "name": "acme",
                    "owner": "acme-corp",
                    "parent": None,
                    "children": ["acme-widgets"],
                },
            )

    def test_cli_show_unknown_fails(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                status, _ = self.run_cli(store, "show", "nope")
            self.assertEqual(status, 1)
            self.assertIn("unknown", err.getvalue().lower())

    def test_cli_remove(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            status, out = self.run_cli(store, "remove", "acme")
            self.assertEqual(status, 0)
            self.assertEqual(out, "removed acme\n")
            status, out = self.run_cli(store, "list")
            self.assertEqual(status, 0)
            self.assertEqual(out, "")

    def test_cli_register_and_grandfather(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            status, out = self.run_cli(
                store, "register", "acme-new", "--owner", "acme-corp"
            )
            self.assertEqual(status, 0)
            self.assertEqual(out, "registered acme-new for acme-corp\n")
            status, out = self.run_cli(
                store, "grandfather", "acme-legacy", "--owner", "mallory"
            )
            self.assertEqual(status, 0)
            self.assertEqual(out, "grandfathered acme-legacy\n")

    def test_cli_check_upload_allowed(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            status, out = self.run_cli(
                store, "check-upload", "acme-new", "--owner", "acme-corp"
            )
            self.assertEqual(status, 0)
            self.assertEqual(out, "OK acme-new\n")

    def test_cli_check_upload_denied(self):
        self.require_impl()
        self.assertEqual(CONFLICT_EXIT, 3)
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                status, _ = self.run_cli(
                    store, "check-upload", "acme-evil", "--owner", "mallory"
                )
            self.assertEqual(status, 3)
            self.assertIn("409", err.getvalue())
            self.assertIn("Conflict", err.getvalue())

    def test_cli_check_upload_grandfathered_allowed(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            self.run_cli(store, "grandfather", "acme-legacy", "--owner", "mallory")
            status, out = self.run_cli(
                store, "check-upload", "acme-legacy", "--owner", "mallory"
            )
            self.assertEqual(status, 0)
            self.assertEqual(out, "OK acme-legacy\n")

    def test_cli_dump(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            status, out = self.run_cli(store, "dump")
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(out),
                {"api_version": "1.5", "namespaces": [{"name": "acme"}]},
            )

    def test_cli_dump_project(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            self.run_cli(store, "reserve", "acme", "--owner", "acme-corp")
            self.run_cli(store, "register", "acme-new", "--owner", "acme-corp")
            status, out = self.run_cli(store, "dump", "--project", "acme-new")
            self.assertEqual(status, 0)
            self.assertEqual(
                json.loads(out),
                {
                    "name": "acme-new",
                    "namespaces": [{"name": "acme", "owned": True}],
                },
            )

    def test_cli_corrupt_store_fails(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            with open(store, "w", encoding="utf-8") as handle:
                handle.write("{not valid json")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                status, _ = self.run_cli(store, "list")
            self.assertEqual(status, 1)
            self.assertIn("error", err.getvalue().lower())

    def test_cli_register_rejects_empty_owner(self):
        self.require_impl()
        with tempfile.TemporaryDirectory() as tmp:
            store = os.path.join(tmp, "store.json")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                status, _ = self.run_cli(
                    store, "register", "acme-new", "--owner", ""
                )
            self.assertEqual(status, 1)
            self.assertIn("error", err.getvalue().lower())

    def test_cli_module_entrypoint(self):
        proc = subprocess.run(
            [sys.executable, "-m", "packagenamespaces", "--help"],
            capture_output=True,
            text=True,
            cwd=repo_root(),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage", proc.stdout.lower())


class HarnessTests(unittest.TestCase):
    def scripts(self):
        root = repo_root()
        return (
            os.path.join(root, "Tools", "packagenamespaces", "gen_fixtures.sh"),
            os.path.join(root, "Tools", "packagenamespaces", "verify_offline.sh"),
        )

    def test_gen_fixtures_writes_indexes(self):
        gen, _verify = self.scripts()
        with tempfile.TemporaryDirectory() as tmp:
            outdir = os.path.join(tmp, "fixtures")
            proc = subprocess.run(
                ["bash", gen, outdir], capture_output=True, text=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            for name in (
                "grants.json",
                "projects.json",
                "grandfathered.json",
                "second-index.json",
            ):
                path = os.path.join(outdir, name)
                self.assertTrue(os.path.isfile(path), name)
                with open(path, encoding="utf-8") as handle:
                    payload = json.load(handle)
                self.assertIsInstance(payload, dict)
            with open(os.path.join(outdir, "grants.json"), encoding="utf-8") as handle:
                grants = json.load(handle)["grants"]
            self.assertGreaterEqual(len(grants), 2)
            self.assertTrue(all("name" in g and "owner" in g for g in grants))

    def test_verify_offline_passes(self):
        gen, verify = self.scripts()
        with tempfile.TemporaryDirectory() as tmp:
            outdir = os.path.join(tmp, "fixtures")
            proc = subprocess.run(
                ["bash", gen, outdir], capture_output=True, text=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            proc = subprocess.run(
                ["bash", verify, outdir], capture_output=True, text=True
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("verify: all checks passed", proc.stdout)


class DocsTests(unittest.TestCase):
    def test_library_page_documents_module(self):
        page = os.path.join(repo_root(), "Doc", "library", "packagenamespaces.rst")
        self.assertTrue(os.path.isfile(page))
        with open(page, encoding="utf-8") as handle:
            text = handle.read()
        for marker in ("packagenamespaces", "PEP 752", "namespaces",
                       "SecurityPolicy", "RepositoryIndex"):
            self.assertIn(marker, text)

    def test_whatsnew_announces_module(self):
        page = os.path.join(repo_root(), "Doc", "whatsnew", "3.16.rst")
        with open(page, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("packagenamespaces", text)
        self.assertIn("752", text)

    def test_news_entry_exists(self):
        pattern = os.path.join(
            repo_root(), "Misc", "NEWS.d", "next", "Library", "*.rst"
        )
        hits = []
        for path in glob.glob(pattern):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            if "packagenamespaces" in text and "752" in text:
                hits.append(path)
        self.assertTrue(hits, "no NEWS entry mentions packagenamespaces + 752")


if __name__ == "__main__":
    unittest.main()
