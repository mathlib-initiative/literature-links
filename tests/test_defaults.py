"""Folder defaults: the merge, end templates, reference rebasing, and reading them from folders."""
from __future__ import annotations

import copy
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

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "companion"
MATHLIB = "https://github.com/leanprover-community/mathlib4"
COMMIT = "db584cd6d46c92f209a44c0f1c829460d327499d"
SHA256 = "6c6a04b64488546e49f0ebb4c6310bb091487b5861b5b525985faec6e80c2e7f"
# End templates: the members the ends of a side share.
SUBJECT = {"type": "pdf", "uri": "../book.pdf", "sha256": SHA256,
           "citation": {"id": "notes", "type": "book", "URL": "notes.html"}}
OBJECT = {"type": "lean", "uri": MATHLIB, "version": COMMIT}


class TestMerge(unittest.TestCase):

    def test_written_members_win_and_objects_merge_at_any_depth(self):
        inherited = {"subject": [SUBJECT], "kind": "lemma", "extensions": {"x.y": {"a": 1, "b": [1, 2]}}}
        written = {"kind": "theorem", "extensions": {"x.y": {"b": [3]}, "x.z": True}}
        self.assertEqual(companion.merge(inherited, written),
                         {"subject": [SUBJECT], "kind": "theorem",
                          "extensions": {"x.y": {"a": 1, "b": [3]}, "x.z": True}})

    def test_null_removes_an_inherited_member_and_is_kept_where_nothing_is_inherited(self):
        inherited = {"status": "partial", "extensions": {"x.y": {"a": 1}}}
        written = {"status": None, "extensions": {"x.y": {"a": None, "b": None}, "x.z": None}}
        self.assertEqual(companion.merge(inherited, written), {"extensions": {"x.y": {"b": None}, "x.z": None}})

    def test_a_written_object_replaces_an_inherited_non_object_as_written(self):
        self.assertEqual(companion.merge({"note": "a"}, {"note": {"text": "b", "x": None}}),
                         {"note": {"text": "b", "x": None}})

    def test_a_written_string_or_list_replaces_an_inherited_object(self):
        self.assertEqual(companion.merge({"status": {"value": "formalized"}}, {"status": "partial"}),
                         {"status": "partial"})
        self.assertEqual(companion.merge({"extensions": {"x.y": {"a": 1}}}, {"extensions": {"x.y": [1]}}),
                         {"extensions": {"x.y": [1]}})

    def test_defaults_is_a_keyword(self):
        with self.assertRaises(TypeError):
            companion.merge({}, {}, True)

    def test_arguments_are_not_changed_or_shared(self):
        inherited = {"a": {"b": [1]}, "subject": copy.deepcopy(SUBJECT)}
        written = {"a": {"c": {"d": 1}}, "subject": [{"location": {"page": 2}}], "object": [{"uri": "x", "e": [1]}]}
        before = copy.deepcopy((inherited, written))
        merged = companion.merge(inherited, written)
        merged["a"]["b"].append(2)
        merged["a"]["c"]["d"] = 2
        merged["subject"][0]["citation"]["id"] = "changed"
        merged["subject"][0]["location"]["page"] = 3
        merged["object"][0]["e"].append(2)
        self.assertEqual((inherited, written), before)


class TestEndTemplates(unittest.TestCase):

    def test_a_template_fills_each_end_without_a_uri(self):
        merged = companion.merge({"subject": SUBJECT, "object": OBJECT},
                                 {"subject": [{"location": {"page": 7}, "title": "Theorem 1.4"}, {}],
                                  "object": [{"location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}]})
        self.assertEqual(merged, {
            "subject": [{**SUBJECT, "location": {"page": 7}, "title": "Theorem 1.4"}, SUBJECT],
            "object": [{**OBJECT, "location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}]})
        self.assertEqual(list(merged["subject"][0]), ["type", "uri", "sha256", "citation", "location", "title"])
        self.assertEqual(companion.validate(merged), [])

    def test_an_end_with_its_own_uri_takes_nothing_from_the_template(self):
        errata = {"type": "pdf", "uri": "../errata.pdf", "location": {"page": 1}}
        self.assertEqual(companion.merge({"subject": SUBJECT}, {"subject": [errata], "object": []}),
                         {"subject": [errata], "object": []})
        # Even a uri of null or the template's own value makes the end complete as written.
        for end in ({"uri": None, "location": {"page": 1}}, {"uri": SUBJECT["uri"]}):
            with self.subTest(end=end):
                self.assertEqual(companion.merge({"subject": SUBJECT}, {"subject": [end]})["subject"], [end])

    def test_a_location_on_the_end_replaces_the_template_location_whole(self):
        template = {**SUBJECT, "location": {"page": 1, "rect": [0, 0, 1, 0.5]}}
        merged = companion.merge({"subject": template},
                                 {"subject": [{"location": {"page": 2, "quote": {"exact": "a"}}}]})
        self.assertEqual(merged["subject"][0]["location"], {"page": 2, "quote": {"exact": "a"}})
        lean = {**OBJECT, "location": {"module": "Mathlib.GroupTheory.Coset.Card", "lines": [70]}}
        merged = companion.merge({"object": lean}, {"object": [{"location": {"declaration": "Subgroup.index"}}]})
        self.assertEqual(merged["object"][0]["location"], {"declaration": "Subgroup.index"})
        # An end without a location keeps the template's.
        self.assertEqual(companion.merge({"object": lean}, {"object": [{}]})["object"], [lean])

    def test_null_on_an_end_removes_a_template_member(self):
        template = {**SUBJECT, "location": {"page": 1}, "identifiers": {"wikidata": "Q1", "arxiv": "0000.00000"}}
        merged = companion.merge({"subject": template},
                                 {"subject": [{"sha256": None, "location": None, "identifiers": {"arxiv": None},
                                               "title": None}]})
        expected = {key: value for key, value in template.items() if key not in ("sha256", "location")}
        expected["identifiers"] = {"wikidata": "Q1"}
        expected["title"] = None  # nothing to remove, so it is kept, and the record is invalid
        self.assertEqual(merged["subject"], [expected])
        self.assertTrue(companion.validate({**merged, "object": []}))

    def test_objects_inside_an_end_merge_member_by_member(self):
        template = {**SUBJECT, "identifiers": {"wikidata": "Q1"}, "extensions": {"x.y": {"a": 1}}}
        merged = companion.merge({"subject": template},
                                 {"subject": [{"identifiers": {"arxiv": "0000.00000"}, "extensions": {"x.y": {"b": 2}},
                                               "citation": {"title": "Notes"}}]})
        end, = merged["subject"]
        self.assertEqual(end["identifiers"], {"wikidata": "Q1", "arxiv": "0000.00000"})
        self.assertEqual(end["extensions"], {"x.y": {"a": 1, "b": 2}})
        self.assertEqual(end["citation"], {**SUBJECT["citation"], "title": "Notes"})

    def test_a_side_left_out_is_the_template_alone(self):
        merged = companion.merge({"subject": SUBJECT, "object": OBJECT}, {"subject": [{"location": {"page": 9}}],
                                                                          "relation": "noMatch"})
        self.assertEqual(merged["object"], [OBJECT])
        self.assertEqual(companion.validate(merged), [])
        self.assertEqual(companion.merge({"subject": SUBJECT, "object": OBJECT}, {}),
                         {"subject": [SUBJECT], "object": [OBJECT]})

    def test_an_explicit_empty_side_stays_empty(self):
        merged = companion.merge({"subject": SUBJECT, "object": OBJECT}, {"subject": [{}], "object": []})
        self.assertEqual(merged["object"], [])
        self.assertEqual(companion.validate(merged), [])

    def test_items_that_are_not_objects_are_kept_as_written(self):
        items = ["../book.pdf", None, 3, [{"location": {"page": 1}}], True]
        merged = companion.merge({"subject": SUBJECT}, {"subject": [*items, {}]})
        self.assertEqual(merged["subject"], [*items, SUBJECT])

    def test_a_side_written_as_an_object_merges_and_stays_invalid(self):
        merged = companion.merge({"subject": SUBJECT}, {"subject": {"location": {"page": 9}}, "object": []})
        self.assertEqual(merged["subject"], {**SUBJECT, "location": {"page": 9}})
        self.assertEqual([problem.path for problem in companion.check(merged).problems], ["$.subject"])
        # Without defaults nothing wraps it either.
        self.assertEqual(companion.merge({}, {"subject": SUBJECT, "object": []})["subject"], SUBJECT)

    def test_a_null_side_removes_the_template(self):
        self.assertEqual(companion.merge({"subject": SUBJECT, "object": OBJECT}, {"object": None}),
                         {"subject": [SUBJECT]})

    def test_an_inherited_list_is_replaced_or_kept_but_never_a_template(self):
        inherited = {"subject": [SUBJECT], "object": []}
        self.assertEqual(companion.merge(inherited, {"subject": [{"location": {"page": 1}}]}),
                         {"subject": [{"location": {"page": 1}}], "object": []})
        self.assertEqual(companion.merge(inherited, {}), inherited)

    def test_two_defaults_files_merge_member_by_member(self):
        outer = {"subject": SUBJECT, "object": {**OBJECT, "location": {"module": "Mathlib.GroupTheory.Coset.Card"}}}
        inner = {"object": {"location": {"declaration": "Subgroup.card_subgroup_dvd_card"}, "role": "states"},
                 "kind": "theorem"}
        merged = companion.merge(outer, inner, defaults=True)
        # Both stay templates, and two templates merge as any two objects do, location included.
        self.assertEqual(merged, {"subject": SUBJECT, "kind": "theorem",
                                  "object": {**OBJECT, "location": {"module": "Mathlib.GroupTheory.Coset.Card",
                                                                    "declaration": "Subgroup.card_subgroup_dvd_card"},
                                             "role": "states"}})
        self.assertEqual(list(merged), ["subject", "object", "kind"])
        record = companion.merge(merged, {"subject": [{"location": {"page": 7}}]})
        self.assertEqual(record["object"], [merged["object"]])
        self.assertEqual(companion.validate(record), [])

    def test_a_defaults_list_over_a_template_is_completed_from_it(self):
        merged = companion.merge({"subject": SUBJECT}, {"subject": [{"location": {"page": 1}}, {"uri": "x.pdf"}]},
                                 defaults=True)
        self.assertEqual(merged["subject"], [{**SUBJECT, "location": {"page": 1}}, {"uri": "x.pdf"}])

    def test_the_rule_is_only_for_the_top_level_sides(self):
        inherited = {"extensions": {"subject": {"a": 1}, "object": {"b": 2}},
                     "note": "x", "citation": {"subject": {"a": 1}}}
        written = {"extensions": {"subject": [{"c": 3}]}, "citation": {"subject": [{"c": 3}]}}
        self.assertEqual(companion.merge(inherited, written),
                         {"extensions": {"subject": [{"c": 3}], "object": {"b": 2}},
                          "note": "x", "citation": {"subject": [{"c": 3}]}})
        # Inside an end, a member named like a side is an ordinary member.
        template = {**SUBJECT, "extensions": {"object": {"a": 1}}}
        end, = companion.merge({"subject": template}, {"subject": [{"extensions": {"object": [{"b": 2}]}}]})["subject"]
        self.assertEqual(end["extensions"], {"object": [{"b": 2}]})

    def test_the_specification_example_reads_as_written_there(self):
        defaults = {"subject": {"type": "pdf", "uri": "../notes.pdf", "sha256": SHA256}, "object": OBJECT}
        record = {"subject": [{"location": {"page": 7}, "title": "Theorem 1.4 (Lagrange)"},
                              {"type": "pdf", "uri": "../errata.pdf", "location": {"page": 1}}],
                  "object": [{"location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}],
                  "relation": "broadMatch"}
        expected = {"subject": [{"type": "pdf", "uri": "../notes.pdf", "sha256": SHA256, "location": {"page": 7},
                                 "title": "Theorem 1.4 (Lagrange)"},
                                {"type": "pdf", "uri": "../errata.pdf", "location": {"page": 1}}],
                    "object": [{**OBJECT, "location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}],
                    "relation": "broadMatch"}
        merged = companion.merge(companion.merge({}, defaults, defaults=True), record)
        self.assertEqual(json.dumps(merged), json.dumps(expected))


class TestRebase(unittest.TestCase):

    def test_relative_references_in_a_template_resolve_against_the_defaults_file(self):
        value = {"$schema": "schema.json", "subject": {**SUBJECT, "location": {"profile": "#p", "fragment": "kept"}},
                 "object": {"type": "lean", "uri": "..", "version": "a/b", "location": {"declaration": "a/b"}}}
        rebased = companion.rebase(value, "../../_defaults.json")
        self.assertEqual(rebased["$schema"], "../../schema.json")
        self.assertEqual(rebased["subject"]["uri"], "../../../book.pdf")
        self.assertEqual(rebased["subject"]["location"], {"profile": "../../_defaults.json#p", "fragment": "kept"})
        self.assertEqual(rebased["object"], {"type": "lean", "uri": "../../..", "version": "a/b",
                                             "location": {"declaration": "a/b"}})
        self.assertEqual(value["subject"]["uri"], "../book.pdf")

    def test_every_end_of_a_list_is_rebased(self):
        value = {"subject": [{"uri": "a.pdf"}, {"uri": "https://example.org/b.pdf"}, "c.pdf", None,
                             {"location": {"profile": "p.json"}}, {"uri": "", "location": None}],
                 "object": [{"uri": "?q", "location": {"profile": "urn:x"}}]}
        self.assertEqual(companion.rebase(value, "../_defaults.json"),
                         {"subject": [{"uri": "../a.pdf"}, {"uri": "https://example.org/b.pdf"}, "c.pdf", None,
                                      {"location": {"profile": "../p.json"}}, {"uri": "", "location": None}],
                          "object": [{"uri": "../_defaults.json?q", "location": {"profile": "urn:x"}}]})

    def test_citations_identifiers_and_extension_strings_are_unchanged(self):
        end = {"uri": "https://example.org/a.pdf", "citation": {"id": "a", "type": "book", "URL": "notes.html"},
               "identifiers": {"local": "relative/id"}, "extensions": {"x.y": "relative/path"}}
        value = {"subject": end, "object": [end], "extensions": {"x.y": "relative/path", "uri": "a.pdf"},
                 "note": "a.pdf", "id": "a.pdf"}
        self.assertEqual(companion.rebase(value, "../_defaults.json"), value)

    def test_absolute_references_and_only_a_scheme_is_absolute(self):
        for reference, expected in (("/site/A.html", "/site/A.html"), ("//example.org/r", "//example.org/r"),
                                    ("lean:Nat.add", "lean:Nat.add"),
                                    ("git+https://example.org/r", "git+https://example.org/r"),
                                    ("1.2:intro.html", "../1.2:intro.html"), ("site/A.html", "../site/A.html")):
            with self.subTest(reference=reference):
                self.assertEqual(companion.rebase({"object": [{"uri": reference}]}, "../_defaults.json"),
                                 {"object": [{"uri": expected}]})

    def test_an_empty_reference_stays_empty(self):
        self.assertEqual(companion.rebase({"subject": {"uri": ""}}, "../_defaults.json"), {"subject": {"uri": ""}})

    def test_the_query_and_fragment_of_the_base_are_not_part_of_its_path(self):
        value = {"subject": {"uri": "x.pdf", "location": {"profile": "#p"}}, "object": [{"uri": "?q=2"}]}
        self.assertEqual(companion.rebase(value, "https://example.org/c/_defaults.json?sig=a/b#top"),
                         {"subject": {"uri": "https://example.org/c/x.pdf",
                                      "location": {"profile": "https://example.org/c/_defaults.json?sig=a/b#p"}},
                          "object": [{"uri": "https://example.org/c/_defaults.json?q=2"}]})

    def test_a_defaults_file_in_the_same_folder_changes_only_same_document_references(self):
        value = {"subject": {"uri": "book.pdf"}, "object": [{"uri": "#a"}]}
        self.assertEqual(companion.rebase(value, "_defaults.json"),
                         {"subject": {"uri": "book.pdf"}, "object": [{"uri": "_defaults.json#a"}]})


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
        defaults = self.write("_defaults.json", {"subject": SUBJECT, "object": [], "kind": "theorem"})
        leaf = self.write("1.1/a.json", {"subject": [{"location": {"page": 3}}]})
        self.write("b.json", {"kind": "lemma"})
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [leaf, self.root / "b.json"])
        first, second = result.records
        self.assertEqual(first.defaults, (defaults,))
        self.assertEqual(first.annotation["subject"][0]["uri"], "../../book.pdf")
        self.assertEqual(first.annotation["subject"][0]["citation"]["URL"], "notes.html")  # not a reference
        self.assertEqual(first.annotation["subject"][0]["location"], {"page": 3})
        self.assertEqual((first.annotation["object"], first.annotation["kind"]), ([], "theorem"))
        self.assertEqual(second.annotation["subject"], [{**SUBJECT, "uri": "../book.pdf"}])
        self.assertEqual(second.annotation["kind"], "lemma")

    def test_nested_defaults_apply_outermost_first_and_can_remove(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": OBJECT, "status": "formalized"})
        inner = self.write("1.2/_defaults.json", {"status": "partial", "kind": "lemma",
                                                  "object": {"location": {"module": "Mathlib.GroupTheory.Coset.Card"}}})
        self.write("1.2/a.json", {"object": [], "kind": "remark"})
        self.write("1.2/sub/b.json", {"object": [{"location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}],
                                      "status": None})
        self.write("1.2/sub/c.json", {"relation": "relatedMatch"})
        result = discovery.collect([self.root / "1.2"])
        self.assertEqual(result.problems, [])
        first, second, third = result.records
        self.assertEqual(first.annotation, {"subject": [{**SUBJECT, "uri": "../../book.pdf"}], "object": [],
                                            "status": "partial", "kind": "remark"})
        self.assertEqual(second.defaults, (self.root / "_defaults.json", inner))
        self.assertNotIn("status", second.annotation)
        self.assertEqual(second.annotation["subject"][0]["uri"], "../../../book.pdf")
        self.assertEqual(second.annotation["object"],
                         [{**OBJECT, "location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}])
        self.assertEqual(third.annotation["object"],
                         [{**OBJECT, "location": {"module": "Mathlib.GroupTheory.Coset.Card"}}])

    def test_a_list_in_an_inner_defaults_file_is_completed_from_an_outer_template(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("1/_defaults.json", {"subject": [{"location": {"page": 4}}]})
        self.write("1/a.json", {})
        self.write("1/b.json", {"subject": [{"location": {"page": 5}}]})
        result = discovery.collect([self.root / "1"])
        record, = result.records
        self.assertEqual(record.annotation["subject"], [{**SUBJECT, "uri": "../../book.pdf", "location": {"page": 4}}])
        # A record's list replaces the inherited list, so no template is left to fill b.json's end.
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("SCHEMA", f"{self.root / '1' / 'b.json'} $.subject[0]")] * 2)

    def test_a_null_in_a_defaults_file_removes_the_outer_default_and_is_kept_at_the_top(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": [], "kind": "lemma", "note": None})
        self.write("1.2/_defaults.json", {"kind": None})
        self.write("1.2/a.json", {"note": "kept"})
        self.write("b.json", {})
        result = discovery.collect([self.root])
        record, = result.records
        self.assertEqual((record.path.name, "kind" in record.annotation, record.annotation["note"]),
                         ("a.json", False, "kept"))
        problem, = result.problems  # the outermost null has nothing to remove, so b.json keeps it
        self.assertEqual((problem.code, problem.path), ("SCHEMA", f"{self.root / 'b.json'} $.note"))

    def test_only_a_file_spelled_exactly_is_a_defaults_file(self):
        complete = {"subject": [{"type": "pdf", "uri": "book.pdf"}], "object": []}
        self.write("_Defaults.json", complete)
        self.write("a.json", {"object": []})
        result = discovery.collect([self.root])
        # On every file system it is an ordinary annotation file, and a.json inherits nothing.
        self.assertEqual([(record.path.name, record.defaults) for record in result.records], [("_Defaults.json", ())])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("SCHEMA", str(self.root / "a.json") + " $")])
        (self.root / "sub" / "_Defaults.json").mkdir(parents=True)  # nor is a folder of that name a broken one
        self.write("sub/b.json", complete)
        self.assertEqual([record.path.name for record in discovery.collect([self.root / "sub"]).records], ["b.json"])

    @unittest.skipIf(sys.platform == "win32" or getattr(os, "geteuid", lambda: 0)() == 0, "needs POSIX permissions")
    def test_a_folder_that_cannot_be_listed_still_gives_its_defaults(self):
        self.write("locked/_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("locked/inner/a.json", {})
        (self.root / "locked").chmod(0o111)
        self.addCleanup((self.root / "locked").chmod, 0o755)
        result = discovery.collect([self.root / "locked" / "inner"])
        self.assertEqual((len(result.records), result.problems), (1, []))

    def test_excluded_or_unselected_defaults_still_apply(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("a.x.json", {})
        for options in ({"exclude": ["**/_defaults.json"]}, {"include": ["*.x.json"]}):
            with self.subTest(options=options):
                result = discovery.collect([self.root], **options)
                self.assertEqual((len(result.records), result.problems), (1, []))

    def test_scan_json_names_the_defaults_of_each_record(self):
        defaults = self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("1.1/a.json", {})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["scan", str(self.root), "--format", "json"]), 0)
        record, = json.loads(output.getvalue())["records"]
        self.assertEqual(record["origin"]["defaults"], [str(defaults)])
        self.assertEqual(record["annotation"]["subject"][0]["uri"], "../../book.pdf")

    def test_a_record_too_deep_to_merge_is_reported_and_the_others_are_read(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("a.json", '{"extensions": {"x.y": ' + "[" * 600 + "]" * 600 + "}}", raw=True)
        self.write("b.json", {})
        result = discovery.collect([self.root])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("JSON", str(self.root / "a.json"))])
        self.assertEqual([record.path for record in result.records], [self.root / "b.json"])
        annotation, _, problems = discovery.inherit(companion.loads((self.root / "a.json").read_text()), self.root / "a.json")
        self.assertEqual((annotation, [problem.code for problem in problems]), (None, ["JSON"]))

    def test_defaults_do_not_reach_sibling_folders(self):
        self.write("a/_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("b/c.json", {"object": []})
        result = discovery.collect([self.root])
        self.assertEqual([problem.code for problem in result.problems], ["SCHEMA"])

    def test_jsonl_rows_each_inherit(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("a.json", {"subject": [{"location": {"page": 1}}]})
        self.write("b.jsonl", '{"subject": [{"location": {"page": 2}}]}\n{"subject": [{"location": {"page": 3}}]}\n',
                   raw=True)
        self.write("c.ndjson", '{"subject": [{"location": {"page": 4}}]}\n', raw=True)
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual([record.annotation["subject"][0]["location"]["page"] for record in result.records],
                         [1, 2, 3, 4])
        self.assertTrue(all(record.annotation["subject"][0]["uri"] == "../book.pdf" for record in result.records))

    def test_problems_name_the_defaults_that_were_applied(self):
        self.write("_defaults.json", {"subject": {"type": "pdf"}, "object": []})
        self.write("a.json", {"subject": [{"location": {"page": 1}}]})
        problem, = discovery.collect([self.root]).problems
        self.assertEqual((problem.code, problem.path), ("SCHEMA", f"{self.root / 'a.json'} $.subject[0]"))
        self.assertIn(str(self.root / "_defaults.json"), problem.message)

    def test_a_broken_defaults_file_is_reported_once_and_hides_its_records(self):
        complete = {"subject": [{"type": "pdf", "uri": "book.pdf"}], "object": []}
        self.write("_defaults.json", ["not", "an", "object"])
        self.write("a.json", complete)
        self.write("b/c.json", complete)
        result = discovery.collect([self.root])
        self.assertEqual([(problem.code, problem.path) for problem in result.problems],
                         [("DEFAULTS", str(self.root / "_defaults.json"))])
        self.assertEqual(result.records, [])
        self.write("_defaults.json", "{", raw=True)
        self.assertEqual([problem.code for problem in discovery.collect([self.root]).problems], ["JSON"])

    def test_a_symlinked_defaults_file_is_a_problem(self):
        target = self.write("elsewhere.txt", {"subject": SUBJECT, "object": []})
        self.write("x/a.json", {"subject": [{"location": {"page": 1}}]})
        try:
            (self.root / "x" / "_defaults.json").symlink_to(target)
        except (NotImplementedError, OSError):
            self.skipTest("symbolic links are unavailable")
        result = discovery.collect([self.root / "x"])
        self.assertEqual([problem.code for problem in result.problems], ["SYMLINK"])

    def test_defaults_files_are_checked_but_never_read_as_annotations(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        self.write("x/_defaults.json", 7)
        self.write("a.json", {})
        result = discovery.collect([self.root, self.root / "_defaults.json"])
        self.assertEqual([problem.code for problem in result.problems], ["DEFAULTS"])
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.files, [self.root / "a.json"])

    def test_a_record_without_defaults_is_read_as_written(self):
        self.write("a.json", {"subject": [{**SUBJECT, "location": None}], "object": []})
        self.write("b.json", {"subject": SUBJECT, "object": []})  # a template is not a side
        problems = discovery.collect([self.root]).problems
        self.assertEqual([(problem.code, problem.path) for problem in problems],
                         [("SCHEMA", f"{self.root / 'a.json'} $.subject[0].location"),
                          ("SCHEMA", f"{self.root / 'b.json'} $.subject")])

    def test_inherit_applies_the_folders_of_one_file(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": OBJECT})
        leaf = self.write("1.1/a.json", {"kind": "lemma"})
        annotation, applied, problems = discovery.inherit({"kind": "lemma"}, leaf)
        self.assertEqual((applied, problems), ((self.root / "_defaults.json",), []))
        self.assertEqual(annotation, {"subject": [{**SUBJECT, "uri": "../../book.pdf"}], "object": [OBJECT],
                                      "kind": "lemma"})

    def test_validate_applies_folder_defaults(self):
        self.write("_defaults.json", {"subject": SUBJECT, "object": []})
        leaf = self.write("1.1/a.json", {"subject": [{"location": {"page": 2}}]})
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
        defaults = self.write("_defaults.json", {"subject": {**SUBJECT, "location": {"page": 0}}, "object": []})
        leaf = self.write("a.json", {})
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(cli.main(["validate", str(leaf)]), 1)
        self.assertIn(f"{leaf}: $.subject[0].location.page: must be >= 1 (with defaults from {defaults}) [SCHEMA]",
                      output.getvalue())
        errors = io.StringIO()  # a problem of the installation is not one of the defaults
        with patch.object(companion, "SCHEMA_PATH", self.root / "missing.json"), redirect_stderr(errors):
            self.assertEqual(cli.main(["validate", str(leaf)]), 2)
        self.assertNotIn("with defaults from", errors.getvalue())


class TestFixture(unittest.TestCase):
    """The companion in tests/fixtures/companion, read end to end with its folder defaults."""

    def test_every_record_reads_as_its_defaults_and_its_file_say(self):
        result = discovery.collect([FIXTURE])
        self.assertEqual(result.problems, [])
        chapter = FIXTURE / "chapter-1"
        notes = {"type": "pdf", "uri": "../notes.pdf", "sha256": SHA256}
        deeper = {**notes, "uri": "../../notes.pdf"}
        card = {"declaration": "Subgroup.card_dvd_of_injective", "module": "Mathlib.GroupTheory.Coset.Card"}
        expected = [
            ("chapter-1/absence.json", None, (chapter,), {
                "subject": [{**notes, "location": {"page": 9}, "title": "Remark 1.6"}],
                "object": [OBJECT], "relation": "noMatch", "kind": "remark"}),
            ("chapter-1/lagrange.json", None, (chapter,), {
                "subject": [{**notes, "location": {"page": 7}, "title": "Theorem 1.4 (Lagrange)"},
                            {"type": "pdf", "uri": "../errata.pdf", "location": {"page": 1}}],
                "object": [{**OBJECT, "location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}],
                "relation": "broadMatch"}),
            ("chapter-1/proofs/steps.jsonl", 1, (chapter, chapter / "proofs"), {
                "subject": [{**deeper, "location": {"page": 9, "rect": [0.12, 0.4, 0.76, 0.06]},
                             "title": "Proof of Corollary 1.7, first step"}],
                "object": [{**OBJECT, "location": {**card, "lines": [82]}}],
                "kind": "proof_step", "relation": "exactMatch"}),
            ("chapter-1/proofs/steps.jsonl", 2, (chapter, chapter / "proofs"), {
                "subject": [{**deeper, "location": {"page": 9, "rect": [0.12, 0.46, 0.76, 0.06]},
                             "title": "Proof of Corollary 1.7, second step"}],
                "object": [{**OBJECT, "location": {**card, "lines": [83]}}],
                "kind": "proof_step", "relation": "exactMatch"}),
            ("chapter-1/proofs/steps.jsonl", 3, (chapter, chapter / "proofs"), {
                "subject": [{**deeper, "location": {"page": 10}, "title": "Remark 1.8"}],
                "object": [{**OBJECT, "location": {"module": "Mathlib.GroupTheory.Coset.Card"}}],
                "kind": "remark", "relation": "relatedMatch"}),
            ("chapter-1/remark.json", None, (chapter,), {
                "subject": [{**notes, "location": {"page": 8}, "title": "Remark 1.5"}],
                "object": [], "kind": "remark"}),
            ("links.jsonl", 1, (), {
                "subject": [{"type": "latex", "uri": "chapters/groups.tex", "location": {"label": "def:index"}}],
                "object": [{**OBJECT, "location": {"declaration": "Subgroup.index",
                                                   "module": "Mathlib.GroupTheory.Index"}}],
                "relation": "exactMatch", "kind": "definition"}),
            ("links.jsonl", 2, (), {
                "subject": [{"type": "html", "uri": "https://en.wikipedia.org/wiki/C*-algebra", "version": "1374776629",
                             "location": {"fragment": "Abstract_characterization"},
                             "identifiers": {"wikidata": "Q263809"}}],
                "object": []}),
        ]
        self.assertEqual(len(result.records), len(expected))
        for record, (path, line, folders, annotation) in zip(result.records, expected):
            with self.subTest(path=path, line=line):
                self.assertEqual((record.path, record.line), (FIXTURE / path, line))
                self.assertEqual(record.defaults, tuple(folder / discovery.DEFAULTS for folder in folders))
                self.assertEqual(record.annotation, annotation)
                self.assertEqual(companion.validate(record.annotation), [])


if __name__ == "__main__":
    unittest.main()
