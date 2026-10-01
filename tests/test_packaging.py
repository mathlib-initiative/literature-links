"""The package as a package: its entry points, its imports, its version and its docs.

It checks that the package imports nothing but the standard library and
itself, that the console script and ``python3 -m`` both reach the checker,
that the version is stated once, that the repository has the documented
layout, and that every repository path the docs cite exists.
"""
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

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
# The copy under test is the one Python imports: an installed package when
# there is one.  Only when none is importable does the suite fall back to the
# source tree, so a checkout still runs with nothing installed.
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                  # noqa: E402
from formal_companion_annotations import validate as V               # noqa: E402

#: The imported package's directory, wherever it was installed.
PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
#: The directory it was imported from (``src/`` or a ``site-packages``).
IMPORT_ROOT = PACKAGE.parent
EXAMPLES = ROOT / "examples" / "annotations"
SCHEMA_FILE = "annotations-v1.0.schema.json"
#: Set by the CI job that installs the package and runs the suite against it.
EXPECT_INSTALLED = os.environ.get("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED") == "1"


def subprocess_env() -> dict:
    """The environment for a child ``python3 -m``: it imports the copy under test."""
    path = os.pathsep.join(p for p in (str(IMPORT_ROOT), os.environ.get("PYTHONPATH", "")) if p)
    return dict(os.environ, PYTHONPATH=path, PYTHONDONTWRITEBYTECODE="1")


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


class TestStandalone(unittest.TestCase):

    def test_the_package_imports_only_the_standard_library_and_itself(self):
        """The imported copy, and the source tree's when that is another copy."""
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

    def test_the_version_is_stated_once(self):
        """pyproject, ``__version__`` and the CHANGELOG's first release heading agree.

        A heading is ``## <version>`` or ``## <version> (<date or "unreleased">)``.
        """
        version = formal_companion_annotations.__version__
        self.assertEqual(pyproject()["project"]["version"], version)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (\S+)", changelog, re.M)
        released = [h for h in headings if h != "Unreleased"]
        self.assertTrue(released)
        self.assertEqual(released[0], version)
        # An "Unreleased" entry, when there is one, comes first and only once.
        self.assertLessEqual(headings.count("Unreleased"), 1)
        if "Unreleased" in headings:
            self.assertEqual(headings[0], "Unreleased")

    def test_a_release_candidate_is_marked_beta(self):
        classifiers = pyproject()["project"]["classifiers"]
        status = [c for c in classifiers if c.startswith("Development Status ::")]
        self.assertEqual(len(status), 1)
        if "rc" in formal_companion_annotations.__version__:
            self.assertEqual(status, ["Development Status :: 4 - Beta"])
        else:
            self.assertEqual(status, ["Development Status :: 5 - Production/Stable"])

    def test_the_schema_ships_as_package_data(self):
        data = pyproject()["tool"]["setuptools"]["package-data"]["formal_companion_annotations"]
        self.assertIn("schema/*.json", data)
        self.assertTrue(V.SCHEMA_PATH.is_file())
        self.assertEqual(V.SCHEMA_PATH.name, SCHEMA_FILE)
        self.assertEqual(Path(V.__file__).resolve().parent, PACKAGE)
        self.assertEqual(V.SCHEMA_PATH.parent, PACKAGE / "schema")
        self.assertNotEqual(V.SCHEMA_PATH.resolve().parent, (ROOT / "schema").resolve(),
                            "the checker must load its own package data, not the repository's schema/")

    def test_the_copy_under_test_is_the_installed_one_when_ci_says_so(self):
        """The CI job that installs the package sets FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED=1."""
        if not EXPECT_INSTALLED:
            self.skipTest("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED is not set")
        self.assertFalse(PACKAGE.is_relative_to(SRC.resolve()), f"imported from the source tree: {PACKAGE}")
        self.assertNotIn(str(SRC), sys.path)
        self.assertIn("site-packages", PACKAGE.parts, PACKAGE)


class TestEntryPoints(unittest.TestCase):

    def test_the_console_script_names_the_checkers_main(self):
        scripts = pyproject()["project"]["scripts"]
        self.assertEqual(scripts, {"formal-companion-annotations-validate": "formal_companion_annotations.validate:main"})

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
                self.assertEqual((child.returncode, child.stdout, child.stderr), (0, out, ""))

    def test_a_missing_packaged_schema_is_a_broken_install_exit_2(self):
        """Not exit 1 with "no schema for major version 1", which blames the document."""
        good = EXAMPLES / "mixed.json"
        with tempfile.TemporaryDirectory() as tmp:
            tmp = str(Path(tmp).resolve())         # the checker reports its resolved path
            broken = Path(tmp) / "formal_companion_annotations"
            shutil.copytree(PACKAGE, broken, ignore=shutil.ignore_patterns("__pycache__"))
            shutil.rmtree(broken / "schema")
            env = dict(os.environ, PYTHONPATH=tmp, PYTHONDONTWRITEBYTECODE="1")
            for module in ("formal_companion_annotations", "formal_companion_annotations.validate"):
                with self.subTest(module=module):
                    child = self.run_module(module, str(good), env=env)
                    self.assertEqual(child.returncode, 2, child.stdout + child.stderr)
                    self.assertEqual(child.stdout, "")
                    missing = broken / "schema" / SCHEMA_FILE
                    self.assertTrue(child.stderr.startswith(
                        f"formal-companion-annotations-validate: schema file not found: {missing} "), child.stderr)
                    self.assertNotIn("no schema for major version", child.stderr)
                    self.assertNotIn("Traceback", child.stderr)
                    # --print-canonical validates first, so it needs the schema too.
                    printed = self.run_module(module, str(good), "--print-canonical", env=env)
                    self.assertEqual(printed.returncode, 2, printed.stderr)
                    self.assertEqual(printed.stdout, "")
                    self.assertIn("schema file not found", printed.stderr)


#: A backticked token is read as a path in this repository when it starts with one of these.
#: ``conformance/`` is the conformance suite's own concern (tests/test_conformance.py).
REPO_ROOTS = ("src/", "schema/", "examples/", "docs/", "tests/", ".github/")
REPO_FILES = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "MANIFEST.in", "pyproject.toml")
#: Documents about THIS repository.
DOCS = ("README.md", "CONTRIBUTING.md", "docs/annotations.md", "docs/id-algorithm.md", "docs/vocabulary.md",
        "docs/mapping-notes.md", "docs/history.md")
#: The repository layout (README.md "Repository layout").
LAYOUT = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE", "MANIFEST.in", "pyproject.toml",
          "docs/annotations.md", "docs/id-algorithm.md", "docs/vocabulary.md", "docs/mapping-notes.md",
          "docs/history.md", f"schema/{SCHEMA_FILE}", "src/formal_companion_annotations/__init__.py",
          "src/formal_companion_annotations/__main__.py", "src/formal_companion_annotations/validate.py",
          "src/formal_companion_annotations/schemacheck.py", "src/formal_companion_annotations/ids.py",
          "src/formal_companion_annotations/vocab.py", f"src/formal_companion_annotations/schema/{SCHEMA_FILE}",
          "src/formal_companion_annotations/py.typed", "examples/annotations/minimal.json", "conformance/ids",
          "tests", ".github/workflows/tests.yml")


class TestTheRepositoryLayout(unittest.TestCase):

    def test_the_documented_layout_exists(self):
        for path in LAYOUT:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).exists(), f"{path} is not here")
        self.assertEqual(sorted(p.name for p in ROOT.glob("*.md")), ["CHANGELOG.md", "CONTRIBUTING.md", "README.md"],
                         "the top-level documents are exactly the documented three")
        self.assertEqual(sorted(p.name for p in (ROOT / "schema").glob("*")), [SCHEMA_FILE])

    def test_the_sdist_manifest_carries_the_test_inputs(self):
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        for line in ("include CHANGELOG.md CONTRIBUTING.md MANIFEST.in\n", "graft docs\n", "graft examples\n",
                     "graft schema\n", "graft conformance\n", "graft tests\n", "graft .github\n"):
            self.assertIn(line, manifest)
        self.assertEqual(manifest.count("include "), 1)

    def test_the_ci_names_the_schema_file(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn(f"schema/{SCHEMA_FILE}", workflow)
        self.assertNotIn("annotations-v1.schema.json", workflow)


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


if __name__ == "__main__":
    unittest.main()
