"""The Annotation Format Map: built from this checkout, its wording names what the format has, and its script runs."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
SCHEMA = ROOT / "schema" / "companion.schema.json"
EXAMPLES = ROOT / "examples" / "companion"
# Test the installed copy when there is one, else src/.
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

from literature_links import discovery  # noqa: E402

# Runs the page's script against a stand-in for the few DOM calls it makes, clicks every
# example button, and reports what it wrote.
STUB = """
const {script, ids, schema, examples} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
function element() {
  return {children: [], dataset: {}, innerHTML: '', classList: {toggle() {}},
          get parentNode() { return element(); }, setAttribute() {},
          addEventListener(type, listener) { this.click = listener; },
          appendChild(child) { this.children.push(child); }};
}
const elements = new Map(ids.map(id => [id, element()]));
elements.get('schema-json').textContent = schema;
elements.get('examples-json').textContent = examples;
new Function('document', script)({getElementById: id => elements.get(id) || null, createElement: element,
                                  querySelectorAll: () => []});
const chips = elements.get('example-chips').children;
const merged = Object.fromEntries(chips.map(chip => {
  chip.click();
  return [chip.dataset.path, elements.get('example-merged').innerHTML];
}));
console.log(JSON.stringify({html: Object.fromEntries([...elements].map(([id, e]) => [id, e.innerHTML])),
                            chips: chips.map(chip => chip.dataset.path), merged}));
"""


def load_build():
    """site/build.py as a module: ``site`` is a standard library name, so it can't be imported as one."""
    spec = importlib.util.spec_from_file_location("site_build", SITE / "build.py")
    module = importlib.util.module_from_spec(spec)
    with patch.object(sys, "path", list(sys.path)):
        spec.loader.exec_module(module)
    return module


def embedded(page: str, name: str) -> str:
    return re.search(rf'<script type="application/json" id="{name}">(.*?)</script>', page, re.S)[1]


class TestTheMap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as folder:
            child = subprocess.run([sys.executable, "-B", str(SITE / "build.py"), folder],
                                   capture_output=True, text=True, check=False)
            if child.returncode:
                raise AssertionError(child.stdout + child.stderr)
            cls.page = (Path(folder) / "index.html").read_text(encoding="utf-8")
        cls.template = (SITE / "index.template.html").read_text(encoding="utf-8")
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.files = {file["path"]: file for file in json.loads(embedded(cls.page, "examples-json"))}
        cls.relations = re.search(r"var RELATIONS = \[(.*?)\n  \];", cls.template, re.S)[1]

    def test_the_page_stands_alone(self):
        self.assertTrue(self.page.startswith("<!doctype html>\n"))
        self.assertTrue(self.page.endswith("</html>\n"))
        self.assertIn('<meta charset="utf-8">', self.page[:1024])
        self.assertIn('<meta name="viewport"', self.page)
        self.assertNotRegex(self.page, r"@@[A-Z]+@@")
        self.assertNotIn(str(ROOT), self.page)
        ids = re.findall(r'\bid="([^"]+)"', self.page)
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_page_holds_the_schema_and_the_examples(self):
        self.assertEqual(json.loads(embedded(self.page, "schema-json")), self.schema)
        on_disk = {path.relative_to(EXAMPLES).as_posix(): path for path in EXAMPLES.rglob("*")
                   if path.is_file() and path.suffix.lower() in (".json", ".jsonl", ".ndjson")}
        self.assertEqual(set(self.files), set(on_disk))
        collection = discovery.collect([EXAMPLES], root=EXAMPLES)
        self.assertEqual(collection.problems, [])
        for name, path in on_disk.items():
            records = [record for record in collection.records if record.path == path]
            with self.subTest(example=name):
                self.assertEqual(self.files[name]["text"], path.read_text(encoding="utf-8"))
                self.assertEqual(self.files[name]["records"], [record.annotation for record in records])
                self.assertEqual(self.files[name]["defaults"], sorted({file.relative_to(EXAMPLES).as_posix()
                                                                       for record in records
                                                                       for file in record.defaults}))

    def test_embedded_data_cannot_end_its_script_element(self):
        data = {"note": "</script><!-- <script>"}
        text = load_build().embedded(data)
        self.assertNotIn("<", text)
        self.assertEqual(json.loads(text), data)

    def test_the_version_comes_from_the_changelog(self):
        version_lines = load_build().version_lines
        version, line = version_lines((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        self.assertIn(f"&middot; {version}</p>", self.page)
        self.assertIn(f'<p class="prov">{line}</p>', self.page)
        version, line = version_lines("# Changelog\n\n## 3.1.0 (2031-02-03)\n\n## 3.0.0 (2030-01-01)\n")
        self.assertEqual(version, "3.1.0")
        self.assertIn("/releases/tag/v3.1.0", line)
        self.assertIn("released 2031-02-03", line)
        for heading in ("## Unreleased", "## 3.1.0 (unreleased)"):
            with self.subTest(heading=heading):
                version, line = version_lines(f"# Changelog\n\n{heading}\n\n## 3.0.0 (2030-01-01)\n")
                self.assertEqual(version, "unreleased")
                self.assertNotIn("released 2030", line)
                self.assertIn("ahead of its last release", line)

    def test_the_wording_names_only_what_the_format_has(self):
        for table in ("SAY", "KEYS"):
            block = re.search(rf"var {table} = \{{(.*?)\n  \}};", self.template, re.S)[1]
            keys = re.findall(r"(?m)^\s*'([\w.]+)':", block)
            self.assertTrue(keys, table)
            for key in keys:
                owner, _, field = key.rpartition(".")
                with self.subTest(table=table, key=key):
                    self.assertIn(field, (self.schema["$defs"][owner] if owner else self.schema)["properties"])
        end = self.schema["$defs"]["end"]["properties"]
        known = {key for owner in (self.schema, *self.schema["$defs"].values()) for key in owner.get("properties", ())}
        known |= {*end["location"]["properties"], *end["type"]["enum"], *re.findall(r"(?m)^\s*\['(\w+)',", self.relations)}
        # The names of registries, which the wording gives as examples.
        known |= {"arxiv", "wikidata"}
        for name in re.findall(r"code\('(\$?\w+)'\)", self.template):
            with self.subTest(cited=name):
                self.assertIn(name, known)

    def test_the_relation_table_is_the_specifications(self):
        spec = (ROOT / "docs" / "companion.md").read_text(encoding="utf-8")
        section = re.search(r"(?ms)^## Relation$(.*?)^#", spec)[1]
        self.assertEqual(re.findall(r"(?m)^\s*\['(\w+)',", self.relations),
                         re.findall(r"(?m)^\| `(\w+)` \| (?!Reading)", section))
        for relation, example in re.findall(r"(?m)^\s*\['(\w+)',.*'([\w/-]+\.jsonl?)'\],?$", self.relations):
            with self.subTest(relation=relation):
                self.assertIn(relation, {record.get("relation") for record in self.files[example]["records"]})

    def test_the_tables_name_examples_that_exist(self):
        named = set(re.findall(r"'([\w./-]+\.(?:json|jsonl|ndjson))'", self.template))
        named -= {"name.json", "name.jsonl", "_defaults.json"}
        self.assertTrue(named)
        for name in named:
            with self.subTest(example=name):
                self.assertIn(name, self.files)
        forms = re.search(r"var EXAMPLES = \{(.*?)\};", self.template, re.S)[1]
        self.assertEqual(set(re.findall(r"(\w+): \[", forms)),
                         {*self.schema["$defs"]["end"]["properties"]["type"]["enum"], "profile"})

    def test_the_script_can_read_the_schema(self):
        # The script names these definitions, and shows a location's rules in only these forms.
        for name in ("citation", "extensions", "identifiers", "sha256"):
            self.assertIn(name, self.schema["$defs"])
        for name, definition in self.schema["$defs"].items():
            if name.endswith("_location"):
                with self.subTest(location=name):
                    self.assertLessEqual(set(definition), {"type", "properties", "additionalProperties", "required",
                                                           "oneOf", "anyOf", "not", "if", "then"})
                    self.assertLessEqual(len(set(definition) & {"oneOf", "anyOf", "not"}), 1)

    @unittest.skipUnless(shutil.which("node"), "needs node")
    def test_the_script_runs_on_what_the_page_holds(self):
        script = re.search(r"<script>(.*?)</script>", self.page, re.S)[1]
        data = {"script": script, "ids": re.findall(r'\bid="([^"]+)"', self.page),
                "schema": embedded(self.page, "schema-json"), "examples": embedded(self.page, "examples-json")}
        child = subprocess.run(["node", "-e", STUB], input=json.dumps(data), capture_output=True, text=True,
                               encoding="utf-8", check=False)
        self.assertEqual(child.returncode, 0, child.stderr)
        result = json.loads(child.stdout)
        self.assertEqual(sorted(result["chips"]), sorted(self.files))
        for name, file in self.files.items():
            with self.subTest(example=name):
                self.assertEqual(bool(result["merged"][name]), bool(file["defaults"]))
        written = "\n".join(result["html"].values())
        owners = (self.schema, *self.schema["$defs"].values(), self.schema["$defs"]["end"]["properties"]["location"])
        for key in {key for owner in owners for key in owner.get("properties", ())}:
            with self.subTest(field=key):
                self.assertIn(f"<code>{key}</code>", written)
        for anchor in re.findall(r'href="#([\w-]+)"', self.page + written):
            with self.subTest(anchor=anchor):
                self.assertRegex(self.page + written, rf'\bid="{anchor}"')
        targets = set(re.findall(r"\bset\('([\w-]+)'", script))
        self.assertGreaterEqual(len(targets), 10)
        for target in targets:
            html = result["html"][target]
            with self.subTest(target=target):
                self.assertTrue(html)
                # "undefined" is also a word the page uses: "where the other side is undefined".
                self.assertIsNone(re.search(r"(?<!is )\bundefined\b|\[object Object\]|\bNaN\b", html), html)


if __name__ == "__main__":
    unittest.main()
