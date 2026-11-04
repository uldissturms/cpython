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
        commands = {
            "reserve": ("namespace", "--owner"),
            "remove": ("namespace",),
            "register": ("project", "--owner"),
            "grandfather": ("project", "--owner"),
            "check-upload": ("project", "--owner"),
            "list": ("--json",),
            "dump": ("--project",),
            "show": ("namespace", "--json"),
        }
        for command, arguments in commands.items():
            with self.subTest(command=command):
                self.assertIn(command, result.stdout)
                help_result = subprocess.run(
                    [sys.executable, "-m", "packagenamespaces",
                     command, "--help"],
                    cwd=REPO_ROOT, capture_output=True, text=True,
                )
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                self.assertIn("usage", help_result.stdout.lower())
                self.assertIn(command, help_result.stdout)
                for argument in arguments:
                    self.assertIn(argument, help_result.stdout.lower())

    def test_cli_corrupt_store_fails(self):
        self.require_impl()
        with open(self.store, "w", encoding="utf-8") as stream:
            stream.write("{not valid json")
        status, _, error = self.invoke("list")
        self.assertEqual(status, 1)
        self.assertIn("error", error.lower())
        for document in (
            [], {"grants": []}, {"projects": []}, {"grandfathered": {}},
        ):
            with self.subTest(document=document):
                with open(self.store, "w", encoding="utf-8") as stream:
                    json.dump(document, stream)
                status, _, error = self.invoke("list")
                self.assertEqual(status, 1)
                self.assertIn("error", error.lower())
        os.remove(self.store)
        os.mkdir(self.store)
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
        for namespace, owner in (("zeta", "zeta-org"), ("beta", "beta-org")):
            status, _, error = self.invoke("reserve", namespace, "--owner", owner)
            self.assertEqual(status, 0, error)
        status, output, error = self.invoke("list")
        self.assertEqual(status, 0, error)
        self.assertEqual(output.strip().splitlines(), [
            "acme acme-corp", "beta beta-org", "zeta zeta-org",
        ])
        status, output, error = self.invoke("list", "--json")
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), [
            {"name": "acme", "owner": "acme-corp"},
            {"name": "beta", "owner": "beta-org"},
            {"name": "zeta", "owner": "zeta-org"},
        ])

    def test_cli_show_unknown_fails(self):
        self.require_impl()
        status, _, error = self.invoke("show", "acme")
        self.assertEqual(status, 1)
        self.assertIn("unknown", error.lower())

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
        self.assertIn("overlap", error.lower())

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
        self.reserve_acme()
        with open(self.store, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream), {
                "grants": {"acme": "acme-corp"},
                "projects": {"acme-new": "acme-corp", "acme-legacy": "mallory"},
                "grandfathered": ["acme-legacy"],
            })

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
            # The verifier image supplies a C compiler. Observe Internet socket
            # attempts in the shell and its children, even if a script ignores
            # the resulting error and otherwise reports success.
            library = os.path.join(directory, "offline.so")
            log = os.path.join(directory, "network.log")
            source = r"""
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <unistd.h>

int socket(int domain, int type, int protocol) {
    if (domain == AF_INET || domain == AF_INET6) {
        const char *log = getenv("PEP752_NETWORK_LOG");
        if (log != NULL) {
            int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0600);
            if (fd >= 0) {
                const char message[] = "Internet socket attempted\n";
                ssize_t written = write(fd, message, sizeof(message) - 1);
                (void)written;
                close(fd);
            }
        }
        errno = EPERM;
        return -1;
    }
    int (*original)(int, int, int) = dlsym(RTLD_NEXT, "socket");
    return original(domain, type, protocol);
}
"""
            compiled = subprocess.run(
                ["cc", "-shared", "-fPIC", "-x", "c", "-", "-o", library, "-ldl"],
                input=source, capture_output=True, text=True,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            env = os.environ.copy()
            env["LD_PRELOAD"] = library
            env["PEP752_NETWORK_LOG"] = log
            # Check that the observer is active before trusting an empty log.
            probe = subprocess.run(
                [sys.executable, "-c", "import socket; socket.socket()"],
                env=env, capture_output=True, text=True,
            )
            self.assertNotEqual(probe.returncode, 0)
            with open(log, encoding="utf-8") as stream:
                self.assertEqual(stream.read(), "Internet socket attempted\n")
            for script in ("gen_fixtures.sh", "verify_offline.sh"):
                with self.subTest(script=script):
                    with open(log, "w", encoding="utf-8"):
                        pass
                    result = self.run_script(script, directory, env=env)
                    with open(log, encoding="utf-8") as stream:
                        self.assertEqual(stream.read(), "", f"{script} used networking")
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

            def count_grants(value):
                if isinstance(value, dict):
                    count = int("name" in value and "owner" in value)
                    return count + sum(count_grants(item) for item in value.values())
                if isinstance(value, list):
                    return sum(count_grants(item) for item in value)
                return 0

            self.assertGreaterEqual(count_grants(documents["grants.json"]), 2)


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
            "RepositoryIndex", "SecurityPolicy", "namespaces", "PEP 752",
            "packagenamespaces",
        ):
            with self.subTest(term=term):
                self.assertIn(term, content)
        path = os.path.join(REPO_ROOT, "Doc", "library", "distribution.rst")
        with open(path, encoding="utf-8") as stream:
            content = stream.read()
        self.assertRegex(
            content,
            r"(?m)^\.\. toctree::[ \t]*\n"
            r"(?:[ \t]*\n|[ \t]+[^\n]*\n)*"
            r"[ \t]+packagenamespaces(?:\.rst)?[ \t]*(?:\n|$)",
        )


if __name__ == "__main__":
    unittest.main()
