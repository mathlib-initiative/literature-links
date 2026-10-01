"""The package as a package: where it finds the schema, its entry points, its version, its public API.

The suite tests whichever copy Python imports: an installed wheel, or the
source tree when nothing is installed.  CI sets
FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED=1 where it installed the wheel.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.util
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                  # noqa: E402
from formal_companion_annotations import validate as V               # noqa: E402

PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
FROM_SOURCE = PACKAGE == (SRC / "formal_companion_annotations").resolve()
SCHEMA = ROOT / "schema" / "annotations-v1.0.schema.json"
EXAMPLES = ROOT / "examples" / "annotations"
MODULES = ("ids", "schemacheck", "validate", "vocab")

#: The public names of each module: a name leaves only in a major release.
EXPECTED_ALL = {
    "validate": {"LINTS", "LoadError", "PROFILES", "Problem", "RECORD_ARRAYS", "Report", "SCHEMA_DIR", "SCHEMA_PATH",
                 "canonical_dumps", "canonicalize", "check", "loads", "main", "order_key", "schema_path",
                 "site_sha256", "validate"},
    "schemacheck": {"SchemaError", "Validator"},
    "ids": {"DECLARED_ID", "HASH_ID", "anonymous_id", "hash_form", "item_label_id", "normalize_statement",
            "normalize_text", "passage_page_id", "passage_quote_id", "private_id", "statement_sha256"},
    "vocab": {
        "ANNOTATION_ARTIFACT_KINDS", "ANNOTATION_CHANGELOG_EVENTS", "ANNOTATION_CHANGELOG_REASONS",
        "ANNOTATION_CHANGELOG_SUBJECTS", "ANNOTATION_CONFORMS_TO", "ANNOTATION_COORDINATE_ORIGINS",
        "ANNOTATION_COORDINATE_UNITS", "ANNOTATION_COORDINATE_X_AXES", "ANNOTATION_COORDINATE_Y_AXES",
        "ANNOTATION_COVERAGE", "ANNOTATION_DESTINATION_RESOLUTIONS", "ANNOTATION_DESTINATION_SITES",
        "ANNOTATION_ID_SOURCES", "ANNOTATION_ITEM_FORMS", "ANNOTATION_ITEM_ID_SOURCES", "ANNOTATION_ITEM_RELATIONS",
        "ANNOTATION_LEAN_KINDS", "ANNOTATION_LINK_RELATIONS", "ANNOTATION_LINK_ROLES", "ANNOTATION_MEMBER_PARENT_KINDS",
        "ANNOTATION_MEMBERSHIP_ROLES", "ANNOTATION_ORIGIN_Y_AXIS", "ANNOTATION_PAGE_ANCHORS", "ANNOTATION_PAGE_BASES",
        "ANNOTATION_PAGE_BOXES", "ANNOTATION_PROFILE_VERSIONS", "ANNOTATION_PROFILES", "ANNOTATION_PROVENANCE_ACTORS",
        "ANNOTATION_PROVENANCE_METHODS", "ANNOTATION_RESOLUTION_STATES", "ANNOTATION_SCHEMA",
        "ANNOTATION_SCHEMA_ID_BASE", "ANNOTATION_SCHEMA_MAJOR", "ANNOTATION_SCHEMA_VERSION",
        "ANNOTATION_SELECTOR_TYPES", "ANNOTATION_SEVERITIES", "ANNOTATION_SORRY_CLASSES", "ANNOTATION_SOURCE_KINDS",
        "ANNOTATION_SOURCE_ROLES", "ANNOTATION_SOURCE_SCOPES", "ANNOTATION_TEXT_CASE", "ANNOTATION_TEXT_ORIGINS",
        "ANNOTATION_TEXT_UNICODE", "ANNOTATION_TEXT_WHITESPACE", "ANNOTATION_UNATTRIBUTED_CLAIMS",
        "ANNOTATION_VERDICT_STATUSES", "ANNOTATION_VERDICTS", "ANNOTATION_XREF_DATABASES", "ANONYMOUS_KEYWORDS",
        "CONFORMS_TO_HTML", "CONFORMS_TO_MEDIA", "CONFORMS_TO_PDF", "CONFORMS_TO_PDF_RFC3778", "CONFORMS_TO_TEXT",
        "DECLARED_ID_PATTERN", "DECLARED_SLUG_PATTERN", "HASH_ID_PATTERN", "PASSAGE_PAGE_ID_PATTERN",
        "PASSAGE_QUOTE_ID_PATTERN"},
}


def module(name: str):
    return importlib.import_module(f"formal_companion_annotations.{name}")


def pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def run_module(name: str, *argv: str, path: str | None = None) -> subprocess.CompletedProcess:
    """``python -m <name>`` in a child that imports the copy under test (or the one under ``path``)."""
    env = dict(os.environ, PYTHONPATH=path or str(PACKAGE.parent), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-m", name, *argv], capture_output=True, text=True, env=env, cwd=ROOT,
                          check=False)


class TestTheSchemaShips(unittest.TestCase):

    def test_one_schema_file_mapped_into_the_wheel(self):
        setuptools = pyproject()["tool"]["setuptools"]
        self.assertEqual(setuptools["package-dir"], {"": "src", "formal_companion_annotations.schema": "schema"})
        self.assertIn("formal_companion_annotations.schema", setuptools["packages"])
        self.assertEqual(setuptools["package-data"]["formal_companion_annotations.schema"], ["*.json"])
        self.assertFalse((SRC / "formal_companion_annotations" / "schema").exists(), "no second copy")

    def test_the_checker_finds_the_schema_installed_or_in_a_checkout(self):
        self.assertTrue(V.SCHEMA_PATH.is_file(), V.SCHEMA_PATH)
        self.assertEqual(V.SCHEMA_PATH.read_bytes(), SCHEMA.read_bytes())
        if FROM_SOURCE:
            self.assertEqual(V.SCHEMA_DIR, ROOT / "schema")
        else:
            self.assertEqual(V.SCHEMA_DIR, PACKAGE / "schema")

    def test_the_copy_under_test_is_the_installed_one_when_ci_says_so(self):
        if os.environ.get("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED") != "1":
            self.skipTest("FORMAL_COMPANION_ANNOTATIONS_TEST_INSTALLED is not set")
        self.assertFalse(FROM_SOURCE)
        self.assertIn("site-packages", PACKAGE.parts)
        self.assertNotIn(str(SRC), sys.path)

    def test_a_missing_schema_is_a_broken_install_exit_2(self):
        """Not exit 1 with "no schema for major version 1", which would blame the document."""
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp).resolve() / "a" / "b"
            shutil.copytree(PACKAGE, top / "formal_companion_annotations",
                            ignore=shutil.ignore_patterns("__pycache__", "schema"))
            missing = top.parent / "schema" / SCHEMA.name
            for name, argv in (("formal_companion_annotations", ()), ("formal_companion_annotations.validate",
                                                                      ("--print-canonical",))):
                child = run_module(name, str(EXAMPLES / "mixed.json"), *argv, path=str(top))
                with self.subTest(module=name, argv=argv):
                    self.assertEqual((child.returncode, child.stdout), (2, ""))
                    self.assertTrue(child.stderr.startswith(f"formal-companion-annotations-validate: schema file not "
                                                            f"found: {missing} "), child.stderr)


class TestStandalone(unittest.TestCase):

    def test_the_package_imports_only_the_standard_library_and_itself(self):
        modules = sorted({*PACKAGE.glob("*.py"), *(SRC / "formal_companion_annotations").glob("*.py")})
        self.assertGreaterEqual(len(modules), 6)
        for path in modules:
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module or ""]
                elif isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                else:
                    continue
                for name in names:
                    self.assertIn(name.split(".")[0], sys.stdlib_module_names | {"__future__"}, path.name)
        self.assertEqual(pyproject()["project"]["dependencies"], [])

    def test_the_version_is_stated_once(self):
        """pyproject, ``__version__`` and the CHANGELOG's first heading agree; a candidate is Beta."""
        version = formal_companion_annotations.__version__
        self.assertEqual(pyproject()["project"]["version"], version)
        headings = re.findall(r"^## (\S+)", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
        self.assertEqual(headings[0], version)
        status = [c for c in pyproject()["project"]["classifiers"] if c.startswith("Development Status ::")]
        self.assertEqual(status, ["Development Status :: 4 - Beta" if "rc" in version
                                  else "Development Status :: 5 - Production/Stable"])
        self.assertEqual(int(version.split(".")[0]), module("vocab").ANNOTATION_SCHEMA_MAJOR, "MAJOR is the format's")


class TestEntryPoints(unittest.TestCase):

    def test_the_console_script_and_python_dash_m_run_the_checker(self):
        self.assertEqual(pyproject()["project"]["scripts"],
                         {"formal-companion-annotations-validate": "formal_companion_annotations.validate:main"})
        bad = EXAMPLES / "invalid-dangling-reference.json"
        want = json.loads(bad.read_text(encoding="utf-8"))["x_expected_error"]
        for name in ("formal_companion_annotations", "formal_companion_annotations.validate"):
            with self.subTest(module=name):
                ok = run_module(name, str(EXAMPLES / "mixed.json"), "--canonical")
                self.assertEqual((ok.returncode, ok.stderr), (0, ""))
                self.assertIn(": ok (", ok.stdout)
                failed = run_module(name, str(bad))
                self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (1, f"{bad}: {want}\n", ""))
                version = run_module(name, "--version")
                self.assertEqual((version.returncode, version.stdout),
                                 (0, f"formal-companion-annotations-validate {formal_companion_annotations.__version__}\n"))

    def test_usage_names_the_console_script(self):
        child = run_module("formal_companion_annotations")
        self.assertEqual((child.returncode, child.stdout), (2, ""))
        self.assertTrue(child.stderr.startswith("usage: formal-companion-annotations-validate "), child.stderr)
        self.assertIn("error: the following arguments are required: documents", child.stderr)
        child = run_module("formal_companion_annotations", "--help")
        self.assertEqual(child.returncode, 0)
        self.assertIn("--print-canonical", child.stdout)


class TestThePublicApi(unittest.TestCase):
    """Each module's ``__all__`` is its stable API."""

    def test_all_is_exactly_the_documented_names(self):
        self.assertEqual(formal_companion_annotations.__all__, ["__version__", *MODULES])
        self.assertEqual(module("__main__").__all__, [])
        for name, expected in EXPECTED_ALL.items():
            mod = module(name)
            with self.subTest(module=name):
                self.assertEqual(set(mod.__all__), expected)
                self.assertEqual(len(mod.__all__), len(set(mod.__all__)))
                namespace: dict = {}
                exec(f"from formal_companion_annotations.{name} import *", namespace)
                namespace.pop("__builtins__", None)
                self.assertEqual(set(namespace), expected)
        vocab = module("vocab")
        self.assertEqual({n for n in vars(vocab) if n.isupper() and not n.startswith("_")}, set(vocab.__all__))

    def test_the_lean_scanner_is_not_here(self):
        ids = module("ids")
        for name in ("scan_file", "assign_ids", "ordinal_ids", "signature_at", "AnonymousDecl", "_File",
                     "_header_end", "_declared_tag"):
            self.assertFalse(hasattr(ids, name), name)

    def test_every_public_callable_is_annotated(self):
        self.assertTrue((PACKAGE / "py.typed").is_file())
        for name in MODULES:
            mod = module(name)
            for attr in mod.__all__:
                obj = getattr(mod, attr)
                if inspect.isclass(obj):
                    functions = [f for n, f in vars(obj).items()
                                 if inspect.isfunction(f) and (not n.startswith("_") or n == "__init__")]
                else:
                    functions = [obj] if inspect.isfunction(obj) else []
                for fn in functions:
                    signature = inspect.signature(fn)
                    with self.subTest(module=name, name=f"{attr}.{fn.__name__}"):
                        self.assertIsNot(signature.return_annotation, inspect.Signature.empty)
                        for p in signature.parameters.values():
                            if p.name not in ("self", "cls"):
                                self.assertIsNot(p.annotation, inspect.Parameter.empty, p.name)

    def test_the_checkers_records_and_signatures(self):
        self.assertEqual([f.name for f in dataclasses.fields(V.Problem)], ["code", "path", "message"])
        self.assertEqual([f.name for f in dataclasses.fields(V.Report)], ["problems", "warnings"])
        problem = V.Problem("I3", "$.links[0].item", "'x' is not an id in items[]")
        self.assertEqual(str(problem), "$.links[0].item: 'x' is not an id in items[]")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            problem.code = "I4"                                         # type: ignore[misc]
        report = V.Report()
        self.assertTrue(report.ok)
        report.problems.append(problem)
        self.assertFalse(report.ok)
        for fn in (V.check, V.validate):
            params = inspect.signature(fn).parameters
            self.assertEqual(list(params), ["doc", "text", "canonical", "lints", "schema"])
            self.assertTrue(all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in list(params.values())[1:]))
        self.assertEqual(list(inspect.signature(V.loads).parameters), ["text"])
        self.assertEqual(list(inspect.signature(V.schema_path).parameters), ["major", "minor"])
        for name, owned in V.PROFILES.items():
            self.assertEqual(set(owned), {"arrays", "fields"})
            self.assertTrue(all(a in V.RECORD_ARRAYS for a in owned["arrays"]))
            for dotted in owned["fields"]:
                self.assertIn(dotted.partition(".")[0], {"companion", *V.RECORD_ARRAYS})


class TestTheDocs(unittest.TestCase):

    def test_every_repository_path_the_docs_cite_exists(self):
        """A backticked or linked path under schema/, docs/, src/, examples/ or tests/ is in the repository."""
        self.assertEqual(sorted(p.name for p in ROOT.glob("*.md")), ["CHANGELOG.md", "CONTRIBUTING.md", "README.md"])
        for name in ("README.md", "CONTRIBUTING.md", "docs/annotations.md"):       # the changelog is history
            text = (ROOT / name).read_text(encoding="utf-8")
            for token in re.findall(r"(?:`|\]\()((?:schema|docs|src|examples|tests)/[^`)\s]*)", text):
                if "<" not in token:
                    with self.subTest(doc=name, path=token):
                        self.assertTrue((ROOT / token).exists(), f"{name} cites {token}")

    def test_no_em_dash(self):
        for name in ("README.md", "CONTRIBUTING.md", "CHANGELOG.md", "docs/annotations.md"):
            self.assertNotIn("\u2014", (ROOT / name).read_text(encoding="utf-8"), name)


if __name__ == "__main__":
    unittest.main()
