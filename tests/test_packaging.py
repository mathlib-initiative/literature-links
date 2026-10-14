"""Packaging: stdlib-only imports, entry points, version, and paths the docs cite."""
from __future__ import annotations

import ast
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
# Test the installed copy when there is one, else src/.
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(SRC))

import literature_links                                  # noqa: E402
from literature_links import cli                         # noqa: E402
from literature_links import companion as C              # noqa: E402

PACKAGE = Path(literature_links.__file__).resolve().parent
IMPORT_ROOT = PACKAGE.parent
EXAMPLES = ROOT / "examples" / "companion"
EXPECT_INSTALLED = os.environ.get("LITERATURE_LINKS_TEST_INSTALLED") == "1"


def subprocess_env() -> dict:
    """The environment for a child ``python3 -m``: it imports the copy under test."""
    path = os.pathsep.join(p for p in (str(IMPORT_ROOT), os.environ.get("PYTHONPATH", "")) if p)
    return dict(os.environ, PYTHONPATH=path, PYTHONDONTWRITEBYTECODE="1")


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class TestStandalone(unittest.TestCase):

    def test_the_package_imports_only_the_standard_library_and_itself(self):
        copies = {PACKAGE, (SRC / "literature_links").resolve()}
        modules = sorted(m for copy in copies for m in copy.glob("*.py"))
        self.assertGreaterEqual(len(modules), 6)
        for module in modules:
            tree = ast.parse(module.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue                                    # relative: this package
                    names = [node.module or ""]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    continue
                for name in names:
                    top = name.split(".")[0]
                    with self.subTest(module=module.name, imports=name):
                        self.assertTrue(top in sys.stdlib_module_names or top == "__future__",
                                        f"{module.name} imports {name}, which is not the standard library")

    def test_no_runtime_dependency_is_declared(self):
        self.assertEqual(pyproject()["project"]["dependencies"], [])

    def test_changelog_agrees_with_the_version(self):
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (\S+)", changelog, re.M)
        released = [h for h in headings if h != "Unreleased"]
        self.assertTrue(released)
        self.assertEqual(released[0], literature_links.__version__)
        self.assertLessEqual(headings.count("Unreleased"), 1)
        if "Unreleased" in headings:
            self.assertEqual(headings[0], "Unreleased")

    def test_the_schema_ships_as_package_data(self):
        setuptools = pyproject()["tool"]["setuptools"]
        data = setuptools["package-data"]["literature_links.schema"]
        self.assertIn("*.json", data)
        self.assertEqual(setuptools["package-dir"]["literature_links.schema"], "schema")
        self.assertTrue(C.SCHEMA_PATH.is_file())
        self.assertEqual(Path(C.__file__).resolve().parent, PACKAGE)
        self.assertEqual(C.SCHEMA_PATH.read_bytes(), (ROOT / "schema" / C.SCHEMA_PATH.name).read_bytes())
        if PACKAGE.is_relative_to(SRC.resolve()):
            self.assertEqual(C.SCHEMA_PATH.parent, ROOT / "schema")
        else:
            self.assertEqual(C.SCHEMA_PATH.parent, PACKAGE / "schema")
            self.assertNotEqual(C.SCHEMA_PATH.resolve().parent, (ROOT / "schema").resolve())

    def test_the_copy_under_test_is_the_installed_one_when_ci_says_so(self):
        if not EXPECT_INSTALLED:
            self.skipTest("LITERATURE_LINKS_TEST_INSTALLED is not set")
        self.assertFalse(PACKAGE.is_relative_to(SRC.resolve()), f"imported from the source tree: {PACKAGE}")
        self.assertNotIn(str(SRC), sys.path)
        self.assertIn("site-packages", PACKAGE.parts, PACKAGE)


class TestEntryPoints(unittest.TestCase):

    def run_module(self, module: str, *argv: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", module, *argv], capture_output=True, text=True,
                              env=env or subprocess_env(), cwd=ROOT, check=False)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = cli.main(list(argv))
            except SystemExit as exc:              # argparse: --version, --help and usage errors
                status = exc.code
        return status, out.getvalue(), err.getvalue()

    def test_usage_names_the_console_script(self):
        status, out, err = self.run_cli()
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("usage: literature-links "), err)
        self.assertNotIn("cli.py", err)
        status, out, err = self.run_cli("validate")
        self.assertEqual(status, 2)
        self.assertIn("literature-links validate: error: the following arguments are required: "
                      "documents", err)
        status, out, _ = self.run_cli("--help")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("usage: literature-links "), out)
        self.assertIn("--version", out)

    def test_version_prints_the_package_version(self):
        expected = f"literature-links {literature_links.__version__}\n"
        self.assertEqual(self.run_cli("--version"), (0, expected, ""))
        child = self.run_module("literature_links", "--version")
        self.assertEqual((child.returncode, child.stdout, child.stderr), (0, expected, ""))

    def test_every_example_is_valid(self):
        examples = sorted(EXAMPLES.glob("*.json"))
        self.assertTrue(examples)
        self.assertEqual(self.run_cli("validate", *map(str, examples))[0], 0)
        self.assertEqual(self.run_cli("scan", str(EXAMPLES))[0], 0)  # the folders too

    def test_the_readme_example_is_valid(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"(?ms)^```json\n(.*?)^```", readme)
        self.assertTrue(blocks)
        for block in blocks:
            with self.subTest(block=block[:40]):
                self.assertEqual(C.validate(C.loads(block)), [])

    def test_a_missing_current_schema_is_reported_without_a_traceback(self):
        good = EXAMPLES / "pdf.json"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp).resolve() / "literature_links"
            shutil.copytree(PACKAGE, broken, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.rmtree(broken / "schema", ignore_errors=True)
            env = dict(os.environ, PYTHONPATH=str(broken.parent), PYTHONDONTWRITEBYTECODE="1")
            child = self.run_module("literature_links", "validate", str(good), env=env)
            self.assertEqual(child.returncode, 2, child.stdout + child.stderr)
            self.assertIn("companion.schema.json", child.stderr)
            self.assertNotIn("Traceback", child.stdout + child.stderr)


REPO_ROOTS = ("src/", "schema/", "examples/", "docs/", "tests/", ".github/")
REPO_FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "pyproject.toml")
#: CHANGELOG.md is excluded: release notes may name paths that are gone.
DOCS = ("README.md", "CONTRIBUTING.md", "docs/companion.md")


class TestTheDocsCiteWhatIsHere(unittest.TestCase):

    def test_every_cited_repository_path_exists(self):
        for name in DOCS:
            text = (ROOT / name).read_text(encoding="utf-8")
            for span in re.findall(r"`([^`\n]+)`", text):
                for token in span.split():
                    token = token.strip(",;:()")
                    if not (token.startswith(REPO_ROOTS) or token in REPO_FILES):
                        continue
                    keep = []
                    for part in Path(token).parts:
                        if any(ch in part for ch in "<*"):
                            break
                        keep.append(part)
                    with self.subTest(doc=name, path=token):
                        self.assertTrue((ROOT / Path(*keep)).exists(), f"{name} cites {token}, which is not here")

    def test_no_em_dash_in_the_docs(self):
        for name in DOCS + ("CHANGELOG.md",):
            with self.subTest(doc=name):
                self.assertNotIn("—", (ROOT / name).read_text(encoding="utf-8"))

    def test_local_markdown_link_targets_exist(self):
        for name in DOCS + ("CHANGELOG.md",):
            document = ROOT / name
            text = document.read_text(encoding="utf-8")
            text = re.sub(r"(?ms)^```.*?^```[ \t]*$", "", text)
            # Check inline/image links and reference definitions without a
            # Markdown dependency or network access. Fragments stay local to
            # their target document; remote URI schemes are outside this test.
            links = re.findall(r"\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)", text)
            links += re.findall(r"(?m)^\s*\[[^]]+\]:\s*<?([^\s>]+)>?", text)
            for link in links:
                uri = urlsplit(link)
                if uri.scheme or uri.netloc or not uri.path:
                    continue
                path = unquote(uri.path)
                target = ROOT / path.lstrip("/") if path.startswith("/") else document.parent / path
                with self.subTest(doc=name, link=link):
                    self.assertTrue(target.exists(), f"{name} links to missing {link}")


if __name__ == "__main__":
    unittest.main()
