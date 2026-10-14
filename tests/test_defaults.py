"""Folder defaults: the merge, reference rebasing, and reading them from folders."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

from literature_links import cli, companion, discovery

SOURCE = {"type": "pdf", "uri": "../book.pdf", "pin": {"type": "book", "title": "Notes", "url": "notes.html"}}


class TestMerge(unittest.TestCase):

    def test_written_members_win_and_objects_merge_at_any_depth(self):
        inherited = {"source": SOURCE, "kind": "lemma", "extensions": {"x.y": {"a": 1, "b": [1, 2]}}}
        written = {"kind": "theorem", "extensions": {"x.y": {"b": [3]}, "x.z": True}}
        self.assertEqual(companion.merge(inherited, written),
                         {"source": SOURCE, "kind": "theorem", "extensions": {"x.y": {"a": 1, "b": [3]}, "x.z": True}})

    def test_null_removes_an_inherited_member_and_is_kept_where_nothing_is_inherited(self):
        inherited = {"target": {"pin": {"type": "repository"}}, "extensions": {"x.y": {"a": 1}}}
        written = {"target": None, "extensions": {"x.y": {"a": None, "b": None}, "x.z": None}}
        self.assertEqual(companion.merge(inherited, written), {"extensions": {"x.y": {"b": None}, "x.z": None}})

    def test_a_written_object_replaces_an_inherited_non_object_as_written(self):
        self.assertEqual(companion.merge({"target": "a.html"}, {"target": {"uri": "b.html", "x": None}}),
                         {"target": {"uri": "b.html", "x": None}})

    def test_a_written_string_replaces_an_inherited_object(self):
        self.assertEqual(companion.merge({"target": {"pin": {"type": "repository"}}}, {"target": "A.html"}),
                         {"target": "A.html"})
        self.assertEqual(companion.merge({"status": {"pin": {"type": "repository"}}}, {"status": "partial"}),
                         {"status": "partial"})

    def test_arguments_are_not_changed_or_shared(self):
        inherited, written = {"a": {"b": [1]}}, {"a": {"c": {"d": 1}}}
        merged = companion.merge(inherited, written)
        merged["a"]["b"].append(2)
        merged["a"]["c"]["d"] = 2
        self.assertEqual((inherited, written), ({"a": {"b": [1]}}, {"a": {"c": {"d": 1}}}))


class TestRebase(unittest.TestCase):

    def test_relative_references_resolve_against_the_defaults_file(self):
        value = {"$schema": "schema.json", "source": SOURCE, "target": "site/A.html#a",
                 "location": {"profile": "#p", "fragment": "kept"},
                 "status": {"pin": {"type": "repository", "url": "?q"}}}
        rebased = companion.rebase(value, "../../_defaults.json")
        self.assertEqual(rebased["$schema"], "../../schema.json")
        self.assertEqual(rebased["source"]["uri"], "../../../book.pdf")
        self.assertEqual(rebased["source"]["pin"]["url"], "../../notes.html")
        self.assertEqual(rebased["target"], "../../site/A.html#a")
        self.assertEqual(rebased["location"], {"profile": "../../_defaults.json#p", "fragment": "kept"})
        self.assertEqual(rebased["status"]["pin"]["url"], "../../_defaults.json?q")
        self.assertEqual(value["source"]["uri"], "../book.pdf")

    def test_absolute_references_and_extension_strings_are_unchanged(self):
        value = {"source": {"uri": "https://example.org/a.pdf"},
                 "target": {"uri": "/site/A.html", "pin": {"url": "//example.org/r"}},
                 "extensions": {"x.y": "relative/path"}}
        self.assertEqual(companion.rebase(value, "../_defaults.json"), value)
        self.assertEqual(companion.rebase({"target": {"uri": "lean:Nat.add"}}, "../_defaults.json"),
                         {"target": {"uri": "lean:Nat.add"}})

    def test_target_and_its_pin_are_rebased_and_only_a_scheme_is_absolute(self):
        value = {"target": {"uri": "site/A.html", "pin": {"type": "repository", "url": "repo/"}}}
        self.assertEqual(companion.rebase(value, "../../_defaults.json")["target"],
                         {"uri": "../../site/A.html", "pin": {"type": "repository", "url": "../../repo/"}})
        self.assertEqual(companion.rebase({"target": "1.2:intro.html"}, "../_defaults.json"), {"target": "../1.2:intro.html"})
        self.assertEqual(companion.rebase({"target": "git+https://example.org/r"}, "../_defaults.json"),
                         {"target": "git+https://example.org/r"})

    def test_an_empty_reference_stays_empty(self):
        self.assertEqual(companion.rebase({"source": {"uri": ""}}, "../_defaults.json"), {"source": {"uri": ""}})

    def test_the_query_and_fragment_of_the_base_are_not_part_of_its_path(self):
        value = {"source": {"uri": "x.pdf"}, "target": "?q=2", "location": {"profile": "#p"}}
        self.assertEqual(companion.rebase(value, "https://example.org/c/_defaults.json?sig=a/b#top"),
                         {"source": {"uri": "https://example.org/c/x.pdf"},
                          "target": "https://example.org/c/_defaults.json?q=2",
                          "location": {"profile": "https://example.org/c/_defaults.json?sig=a/b#p"}})

    def test_a_defaults_file_in_the_same_folder_changes_only_same_document_references(self):
        value = {"source": {"uri": "book.pdf"}, "target": "#a"}
        self.assertEqual(companion.rebase(value, "_defaults.json"),
                         {"source": {"uri": "book.pdf"}, "target": "_defaults.json#a"})


class TestFolders(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / "companion"

    def write(self, relative: str, value: object, *, raw: bool = False) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if raw else json.dumps(value), encoding="utf-8")
        return path

    def test_annotations_below_a_defaults_file_inherit_its_members(self):
        defaults = self.write("_defaults.json", {"source": SOURCE, "kind": "theorem"})
        leaf = self.write("1.1/a.json", {"location": {"page": 3}, "target": "../site/A.html"})
        self.write("b.json", {"kind": "lemma", "target": "site/B.html"})
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [leaf, self.root / "b.json"])
        first, second = result.records
        self.assertEqual(first.defaults, (defaults,))
        self.assertEqual(first.annotation["source"]["uri"], "../../book.pdf")
        self.assertEqual(first.annotation["source"]["pin"]["url"], "../notes.html")
        self.assertEqual(first.annotation["kind"], "theorem")
        self.assertEqual(second.annotation["source"]["uri"], "../book.pdf")
        self.assertEqual(second.annotation["kind"], "lemma")

    def test_nested_defaults_apply_outermost_first_and_can_remove(self):
        self.write("_defaults.json", {"source": SOURCE, "status": "formalized", "target": {"pin": {"type": "repository"}}})
        inner = self.write("1.2/_defaults.json", {"status": "partial", "kind": "lemma"})
        self.write("1.2/a.json", {"target": None, "kind": "remark"})
        self.write("1.2/sub/b.json", {"target": {"uri": "../../B.html"}, "status": None})
        result = discovery.collect([self.root / "1.2"])
        self.assertEqual(result.problems, [])
        first, second = result.records
        self.assertEqual(first.annotation, {"source": {**SOURCE, "uri": "../../book.pdf", "pin": {
            **SOURCE["pin"], "url": "../notes.html"}}, "status": "partial", "kind": "remark"})
        self.assertEqual(second.defaults, (self.root / "_defaults.json", inner))
        self.assertNotIn("status", second.annotation)
        self.assertEqual(second.annotation["source"]["uri"], "../../../book.pdf")
        self.assertEqual(second.annotation["target"], {"pin": {"type": "repository"}, "uri": "../../B.html"})

    def test_a_null_in_a_defaults_file_removes_the_outer_default_and_is_kept_at_the_top(self):
        self.write("_defaults.json", {"source": SOURCE, "kind": "lemma", "note": None})
        self.write("1.2/_defaults.json", {"kind": None})
        self.write("1.2/a.json", {"note": "kept"})
        self.write("b.json", {})
        result = discovery.collect([self.root])
        record, = result.records
        self.assertEqual((record.path.name, "kind" in record.annotation, record.annotation["note"]),
                         ("a.json", False, "kept"))
        problem, = result.problems  # the outermost null has nothing to remove, so b.json keeps it
        self.assertEqual((problem.code, problem.path), ("SCHEMA", f"{self.root / 'b.json'}# $.note"))

    def test_only_a_file_spelled_exactly_is_a_defaults_file(self):
        self.write("_Defaults.json", {"source": SOURCE})
        self.write("a.json", {"target": "x.html"})
        result = discovery.collect([self.root])
        # On every file system it is an ordinary annotation file, and a.json inherits nothing.
        self.assertEqual([(record.path.name, record.defaults) for record in result.records], [("_Defaults.json", ())])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("SCHEMA", str(self.root / "a.json") + "# $")])
        (self.root / "sub" / "_Defaults.json").mkdir(parents=True)  # nor is a folder of that name a broken one
        self.write("sub/b.json", {"source": SOURCE})
        self.assertEqual([record.path.name for record in discovery.collect([self.root / "sub"]).records], ["b.json"])

    @unittest.skipIf(sys.platform == "win32" or getattr(os, "geteuid", lambda: 0)() == 0, "needs POSIX permissions")
    def test_a_folder_that_cannot_be_listed_still_gives_its_defaults(self):
        self.write("locked/_defaults.json", {"source": SOURCE})
        self.write("locked/inner/a.json", {})
        (self.root / "locked").chmod(0o111)
        self.addCleanup((self.root / "locked").chmod, 0o755)
        result = discovery.collect([self.root / "locked" / "inner"])
        self.assertEqual((len(result.records), result.problems), (1, []))

    def test_excluded_or_unselected_defaults_still_apply(self):
        self.write("_defaults.json", {"source": SOURCE})
        self.write("a.x.json", {})
        for options in ({"exclude": ["**/_defaults.json"]}, {"include": ["*.x.json"]}):
            with self.subTest(options=options):
                result = discovery.collect([self.root], **options)
                self.assertEqual((len(result.records), result.problems), (1, []))

    def test_scan_json_names_the_defaults_of_each_record(self):
        defaults = self.write("_defaults.json", {"source": SOURCE})
        self.write("1.1/a.json", {})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["scan", str(self.root), "--format", "json"]), 0)
        record, = json.loads(output.getvalue())["records"]
        self.assertEqual(record["origin"]["defaults"], [str(defaults)])

    def test_a_record_too_deep_to_merge_is_reported_and_the_others_are_read(self):
        self.write("_defaults.json", {"source": SOURCE})
        self.write("a.json", '{"extensions": {"x.y": ' + "[" * 600 + "]" * 600 + "}}", raw=True)
        self.write("b.json", {})
        result = discovery.collect([self.root])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("JSON", str(self.root / "a.json") + "#")])
        self.assertEqual([record.path for record in result.records], [self.root / "b.json"])
        annotation, _, problems = discovery.inherit(companion.loads((self.root / "a.json").read_text()), self.root / "a.json")
        self.assertEqual((annotation, [problem.code for problem in problems]), (None, ["JSON"]))

    def test_defaults_do_not_reach_sibling_folders(self):
        self.write("a/_defaults.json", {"source": SOURCE})
        self.write("b/c.json", {"target": "x.html"})
        result = discovery.collect([self.root])
        self.assertEqual([problem.code for problem in result.problems], ["SCHEMA"])

    def test_jsonl_rows_each_inherit(self):
        self.write("_defaults.json", {"source": SOURCE})
        self.write("a.json", {"location": {"page": 1}})
        self.write("b.jsonl", '{"location": {"page": 2}}\n{"location": {"page": 3}}\n', raw=True)
        self.write("c.ndjson", '{"location": {"page": 4}}\n', raw=True)
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual([record.annotation["location"]["page"] for record in result.records], [1, 2, 3, 4])
        self.assertTrue(all(record.annotation["source"]["uri"] == "../book.pdf" for record in result.records))

    def test_normalize_gives_merged_records_one_shape(self):
        pin = {"type": "repository", "url": "https://example.org/formal"}
        self.write("_defaults.json", {"source": SOURCE, "target": {"pin": pin}, "status": "formalized"})
        self.write("a.json", {"target": {"uri": "A.html"}})
        self.write("b.json", {"target": "B.html", "status": {"value": "partial"}})
        self.write("c.json", {"target": None})
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        a, b, c = (companion.normalize(record.annotation) for record in result.records)
        self.assertEqual((a["target"], a["status"]), ({"uri": "A.html", "pin": pin}, {"value": "formalized"}))
        # A written string replaces the inherited object, so b keeps no pin.
        self.assertEqual((b["target"], b["status"]), ({"uri": "B.html"}, {"value": "partial"}))
        self.assertEqual((c.get("target"), c["status"]), (None, {"value": "formalized"}))
        self.assertEqual([companion.validate(value) for value in (a, b, c)], [[], [], []])
        # Hence normalize after merging, not before.
        inherited, written = {"target": {"pin": pin}}, {"target": "B.html"}
        self.assertNotEqual(companion.merge(companion.normalize(inherited), companion.normalize(written)),
                            companion.normalize(companion.merge(inherited, written)))

    def test_problems_name_the_defaults_that_were_applied(self):
        self.write("_defaults.json", {"source": {"type": "pdf"}})
        self.write("a.json", {"location": {"page": 1}})
        problem, = discovery.collect([self.root]).problems
        self.assertEqual(problem.code, "SCHEMA")
        self.assertIn(str(self.root / "_defaults.json"), problem.message)

    def test_a_broken_defaults_file_is_reported_once_and_hides_its_records(self):
        self.write("_defaults.json", ["not", "an", "object"])
        self.write("a.json", {"source": SOURCE})
        self.write("b/c.json", {"source": SOURCE})
        result = discovery.collect([self.root])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("DEFAULTS", str(self.root / "_defaults.json"))])
        self.assertEqual(result.records, [])
        self.write("_defaults.json", "{", raw=True)
        self.assertEqual([problem.code for problem in discovery.collect([self.root]).problems], ["JSON"])

    def test_a_symlinked_defaults_file_is_a_problem(self):
        target = self.write("elsewhere.txt", {"source": SOURCE})
        self.write("x/a.json", {"location": {"page": 1}})
        try:
            (self.root / "x" / "_defaults.json").symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symbolic links are unavailable")
        result = discovery.collect([self.root / "x"])
        self.assertEqual([problem.code for problem in result.problems], ["SYMLINK"])

    def test_defaults_files_are_checked_but_never_read_as_annotations(self):
        self.write("_defaults.json", {"source": SOURCE})
        self.write("x/_defaults.json", 7)
        self.write("a.json", {})
        result = discovery.collect([self.root, self.root / "_defaults.json"])
        self.assertEqual([problem.code for problem in result.problems], ["DEFAULTS"])
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.files, [self.root / "a.json"])

    def test_a_record_without_defaults_is_read_as_written(self):
        self.write("a.json", {"source": SOURCE, "location": None})
        problem, = discovery.collect([self.root]).problems
        self.assertEqual(problem.code, "SCHEMA")

    def test_inherit_applies_the_folders_of_one_file(self):
        self.write("_defaults.json", {"source": SOURCE})
        leaf = self.write("1.1/a.json", {"kind": "lemma"})
        annotation, applied, problems = discovery.inherit({"kind": "lemma"}, leaf)
        self.assertEqual((applied, problems), ((self.root / "_defaults.json",), []))
        self.assertEqual(annotation["source"]["uri"], "../../book.pdf")

    def test_validate_applies_folder_defaults(self):
        self.write("_defaults.json", {"source": SOURCE})
        leaf = self.write("1.1/a.json", {"location": {"page": 2}})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["validate", str(leaf), "--format", "json"]), 0)
        report = json.loads(output.getvalue())
        self.assertEqual(report["defaults"], [str(self.root / "_defaults.json")])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["validate", str(self.root / "_defaults.json")]), 1)
        self.write("_defaults.json", [], raw=False)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["validate", str(leaf)]), 1)
        self.write("_defaults.json", "{", raw=True)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["validate", str(leaf)]), 2)

    def test_validate_names_the_defaults_behind_a_problem(self):
        defaults = self.write("_defaults.json", {"source": SOURCE, "location": {"page": 0}})
        leaf = self.write("a.json", {})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["validate", str(leaf)]), 1)
        self.assertIn(f"(with defaults from {defaults}) [SCHEMA]", output.getvalue())
        errors = io.StringIO()  # a problem of the installation is not one of the defaults
        with patch.object(companion, "SCHEMA_PATH", self.root / "missing.json"), redirect_stderr(errors):
            self.assertEqual(cli.main(["validate", str(leaf)]), 2)
        self.assertNotIn("with defaults from", errors.getvalue())


if __name__ == "__main__":
    unittest.main()
