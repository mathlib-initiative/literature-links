"""The conformance suite (conformance/) against the package.

``conformance/documents/manifest.json`` lists every document of the suite with
the exact problem and warning codes and paths the checker reports, whether
plain JSON Schema validation alone accepts it, and the CLI's exit status;
``conformance/canonical/cases.json`` pins the canonical writer.  Every entry
is run against the package here (the ``conformance/ids/`` vectors run in
tests/test_ids.py), and the manifest's own coverage is pinned: every code the
checker emits, every invariant, every profile, every source kind and every
regex-dialect trap has a document.  The Node side of the suite
(conformance/js/run.mjs) runs the same manifest against the schema with ajv.
"""
from __future__ import annotations

import importlib.util
import io
import json
import re
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import validate as V                              # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402
from formal_companion_annotations.schemacheck import Validator                      # noqa: E402

CONFORMANCE = ROOT / "conformance"
DOCUMENTS = CONFORMANCE / "documents"
MANIFEST = DOCUMENTS / "manifest.json"
CANONICAL_CASES = CONFORMANCE / "canonical" / "cases.json"
JS = CONFORMANCE / "js"
README = CONFORMANCE / "README.md"

#: The codes the checker emits (docs/annotations.md sections 9.3 to 9.5), every
#: one of which the manifest must cover at least once.
PROBLEM_CODES = frozenset({"SCHEMA", "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I11", "I12", "I13", "I14",
                           "L1"})
WARNING_CODES = frozenset({"W-CONFORMS", "W-MEDIA", "W-RELATION", "W-XREF", "W-NEWER", "W-SCHEMA-ID"})
#: Keys of a manifest entry: the fixed ones, and the optional flags.
ENTRY_KEYS = frozenset({"file", "valid", "schema_valid", "exit_status", "problems", "warnings", "note"})
OPTIONAL_KEYS = frozenset({"lints", "canonical", "unreadable", "known_divergence"})
#: Characters the traps use, built from code points so the source stays ASCII.
BOM = chr(0xFEFF)
FILE_SEPARATOR = chr(0x1C)
ARABIC_INDIC_ZERO = chr(0x660)
LINE_SEPARATOR = chr(0x2028)
PRIVATE_USE = chr(0xE000)
GRINNING_FACE = chr(0x1F600)


def load_manifest() -> list[dict]:
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert isinstance(entries, list) and entries
    return entries


def pairs(found: list[dict]) -> set[tuple[str, str]]:
    return {(p["code"], p["path"]) for p in found}


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            status = V.main(list(argv))
        except SystemExit as exc:
            status = exc.code
    return status, out.getvalue(), err.getvalue()


def cli_argv(entry: dict) -> list[str]:
    argv = [str(DOCUMENTS / entry["file"])]
    argv += [f"--lint={name}" for name in entry.get("lints", [])]
    if entry.get("canonical"):
        argv.append("--canonical")
    return argv


class TestTheManifest(unittest.TestCase):
    """Every entry of the manifest holds against the package."""

    @classmethod
    def setUpClass(cls):
        cls.entries = load_manifest()
        cls.schema = Validator(V.load_schema(V.SCHEMA_PATH))

    def test_every_document_is_listed_once_and_every_entry_exists(self):
        listed = [e["file"] for e in self.entries]
        self.assertEqual(len(listed), len(set(listed)), "a document is listed twice")
        on_disk = sorted(str(p.relative_to(DOCUMENTS)) for p in DOCUMENTS.glob("*/*.json"))
        self.assertEqual(sorted(listed), on_disk)
        self.assertEqual(sorted(p.name for p in DOCUMENTS.iterdir()), ["invalid", "manifest.json", "unreadable", "valid"])

    def test_the_entry_shapes(self):
        for entry in self.entries:
            with self.subTest(file=entry["file"]):
                keys = set(entry)
                self.assertTrue(ENTRY_KEYS <= keys, sorted(ENTRY_KEYS - keys))
                self.assertTrue(keys - ENTRY_KEYS <= OPTIONAL_KEYS, sorted(keys - ENTRY_KEYS - OPTIONAL_KEYS))
                head = entry["file"].split("/")[0]
                self.assertIn(head, ("valid", "invalid", "unreadable"))
                self.assertIsInstance(entry["valid"], bool)
                self.assertEqual(entry["valid"], head == "valid")
                self.assertEqual(entry.get("unreadable", False), head == "unreadable")
                self.assertIsInstance(entry["note"], str)
                self.assertTrue(entry["note"])
                for found in (entry["problems"], entry["warnings"]):
                    for p in found:
                        self.assertEqual(sorted(p), ["code", "path"])
                        self.assertTrue(p["path"].startswith("$"), p["path"])
                if head == "unreadable":
                    self.assertIsNone(entry["schema_valid"])
                    self.assertEqual(entry["exit_status"], 2)
                    self.assertEqual(pairs(entry["problems"]), {("IJSON", "$")})
                    self.assertEqual(entry["warnings"], [])
                else:
                    self.assertIsInstance(entry["schema_valid"], bool)
                    self.assertEqual(entry["exit_status"], 0 if entry["valid"] else 1)
                    self.assertEqual(entry["valid"], not entry["problems"])
                    self.assertTrue(set(entry.get("lints", [])) <= V.LINTS, entry.get("lints"))
                    codes = {p["code"] for p in entry["problems"]}
                    self.assertTrue(codes <= PROBLEM_CODES, codes - PROBLEM_CODES)
                    self.assertTrue({w["code"] for w in entry["warnings"]} <= WARNING_CODES)
                    # the lint and the canonical bytes are checked only when asked for
                    if "L1" in codes:
                        self.assertIn("external-urls", entry.get("lints", []))
                    if "I11" in codes:
                        self.assertTrue(entry.get("canonical"))

    def test_readable_documents_report_exactly_the_listed_problems_and_warnings(self):
        for entry in self.entries:
            if entry.get("unreadable"):
                continue
            with self.subTest(file=entry["file"]):
                data = (DOCUMENTS / entry["file"]).read_bytes()
                doc = V.loads(data)
                report = V.check(doc, text=data if entry.get("canonical") else None,
                                 canonical=bool(entry.get("canonical")), lints=entry.get("lints", ()))
                self.assertEqual(pairs([vars(p) for p in report.problems]), pairs(entry["problems"]),
                                 [f"{p} [{p.code}]" for p in report.problems])
                self.assertEqual(pairs([vars(w) for w in report.warnings]), pairs(entry["warnings"]),
                                 [f"{w} [{w.code}]" for w in report.warnings])
                self.assertEqual(report.ok, entry["valid"])
                # the listed order is the sorted one, so a diff reads well
                self.assertEqual(entry["problems"], sorted(entry["problems"], key=lambda p: (p["code"], p["path"])))

    def test_schema_valid_is_plain_schema_validation_alone(self):
        """What ajv (conformance/js/run.mjs) and schemacheck agree on: no invariant, no forward mode."""
        for entry in self.entries:
            if entry.get("unreadable"):
                continue
            with self.subTest(file=entry["file"]):
                doc = V.loads((DOCUMENTS / entry["file"]).read_bytes())
                errors = self.schema.errors(doc)
                self.assertEqual(not errors, entry["schema_valid"], errors[:3])

    def test_schema_valid_agrees_with_the_codes(self):
        """A SCHEMA problem means the schema rejects the document; a document the schema rejects and the
        checker accepts is a forward-mode one (W-NEWER); the schema accepts everything else."""
        for entry in self.entries:
            if entry.get("unreadable"):
                continue
            with self.subTest(file=entry["file"]):
                codes = {p["code"] for p in entry["problems"]}
                warnings = {w["code"] for w in entry["warnings"]}
                if "SCHEMA" in codes:
                    self.assertFalse(entry["schema_valid"])
                    self.assertEqual(codes, {"SCHEMA"}, "nothing runs after a schema failure")
                elif not entry["schema_valid"]:
                    self.assertIn("W-NEWER", warnings, "only forward mode accepts what the schema rejects")
                    self.assertTrue(entry["valid"])

    def test_the_cli_exit_status(self):
        for entry in self.entries:
            with self.subTest(file=entry["file"]):
                status, out, err = run_cli(*cli_argv(entry))
                self.assertEqual(status, entry["exit_status"], out + err)
                if entry.get("unreadable"):
                    self.assertEqual(out, "")
                    self.assertTrue(err.startswith(f"{DOCUMENTS / entry['file']}: cannot read: "), err)
                else:
                    self.assertEqual(err, "")
                    for p in entry["problems"]:
                        self.assertIn(f"{p['path']}: ", out)
                        self.assertIn(f" [{p['code']}]\n", out)
                    for w in entry["warnings"]:
                        self.assertIn(f": warning: {w['path']}: ", out)
                        self.assertIn(f" [{w['code']}]\n", out)
                    if entry["valid"]:
                        self.assertIn(": ok (", out)

    def test_unreadable_documents_are_refused_by_the_loader(self):
        for entry in self.entries:
            if not entry.get("unreadable"):
                continue
            with self.subTest(file=entry["file"]):
                data = (DOCUMENTS / entry["file"]).read_bytes()
                with self.assertRaises(V.LoadError):
                    V.loads(data)

    def test_valid_documents_are_in_canonical_form(self):
        for entry in self.entries:
            if not entry["valid"]:
                continue
            with self.subTest(file=entry["file"]):
                data = (DOCUMENTS / entry["file"]).read_bytes()
                self.assertEqual(data, V.canonical_dumps(V.canonicalize(V.loads(data))).encode("utf-8"))
                self.assertEqual(V.check(V.loads(data), text=data, canonical=True).problems, [])

    def test_the_documents_are_small_and_synthetic(self):
        for entry in self.entries:
            with self.subTest(file=entry["file"]):
                data = (DOCUMENTS / entry["file"]).read_bytes()
                self.assertLess(len(data), 8000)
                self.assertLessEqual(data.count(b"\n"), 150)
                if not entry.get("unreadable"):
                    self.assertIn(b"example.org", data, "a synthetic document lives at example.org")


class TestWhatTheManifestCovers(unittest.TestCase):
    """The suite covers every code, invariant, profile, source kind and trap it promises."""

    @classmethod
    def setUpClass(cls):
        cls.entries = load_manifest()
        cls.readable = [e for e in cls.entries if not e.get("unreadable")]
        cls.docs = {e["file"]: V.loads((DOCUMENTS / e["file"]).read_bytes()) for e in cls.readable}

    def problem_paths(self, code: str) -> set[tuple[str, str]]:
        return {(e["file"], p["path"]) for e in self.readable for p in e["problems"] if p["code"] == code}

    def test_every_code_at_least_once(self):
        problems = {p["code"] for e in self.readable for p in e["problems"]}
        warnings = {w["code"] for e in self.readable for w in e["warnings"]}
        self.assertEqual(problems, PROBLEM_CODES)
        self.assertEqual(warnings, WARNING_CODES)
        self.assertGreaterEqual(sum(1 for e in self.entries if e.get("unreadable")), 5, "IJSON: the unreadable cases")

    def test_the_rewritten_i5_rules(self):
        """Rules 2, 3, 4 (each coverage class that excludes a key link), 5 and 6, each with its own document."""
        files = {f for f, _p in self.problem_paths("I5")}
        for name in ("invalid/coverage-missing.json", "invalid/attributed-without-key.json",
                     "invalid/formalized-without-key.json", "invalid/partial-only-with-key.json",
                     "invalid/private-only-public-key.json", "invalid/private-only-key-to-cluster.json",
                     "invalid/private-only-without-link.json",
                     "invalid/not-formalized-with-attributed.json", "invalid/out-of-scope-with-key.json",
                     "invalid/coverage-note-without-coverage.json"):
            self.assertIn(name, files)
        self.assertIn(("invalid/coverage-note-without-coverage.json", "$.items[0].coverage_note"), self.problem_paths("I5"))

    def test_i14_for_each_profile(self):
        arrays = {path for _f, path in self.problem_paths("I14")}
        for name, owned in V.PROFILES.items():
            with self.subTest(profile=name):
                self.assertTrue(any(f"$.{array}" in arrays for array in owned["arrays"]), name)
        self.assertIn(("invalid/profile-destination-artifact-needs-graph.json", "$.destinations[0].artifact"),
                      self.problem_paths("I14"))

    def test_the_regex_dialect_traps(self):
        def doc_text(name: str) -> str:
            return (DOCUMENTS / name).read_text(encoding="utf-8")
        self.assertIn('\\n"', doc_text("invalid/trap-id-trailing-newline.json"))
        self.assertIn(BOM, doc_text("invalid/trap-id-bom.json"))
        self.assertIn("\\u001c", doc_text("invalid/trap-id-file-separator.json"))
        commit = self.docs["invalid/trap-commit-trailing-newline.json"]["companion"]["commit"]
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}\n", commit))
        self.assertEqual(self.docs["invalid/trap-version-trailing-newline.json"]["schema_version"], "1.0\n")
        value = self.docs["invalid/trap-page-non-ascii-digit.json"]["locations"][0]["target"]["selector"][0]["value"]
        self.assertEqual(value, "page=1" + ARABIC_INDIC_ZERO)
        for name in ("invalid/trap-id-trailing-newline.json", "invalid/trap-id-bom.json",
                     "invalid/trap-id-file-separator.json", "invalid/trap-commit-trailing-newline.json",
                     "invalid/trap-version-trailing-newline.json"):
            entry = next(e for e in self.entries if e["file"] == name)
            self.assertEqual({p["code"] for p in entry["problems"]}, {"SCHEMA"}, name)
            self.assertFalse(entry["schema_valid"], name)
        readme = README.read_text(encoding="utf-8")                 # a Python-re validator accepts three of them
        self.assertIn("before a final newline", readme)
        self.assertIn("trap-*-trailing-newline", readme)

    def test_one_valid_document_per_profile_and_one_with_all_four(self):
        declared = {f: set(d.get("profiles", {})) for f, d in self.docs.items() if f.startswith("valid/")}
        for name in vocab.ANNOTATION_PROFILES:
            with self.subTest(profile=name):
                self.assertIn(f"valid/profile-{name}.json", declared)
                self.assertEqual(declared[f"valid/profile-{name}.json"], {name})
        self.assertEqual(declared["valid/all-profiles.json"], set(vocab.ANNOTATION_PROFILES))
        used = self.docs["valid/all-profiles.json"]
        for owned in V.PROFILES.values():
            for array in owned["arrays"]:
                self.assertIn(array, used)

    def test_one_valid_document_per_source_kind(self):
        kinds = {}
        for f, d in self.docs.items():
            if f.startswith("valid/"):
                for s in d["sources"]:
                    kinds.setdefault((s["kind"], s.get("scope", "page")), f)
        for want in (("pdf", "page"), ("web", "page"), ("web", "site"), ("tex", "page"), ("lean", "page"),
                     ("other", "page")):
            with self.subTest(kind=want):
                self.assertIn(want, kinds)
        selectors = set()

        def walk(sel: dict) -> None:
            selectors.add(sel["type"])
            if "refinedBy" in sel:
                walk(sel["refinedBy"])
        for f, d in self.docs.items():
            if f.startswith("valid/"):
                for loc in d.get("locations", []):
                    for sel in loc["target"]["selector"]:
                        walk(sel)
        self.assertEqual(selectors, vocab.ANNOTATION_SELECTOR_TYPES)

    def test_i4_identifiers_only_sources_a_core_role_and_a_primed_sub(self):
        """I4 on a passage, with its numbered twin valid; a pdf pinned by identifiers alone, valid with a page=
        fragment and invalid with a region; a source role with no profile; a sub with a prime."""
        self.assertEqual(self.docs["invalid/unanchored-item.json"]["items"][0]["form"], "passage")
        self.assertIn(("invalid/unanchored-item.json", "$.items[0]"), self.problem_paths("I4"))
        twin = self.docs["valid/numbered-item-without-anchor.json"]
        self.assertEqual(twin["items"][0]["form"], "numbered")
        self.assertFalse({"pages", "quote"} & set(twin["items"][0]))
        self.assertNotIn("locations", twin)
        for name in ("valid/source-pdf-by-identifiers.json", "invalid/region-without-bytes.json"):
            source = self.docs[name]["sources"][0]
            self.assertEqual((source["kind"], "sha256" in source, "identifiers" in source), ("pdf", False, True))
        self.assertIn(("invalid/region-without-bytes.json", "$.locations[0].target.selector[0]"),
                      self.problem_paths("I7"))
        role = self.docs["valid/source-role-core.json"]
        self.assertNotIn("profiles", role)
        self.assertEqual(role["sources"][0]["role"], "audited")
        self.assertEqual({p["path"] for p in next(e for e in self.entries
                                                  if e["file"] == "invalid/profile-audit-undeclared.json")["problems"]},
                         {"$.verdicts"})
        prime = self.docs["valid/sub-with-prime.json"]
        self.assertEqual((prime["items"][0]["sub"], prime["items"][0]["id"], prime["links"][0]["sub"]),
                         ("b'", "exercise-1.4-b'", "b'"))

    def test_the_forward_mode_document(self):
        entry = next(e for e in self.entries if e["file"] == "valid/newer-minor.json")
        self.assertTrue(entry["valid"])
        self.assertFalse(entry["schema_valid"])
        self.assertEqual(pairs(entry["warnings"]), {("W-NEWER", "$.schema_version"), ("W-NEWER", "$.items[0].future_field")})
        self.assertEqual(self.docs["valid/newer-minor.json"]["schema_version"], "1.7")

    def test_the_lint_documents(self):
        linted = [e for e in self.entries if e.get("lints")]
        self.assertTrue(any(e["valid"] for e in linted), "a valid document with URLs at the exempt paths")
        self.assertTrue(any("L1" in {p["code"] for p in e["problems"]} for e in linted))
        for entry in linted:
            with self.subTest(file=entry["file"]):
                doc = self.docs[entry["file"]]
                without = V.check(doc)
                self.assertTrue(without.ok, "a lint never affects validity")


class TestTheCanonicalCases(unittest.TestCase):
    """conformance/canonical/cases.json against the reference writer."""

    @classmethod
    def setUpClass(cls):
        # A plain parser: the writer is defined on any JSON value, 1e20 included (section 9.1 keeps
        # such integers out of a valid document, but a writer still spells them).
        cls.cases = json.loads(CANONICAL_CASES.read_text(encoding="utf-8"))

    def test_the_shapes(self):
        names = [c["name"] for c in self.cases]
        self.assertEqual(len(names), len(set(names)))
        for c in self.cases:
            with self.subTest(name=c["name"]):
                self.assertEqual(sorted(c), ["canonical", "input", "name"])
                self.assertIsInstance(c["canonical"], str)
                self.assertTrue(c["canonical"].endswith("\n"))
                self.assertFalse(c["canonical"].endswith("\n\n"))
                self.assertNotIn("\r", c["canonical"])

    def test_every_case(self):
        for c in self.cases:
            with self.subTest(name=c["name"]):
                self.assertEqual(V.canonical_dumps(c["input"]), c["canonical"])
                # the text parses back to the input (-0 and 1.0 compare equal to 0 and 1)
                self.assertEqual(json.loads(c["canonical"]), c["input"])

    def test_the_number_boundaries_of_section_10(self):
        inputs = [c["input"] for c in self.cases]
        for value in (1e21, 1e-7, 5e-324, 9007199254740991, 0.30000000000000004, 100000000000000000000):
            with self.subTest(value=value):
                self.assertIn(value, inputs)
        texts = {c["canonical"] for c in self.cases}
        for text in ("1e+21\n", "1e-7\n", "5e-324\n", "9007199254740991\n", "0.30000000000000004\n",
                     "100000000000000000000\n", "1\n", "0\n"):
            self.assertIn(text, texts)
        self.assertTrue(any(isinstance(c["input"], float) and c["input"] == 0 and c["canonical"] == "0\n"
                            for c in self.cases), "-0 is written 0")
        self.assertTrue(any(c["input"] == 1.0 and isinstance(c["input"], float) for c in self.cases), "1.0 -> 1")

    def test_the_string_and_key_cases_of_section_10(self):
        texts = "".join(c["canonical"] for c in self.cases)
        self.assertIn('"\\u0000\\u0001\\u001f"', texts)
        self.assertIn('"\\b\\f\\n\\r\\t"', texts)
        self.assertIn('"a\\"b\\\\c"', texts)
        self.assertIn(LINE_SEPARATOR, texts)
        self.assertIn(GRINNING_FACE, texts)
        objects = [c for c in self.cases if isinstance(c["input"], dict)]
        # an astral key before a U+E000 key, by UTF-16 code units
        astral_first = next(c for c in objects if set(c["input"]) == {PRIVATE_USE, GRINNING_FACE})
        self.assertLess(astral_first["canonical"].index(GRINNING_FACE), astral_first["canonical"].index(PRIVATE_USE))
        integer_like = next(c for c in objects if set(c["input"]) == {"10", "9", "a"})
        self.assertEqual(integer_like["canonical"], '{\n  "10": 1,\n  "9": 2,\n  "a": 3\n}\n')
        self.assertIn('{\n  "a": {},\n  "b": []\n}\n', texts)


class TestTheSuiteIsWiredUp(unittest.TestCase):
    """The README cites what is here, the Node side is pinned, CI runs it, the sdist carries it."""

    def test_the_readme_cites_paths_that_exist(self):
        text = README.read_text(encoding="utf-8")
        for span in re.findall(r"`([^`\n]+)`", text):
            for token in span.split():
                token = token.strip(",;:()")
                if not token.startswith(("conformance/", "docs/", "schema/", "examples/", "tests/", ".github/")):
                    continue
                keep = []
                for part in Path(token).parts:
                    if any(ch in part for ch in "<*"):
                        break
                    keep.append(part)
                with self.subTest(path=token):
                    self.assertNotIn("node_modules", token, f"README cites {token}, which git ignores: a fresh "
                                                            f"checkout and the sdist have no such path")
                    self.assertTrue((ROOT / Path(*keep)).exists(), f"README cites {token}, which is not here")
        self.assertIn("docs/id-algorithm.md", text)
        self.assertIn("python3 -m pytest tests/test_conformance.py", text)
        self.assertIn("node conformance/js/run.mjs", text)
        self.assertNotIn(chr(0x2014), text)

    def test_the_node_runner_is_pinned(self):
        package = json.loads((JS / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["type"], "module")
        self.assertTrue(package["private"])
        self.assertTrue(package["dependencies"]["ajv"].startswith("^8."))
        self.assertIn("ajv-formats", package["dependencies"])
        self.assertNotIn("scripts", {k for k in package.get("scripts", {}) if k.endswith("install")})
        self.assertTrue((JS / "package-lock.json").is_file(), "npm ci needs the lock file")
        for name in ("run.mjs", "canonical.mjs"):
            self.assertTrue((JS / name).is_file())
        gitignore = ROOT / ".gitignore"                  # absent from an sdist, which carries no node_modules
        if gitignore.is_file():
            self.assertIn("conformance/js/node_modules/", gitignore.read_text(encoding="utf-8"))

    def test_ci_runs_the_node_side_and_the_sdist_carries_the_suite(self):
        workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn("conformance-node:", workflow)
        self.assertIn("actions/setup-node@v4", workflow)
        self.assertIn("node conformance/js/run.mjs", workflow)
        self.assertIn("npm ci", workflow)
        self.assertIn("the sdist carries the conformance suite and no node_modules", workflow)
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
        self.assertIn("graft conformance\n", manifest)
        self.assertIn("prune conformance/js/node_modules\n", manifest, "a maintainer's tree has one after npm ci")


if __name__ == "__main__":
    unittest.main()
