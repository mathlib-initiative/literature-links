"""Packaging: stdlib-only imports, entry points, version, and paths the docs cite."""
from __future__ import annotations

import ast
import importlib.util
import io
import json
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
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                  # noqa: E402
from formal_companion_annotations import validate as V               # noqa: E402
from formal_companion_annotations import companion as C              # noqa: E402

PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
IMPORT_ROOT = PACKAGE.parent
EXAMPLES = ROOT / "examples" / "annotations"
EXPECT_INSTALLED = os.environ.get("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED") == "1"


def subprocess_env() -> dict:
    """The environment for a child ``python3 -m``: it imports the copy under test."""
    path = os.pathsep.join(p for p in (str(IMPORT_ROOT), os.environ.get("PYTHONPATH", "")) if p)
    return dict(os.environ, PYTHONPATH=path, PYTHONDONTWRITEBYTECODE="1")


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class TestStandalone(unittest.TestCase):

    def test_the_package_imports_only_the_standard_library_and_itself(self):
        copies = {PACKAGE, (SRC / "formal_companion_annotations").resolve()}
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

    def test_package_metadata_and_changelog_agree_on_the_version(self):
        self.assertEqual(pyproject()["project"]["version"], formal_companion_annotations.__version__)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (\S+)", changelog, re.M)
        released = [h for h in headings if h != "Unreleased"]
        self.assertTrue(released)
        self.assertEqual(released[0], formal_companion_annotations.__version__)
        self.assertLessEqual(headings.count("Unreleased"), 1)
        if "Unreleased" in headings:
            self.assertEqual(headings[0], "Unreleased")

    def test_the_schema_ships_as_package_data(self):
        setuptools = pyproject()["tool"]["setuptools"]
        data = setuptools["package-data"]["formal_companion_annotations.schema"]
        self.assertIn("*.json", data)
        self.assertEqual(setuptools["package-dir"]["formal_companion_annotations.schema"], "schema")
        for module in (C, V):
            with self.subTest(schema=module.SCHEMA_PATH.name):
                self.assertTrue(module.SCHEMA_PATH.is_file())
                self.assertEqual(Path(module.__file__).resolve().parent, PACKAGE)
                self.assertEqual(module.SCHEMA_PATH.read_bytes(), (ROOT / "schema" / module.SCHEMA_PATH.name).read_bytes())
                if PACKAGE.is_relative_to(SRC.resolve()):
                    self.assertEqual(module.SCHEMA_PATH.parent, ROOT / "schema")
                else:
                    self.assertEqual(module.SCHEMA_PATH.parent, PACKAGE / "schema")
                    self.assertNotEqual(module.SCHEMA_PATH.resolve().parent, (ROOT / "schema").resolve())

    def test_the_copy_under_test_is_the_installed_one_when_ci_says_so(self):
        if not EXPECT_INSTALLED:
            self.skipTest("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED is not set")
        self.assertFalse(PACKAGE.is_relative_to(SRC.resolve()), f"imported from the source tree: {PACKAGE}")
        self.assertNotIn(str(SRC), sys.path)
        self.assertIn("site-packages", PACKAGE.parts, PACKAGE)


class TestEntryPoints(unittest.TestCase):

    def test_the_console_script_names_the_checkers_main(self):
        scripts = pyproject()["project"]["scripts"]
        self.assertEqual(scripts, {"formal-companion-annotations-validate": "formal_companion_annotations.validate:main",
                                   "formal-companion-annotations": "formal_companion_annotations.cli:main"})

    def run_module(self, module: str, *argv: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-m", module, *argv], capture_output=True, text=True,
                              env=env or subprocess_env(), cwd=ROOT, check=False)

    def test_a_child_process_imports_the_copy_under_test(self):
        child = subprocess.run([sys.executable, "-c",
                                "import formal_companion_annotations as p; print(p.__file__)"],
                               capture_output=True, text=True, env=subprocess_env(), cwd=ROOT, check=True)
        self.assertEqual(Path(child.stdout.strip()).resolve().parent, PACKAGE)

    def test_python_dash_m_runs_the_checker(self):
        for module in ("formal_companion_annotations", "formal_companion_annotations.validate"):
            with self.subTest(module=module):
                ok = self.run_module(module, str(EXAMPLES / "mixed.json"), "--canonical")
                self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
                self.assertIn(": ok (", ok.stdout)
                bad = EXAMPLES / "invalid-dangling-reference.json"
                want = json.loads(bad.read_text(encoding="utf-8"))["x_expected_error"]
                failed = self.run_module(module, str(bad))
                self.assertEqual(failed.returncode, 1)
                self.assertEqual(failed.stdout, f"{bad}: {want}\n")
                self.assertEqual(failed.stderr, "")

    def test_python_dash_m_supports_the_current_commands(self):
        example = ROOT / "examples" / "companion" / "pdf.json"
        for argv in (("validate", str(example)), ("scan", str(example)), ("format", str(example))):
            with self.subTest(arguments=argv):
                child = self.run_module("formal_companion_annotations", *argv)
                self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
        help_result = self.run_module("formal_companion_annotations", "--help")
        self.assertEqual(help_result.returncode, 0)
        self.assertIn("scan", help_result.stdout)
        self.assertIn("Legacy", help_result.stdout)

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                status = V.main(list(argv))
            except SystemExit as exc:              # argparse: --version, --help and usage errors
                status = exc.code
        return status, out.getvalue(), err.getvalue()

    def test_usage_names_the_console_script(self):
        status, out, err = self.run_cli()
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertTrue(err.startswith("usage: formal-companion-annotations-validate "), err)
        self.assertIn("formal-companion-annotations-validate: error: the following arguments are required: "
                      "documents", err)
        self.assertNotIn("validate.py", err)
        status, out, err = self.run_cli("a.json", "b.json", "--print-canonical")
        self.assertEqual(status, 2)
        self.assertIn("formal-companion-annotations-validate: error: --print-canonical takes exactly one "
                      "document", err)
        status, out, _ = self.run_cli("--help")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("usage: formal-companion-annotations-validate "), out)
        self.assertIn("--version", out)

    def test_version_prints_the_package_version(self):
        status, out, err = self.run_cli("--version")
        self.assertEqual((status, out, err),
                         (0, f"formal-companion-annotations-validate {formal_companion_annotations.__version__}\n", ""))
        for module in ("formal_companion_annotations", "formal_companion_annotations.validate"):
            with self.subTest(module=module):
                child = self.run_module(module, "--version")
                program = "formal-companion-annotations" if module == "formal_companion_annotations" else "formal-companion-annotations-validate"
                self.assertEqual((child.returncode, child.stdout, child.stderr),
                                 (0, f"{program} {formal_companion_annotations.__version__}\n", ""))

    def test_a_missing_packaged_schema_is_a_broken_install_exit_2(self):
        good = EXAMPLES / "mixed.json"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = str(Path(tmp).resolve())         # the checker reports its resolved path
            broken = Path(tmp) / "formal_companion_annotations"
            shutil.copytree(PACKAGE, broken, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.rmtree(broken / "schema", ignore_errors=True)
            env = dict(os.environ, PYTHONPATH=tmp, PYTHONDONTWRITEBYTECODE="1")
            for module in ("formal_companion_annotations", "formal_companion_annotations.validate"):
                with self.subTest(module=module):
                    child = self.run_module(module, str(good), env=env)
                    self.assertEqual(child.returncode, 2, child.stdout + child.stderr)
                    self.assertEqual(child.stdout, "")
                    missing = broken / "schema" / "annotations-v1.schema.json"
                    self.assertTrue(child.stderr.startswith(
                        f"formal-companion-annotations-validate: schema file not found: {missing} "), child.stderr)
                    self.assertNotIn("no schema for major version", child.stderr)
                    self.assertNotIn("Traceback", child.stderr)
                    # --print-canonical reads no schema, so it still works there.
                    printed = self.run_module(module, str(good), "--print-canonical", env=env)
                    self.assertEqual(printed.returncode, 0, printed.stderr)
                    self.assertEqual(printed.stdout, good.read_text(encoding="utf-8"))

    def test_a_missing_current_schema_is_reported_without_a_traceback(self):
        good = ROOT / "examples" / "companion" / "pdf.json"
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp).resolve() / "formal_companion_annotations"
            shutil.copytree(PACKAGE, broken, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.rmtree(broken / "schema", ignore_errors=True)
            env = dict(os.environ, PYTHONPATH=str(broken.parent), PYTHONDONTWRITEBYTECODE="1")
            child = self.run_module("formal_companion_annotations", "validate", str(good), env=env)
            self.assertEqual(child.returncode, 2, child.stdout + child.stderr)
            self.assertIn("companion.schema.json", child.stderr)
            self.assertNotIn("Traceback", child.stdout + child.stderr)


REPO_ROOTS = ("src/", "schema/", "examples/", "conformance/", "docs/", "tests/", ".github/")
REPO_FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "pyproject.toml")
#: CHANGELOG.md is excluded: it cites the skill's paths by design.
DOCS = ("README.md", "CONTRIBUTING.md", *(str(path.relative_to(ROOT))
        for folder in ("docs", "examples", "conformance", "schema")
        for path in sorted((ROOT / folder).rglob("*.md"))))


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
