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
import unicodedata
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
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
from literature_links import discovery                   # noqa: E402

PACKAGE = Path(literature_links.__file__).resolve().parent
IMPORT_ROOT = PACKAGE.parent
EXAMPLES = ROOT / "examples" / "companion"
FIXTURE = HERE / "fixtures" / "companion"
ANNOTATION_SUFFIXES = (".json", ".jsonl", ".ndjson")
EXPECT_INSTALLED = os.environ.get("LITERATURE_LINKS_TEST_INSTALLED") == "1"
EXPECT_RELEASE = os.environ.get("LITERATURE_LINKS_RELEASE") == "1"


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
        # 1.x was never public: the oldest entry is 2.0.0, the first public release.
        self.assertEqual(released[-1], "2.0.0")
        oldest = changelog[changelog.rindex("\n## "):].split("\n", 2)[2]
        self.assertTrue(oldest.lstrip().startswith("First public release."), oldest[:80])

    def test_a_release_commit_dates_its_changelog_heading(self):
        if not EXPECT_RELEASE:
            self.skipTest("LITERATURE_LINKS_RELEASE is not set")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        heading = re.search(r"^## .*$", changelog, re.M).group(0)
        dated = re.fullmatch(rf"## {re.escape(literature_links.__version__)} \((\d{{4}}-\d{{2}}-\d{{2}})\)", heading)
        self.assertTrue(dated, heading)
        date.fromisoformat(dated.group(1))

    def test_the_schema_id_names_the_release_tag(self):
        # The $id names this release's tag, so a later schema never claims an earlier release.
        expected = (f"https://raw.githubusercontent.com/mathlib-initiative/literature-links/"
                    f"v{literature_links.__version__}/schema/companion.schema.json")
        self.assertEqual(C.load_schema()["$id"], expected)

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
                      "FILE", err)
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
        files = sorted(path for path in EXAMPLES.rglob("*")
                       if path.suffix.lower() in ANNOTATION_SUFFIXES and path.name != "_defaults.json")
        # The examples include JSONL and folder defaults, so validate and scan read both.
        self.assertTrue(any(path.suffix.lower() != ".json" for path in files))
        self.assertTrue(any(EXAMPLES.rglob("_defaults.json")))
        self.assertEqual(self.run_cli("validate", *map(str, files))[0], 0)
        count = sum(1 if path.suffix.lower() == ".json" else
                    sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip(" \t"))
                    for path in files)
        status, out, _ = self.run_cli("scan", str(EXAMPLES))
        summary = f"{count} annotation{'s' * (count != 1)} from {len(files)} file{'s' * (len(files) != 1)}"
        self.assertEqual((status, out), (0, f"{summary}; 0 problems\n"))

    def test_the_examples_show_each_location_form_and_field(self):
        # The README says so.
        schema = C.load_schema()
        records = discovery.collect([EXAMPLES]).records
        ends = [end for record in records for side in ("subject", "object") for end in record.annotation[side]]
        self.assertEqual({key for record in records for key in record.annotation}, set(schema["properties"]))
        self.assertEqual({key for end in ends for key in end}, set(schema["$defs"]["end"]["properties"]))
        for mode in schema["$defs"]["end"]["properties"]["type"]["enum"]:
            locations = [end["location"] for end in ends if end["type"] == mode and "location" in end]
            keys = set(schema["$defs"].get(f"{mode}_location", {}).get("properties", {}))
            with self.subTest(type=mode):
                self.assertTrue(locations)
                self.assertLessEqual(keys, {key for location in locations for key in location})
        self.assertTrue(any("profile" in end.get("location", {}) for end in ends))

    def test_a_missing_schema_is_reported_without_a_traceback(self):
        good = FIXTURE / "links.jsonl"
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
DOCS = ("README.md", "CONTRIBUTING.md", "docs/companion.md", "docs/tools.md")
#: The section anchors of docs/companion.md. Other repositories may link to them.
SPEC_ANCHORS = ("literature-links-specification", "terms", "fields", "relation", "unlinked-passages-and-checked-absences",
                "status-kind-id-and-note", "ends", "location", "pdf", "latex", "html", "lean", "lines", "generic",
                "extensions", "references", "folder-defaults", "validation", "discovery")


def prose(text: str) -> str:
    """Markdown without its fenced code blocks."""
    return re.sub(r"(?ms)^```.*?^```[ \t]*$", "", text)


def anchors(text: str) -> set[str]:
    """GitHub's heading anchors: lowercase, punctuation dropped, spaces as hyphens, repeats numbered."""
    result: set[str] = set()
    counts: dict[str, int] = {}
    for heading in re.findall(r"(?m)^#{1,6}[ \t]+(.+?)[ \t]*$", prose(text)):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        counts[slug] = counts.get(slug, 0) + 1
        result.add(slug if counts[slug] == 1 else f"{slug}-{counts[slug] - 1}")
    return result


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

    def test_the_readme_example_is_valid(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        blocks = re.findall(r"(?ms)^```json\n(.*?)^```", readme)
        self.assertTrue(blocks)
        for block in blocks:
            with self.subTest(block=block[:40]):
                self.assertEqual(C.validate(C.loads(block)), [])

    def test_the_specification_examples_are_valid(self):
        spec = (ROOT / "docs" / "companion.md").read_text(encoding="utf-8")
        # A block holds an annotation, an end or a "location" member, or belongs to the folder defaults
        # example: a defaults file, an annotation written beside it, and that annotation as read.
        blocks = [C.loads(block if block.startswith("{") else "{" + block + "}")
                  for block in re.findall(r"(?ms)^```json\n(.*?)^```", spec)]
        first = next(index for index, block in enumerate(blocks) if isinstance(block.get("subject"), dict))
        defaults, written, read = blocks[first:first + 3]
        inherited = C.merge({}, defaults, defaults=True)
        self.assertEqual(C.merge(inherited, written), read)
        for block in blocks[:first] + blocks[first + 2:]:
            if "subject" in block:
                annotations = [block]
            elif "type" in block:
                annotations = [{"subject": [block], "object": []}]
            else:
                annotations = [{"subject": [{"type": mode, "uri": "a", **block}], "object": []}
                               for mode in ("pdf", "latex", "html", "lean", "generic")]
            for annotation in annotations:
                with self.subTest(annotation=annotation):
                    self.assertEqual(C.validate(annotation), [])
        # The checked absence written in prose leaves its object to the template.
        absence, = (C.loads(span) for span in re.findall(r"`(\{[^`]*\"noMatch\"[^`]*\})`", prose(spec)))
        merged = C.merge(inherited, absence)
        self.assertEqual((merged["object"], C.validate(merged)), ([defaults["object"]], []))
        # In the section of each type, an object in prose is a location of that type.
        found, section = set(), ""
        for line in prose(spec).splitlines():
            if line.startswith("#"):
                section = line.lstrip("#").strip().lower()
            elif section in ("pdf", "latex", "lean", "generic"):
                for span in re.findall(r"`(\{[^`]*\})`", line):
                    found.add(section)
                    with self.subTest(section=section, location=span):
                        location = C.loads(span)
                        self.assertEqual(C.validate({"subject": [{"type": section, "uri": "a", "location": location}],
                                                     "object": []}), [])
        self.assertEqual(found, {"pdf", "latex", "lean", "generic"})

    def test_the_tools_example_runs(self):
        example, = re.findall(r"(?ms)^```python\n(.*?)^```", (ROOT / "docs" / "tools.md").read_text(encoding="utf-8"))
        check = "assert problems == [] and collection.problems == [] and collection.records, (problems, collection)\n"
        child = subprocess.run([sys.executable, "-c", example + check], capture_output=True, text=True,
                               env=subprocess_env(), cwd=ROOT, check=False)
        self.assertEqual((child.returncode, child.stderr), (0, ""))

    def test_no_em_dash_in_the_docs(self):
        for name in DOCS + ("CHANGELOG.md",):
            with self.subTest(doc=name):
                self.assertNotIn("—", (ROOT / name).read_text(encoding="utf-8"))

    def test_no_file_holds_a_literal_invisible_character(self):
        # Bidirectional, zero-width and other invisible characters make text read unlike what it holds, and
        # GitHub flags them. Python and JSON write them as escapes.
        paths = [*ROOT.iterdir(), *(path for root in REPO_ROOTS for path in (ROOT / root).rglob("*"))]
        for path in sorted(paths):
            if path.suffix not in (".py", ".md", ".json", ".jsonl", ".toml", ".yml", ".in") or not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            hidden = sorted({f"U+{ord(char):04X}" for char in text if char not in "\t\n\r " and
                             (unicodedata.category(char) in ("Cc", "Cf", "Zs", "Zl", "Zp") or char in "\ufffe\uffff")})
            with self.subTest(file=path.relative_to(ROOT).as_posix()):
                self.assertEqual(hidden, [])

    def test_local_markdown_links_reach_a_file_and_heading(self):
        for name in DOCS + ("CHANGELOG.md",):
            document = ROOT / name
            text = prose(document.read_text(encoding="utf-8"))
            # Check inline/image links and reference definitions without a
            # Markdown dependency or network access. A fragment into a Markdown
            # file names one of its headings; remote URI schemes are outside this test.
            links = re.findall(r"\]\(<?([^\s)>]+)>?(?:\s+[^)]*)?\)", text)
            links += re.findall(r"(?m)^\s*\[[^]]+\]:\s*<?([^\s>]+)>?", text)
            for link in links:
                uri = urlsplit(link)
                if uri.scheme or uri.netloc:
                    continue
                path = unquote(uri.path)
                target = (ROOT / path.lstrip("/") if path.startswith("/") else document.parent / path) if path else document
                with self.subTest(doc=name, link=link):
                    self.assertTrue(target.exists(), f"{name} links to missing {link}")
                    if uri.fragment and target.suffix == ".md":
                        self.assertIn(unquote(uri.fragment), anchors(target.read_text(encoding="utf-8")),
                                      f"{name} links to a missing heading: {link}")

    def test_the_specification_and_the_tools_link_both_ways(self):
        spec, tools = ((ROOT / "docs" / name).read_text(encoding="utf-8") for name in ("companion.md", "tools.md"))
        self.assertIn("](tools.md", spec)
        self.assertIn("](companion.md", tools)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("](docs/companion.md)", readme)
        self.assertIn("](docs/tools.md)", readme)

    def test_the_specification_keeps_its_anchors(self):
        found = anchors((ROOT / "docs" / "companion.md").read_text(encoding="utf-8"))
        for anchor in SPEC_ANCHORS:
            with self.subTest(anchor=anchor):
                self.assertIn(anchor, found)


if __name__ == "__main__":
    unittest.main()
