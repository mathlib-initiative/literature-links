"""Validation and JSON reading and writing of one annotation."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import importlib.util
import json
import math
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

from literature_links import companion as C
from literature_links.schemacheck import SchemaError, Validator

MATHLIB = "https://github.com/leanprover-community/mathlib4"
COMMIT = "db584cd6d46c92f209a44c0f1c829460d327499d"
SHA256 = "6c6a04b64488546e49f0ebb4c6310bb091487b5861b5b525985faec6e80c2e7f"
URIS = {"pdf": "notes.pdf", "latex": "chapters/groups.tex", "html": "notes/groups.html", "lean": MATHLIB,
        "generic": "urn:example:record:17"}
# One schema case per line: a record, whether the schema accepts it, and the codes check adds.
CASES = Path(__file__).resolve().parent / "fixtures" / "schema-cases.jsonl"


def end(mode: str = "latex", location: dict | None = None) -> dict:
    result = {"type": mode, "uri": URIS.get(mode, "a")}
    if location is not None:
        result["location"] = location
    return result


def document(mode: str = "latex", location: dict | None = None) -> dict:
    """A record whose one subject end has this type and location, linked to a Mathlib declaration."""
    return {"subject": [end(mode, location)],
            "object": [{"type": "lean", "uri": MATHLIB, "version": COMMIT,
                        "location": {"declaration": "Subgroup.card_subgroup_dvd_card"}}]}


def schema_cases() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines()]


VALID_LOCATIONS = {
    "pdf": [{"page": 1}, {"page": 7, "rect": [0.1, 0.2, 0.6, 0.1]},
            {"page": 2, "rect": [0, 0, 1, 1]}, {"page": 2, "rect": [0.9, 0.9, 0.1, 0.1]},
            {"page": 3, "quote": {"exact": "a finite group", "prefix": "Let ", "suffix": " be given."}},
            {"page": 1, "quote": {"exact": "x"}}],
    "latex": [{"label": "thm:α_2.1"}, {"lines": [1, 1]}, {"lines": [12, 18]}, {"lines": [12]}],
    "html": [{"fragment": "thm-lagrange"}, {"fragment": "thm:α%20"},
             {"css": "article > h2[data-kind='theorem']"}, {"css": "["},
             {"quote": {"exact": "a finite group", "prefix": "Let ", "suffix": " be given."}}],
    "lean": [{"declaration": "Subgroup.card_subgroup_dvd_card"},
             {"declaration": "Subgroup.card_subgroup_dvd_card", "module": "Mathlib.GroupTheory.Coset.Card"},
             {"declaration": "Subgroup.card_dvd_of_injective", "module": "Mathlib.GroupTheory.Coset.Card",
              "lines": [82]},
             {"declaration": "Subgroup.card_dvd_of_injective", "module": "Mathlib.GroupTheory.Coset.Card",
              "lines": [82, 83]},
             {"module": "Mathlib.GroupTheory.Coset.Card"}, {"module": "Notes.Groups", "lines": [12]},
             {"module": "Notes.Groups", "lines": [3, 9]}, {"declaration": "«a name».with spaces and 100%"}],
    "generic": [{}, {"profile": "https://example.org/image-v1", "rect": [0, 1, 20, 30]},
                {"database": {"row": 4, "cell": "A", "values": [None, True, 2.5, "text"]}}],
}

END_FIELDS = {
    "version": COMMIT,
    "sha256": SHA256,
    "citation": {"id": "notes", "type": "book", "title": "Lecture Notes on Groups",
                 "author": [{"family": "Author", "given": "A."}], "issued": {"date-parts": [[2026]]}},
    "identifiers": {"wikidata": "Q263809", "arxiv": "0000.00000", "zbmath": "0000.00001", "doi": "10.0000/example"},
    "title": "Theorem 1.4 (Lagrange)",
    "role": "states",
    "junk": ["Nat.card of an infinite type is 0"],
    "extensions": {"org.example": {"line": 38}},
}


class TestSmallContract(unittest.TestCase):
    def test_every_builtin_and_generic_location_on_either_side(self):
        for mode, locations in VALID_LOCATIONS.items():
            for location in locations:
                for side in ("subject", "object"):
                    doc = document()
                    doc[side] = [end(mode, location)]
                    with self.subTest(mode=mode, location=location, side=side):
                        self.assertEqual(C.validate(doc), [])

    def test_omitted_location_means_the_whole_document_in_every_type(self):
        for mode in VALID_LOCATIONS:
            for side in ("subject", "object"):
                doc = document()
                doc[side] = [end(mode)]
                with self.subTest(mode=mode, side=side):
                    self.assertEqual(C.validate(doc), [])

    def test_a_missing_subject_or_end_type_is_the_only_problem_it_causes(self):
        for location in ({"page": 3, "rect": [0.1, 0.2, 0.3, 0.4]}, {"label": "a"}, {"fragment": "a"},
                         {"declaration": "a", "lines": [3]}):
            for subject in ({}, {"subject": None}, {"subject": "a.pdf"}, {"subject": []}, {"subject": {"uri": "a"}}):
                with self.subTest(location=location, subject=subject):
                    doc = {"object": [{"type": "generic", "uri": "a", "location": location}], **subject}
                    self.assertEqual(len(C.validate(doc)), 1)
            with self.subTest(location=location, end="no type"):
                self.assertEqual(len(C.validate({"subject": [{"uri": "a", "location": location}], "object": []})), 1)

    def test_required_fields_and_object_shapes(self):
        cases = [None, [], 2, "document", {}, {"version": 2}, [document()]]
        for side in ("subject", "object"):
            doc = document()
            del doc[side]
            cases.append(doc)
            for field in ("type", "uri"):
                doc = document()
                del doc[side][0][field]
                cases.append(doc)
            for item in (None, "a.pdf", [], 1, [end()]):
                doc = document()
                doc[side] = [item]
                cases.append(doc)
        for bad in cases:
            with self.subTest(document=bad):
                self.assertTrue(C.validate(bad))

    def test_top_level_version_fields_and_unknown_types_are_rejected(self):
        for key in ("version", "schema_version"):
            for version in (None, True, False, "2", 1, 2, 3, 2.1, "2.0"):
                doc = document()
                doc[key] = version
                with self.subTest(key=key, version=version):
                    self.assertTrue(C.validate(doc))
        for mode in ("markdown", "wikitext", "tex", "web", "PDF", "Lean", "lean4", "repository", "", None):
            for side in ("subject", "object"):
                doc = document()
                doc[side][0]["type"] = mode
                with self.subTest(mode=mode, side=side):
                    self.assertTrue(C.validate(doc))

    def test_1x_fields_typos_and_wrappers_are_rejected(self):
        record_keys = ("source", "target", "location", "label", "pin", "sources", "subjects", "objects", "mode",
                       "relations", "annotations", "type", "uri")
        end_keys = ("format", "pin", "label", "page", "lines", "declaration", "status", "kind", "id", "note",
                    "relation", "url", "subject")
        for key in record_keys:
            doc = document()
            doc[key] = []
            with self.subTest(place="record", key=key):
                self.assertTrue(C.validate(doc))
        for key in end_keys:
            for side in ("subject", "object"):
                doc = document()
                doc[side][0][key] = []
                with self.subTest(place=side, key=key):
                    self.assertTrue(C.validate(doc))

    def test_sides_are_lists_of_ends_taken_jointly(self):
        doc = document("pdf", {"page": 7})
        doc["subject"].append(end("pdf", {"page": 8}))
        doc["object"].append({"type": "lean", "uri": MATHLIB, "location": {"declaration": "Subgroup.index_mul_card"}})
        self.assertEqual(C.validate(doc), [])
        doc["subject"].append(copy.deepcopy(doc["subject"][0]))  # a repeated end is not a problem
        self.assertEqual(C.validate(doc), [])
        doc["object"] = []
        self.assertEqual(C.validate(doc), [])
        for side, value in (("subject", []), ("subject", end("pdf")), ("object", end("lean")), ("subject", "a.pdf"),
                            ("object", None), ("object", [[end("lean")]]), ("subject", {"0": end()})):
            doc = document()
            doc[side] = value
            with self.subTest(side=side, value=value):
                self.assertTrue(C.validate(doc))

    def test_annotation_id_is_an_optional_nonempty_application_label(self):
        doc = document()
        self.assertEqual(C.validate(doc), [])
        for identity in ("a", "a label", " ", "α", "https://example.org/annotation/1"):
            doc["id"] = identity
            duplicate = copy.deepcopy(doc)
            duplicate["object"] = [end("generic")]
            self.assertEqual(C.validate(doc), [])
            self.assertEqual(C.validate(duplicate), [])
        doc["extensions"] = {"id": "a", "tool": {"id": "a"}}
        doc["subject"][0]["extensions"] = {"id": "a"}
        self.assertEqual(C.validate(doc), [])
        for invalid in ("", None, 3, True, []):
            doc["id"] = invalid
            with self.subTest(id=invalid):
                self.assertTrue(C.validate(doc))
        doc["id"] = "a"
        doc["subject"][0]["id"] = "a"  # an end has no id
        self.assertTrue(C.validate(doc))

    def test_check_does_not_mutate_or_sort(self):
        doc = document("generic", {"z": [3, 2, 1], "a": {"key": "value"}})
        doc["extensions"] = {"z": {"target": "urn:embedded", "annotations": [3, 2, 1]}, "a": 0}
        doc["object"].insert(0, end("pdf", {"page": 2, "rect": [0.5, 0, 0.5, 1]}))
        before = copy.deepcopy(doc)
        self.assertEqual(C.check(doc), C.Report())
        self.assertEqual(doc, before)
        self.assertEqual(list(doc["subject"][0]["location"]), ["z", "a"])
        self.assertEqual(list(doc["extensions"]), ["z", "a"])
        self.assertEqual([item["type"] for item in doc["object"]], ["pdf", "lean"])


class TestRecordFields(unittest.TestCase):
    def test_relation_status_kind_id_and_note_are_optional_nonempty_strings(self):
        doc = document()
        values = ("exactMatch", "closeMatch", "broadMatch", "narrowMatch", "relatedMatch", "hasPart", "noMatch",
                  "formalized", "partial", "not_formalized", "proof_step", "A label with spaces", "α",
                  "anything applications agree on")
        for key in ("relation", "status", "kind", "id", "note"):
            for value in values:
                doc[key] = value
                self.assertEqual(C.validate(doc), [], (key, value))
            for value in ("", None, 1, True, [], ["formalized"], {"value": "formalized"}):
                doc[key] = value
                with self.subTest(key=key, value=value):
                    self.assertTrue(C.validate(doc))
            del doc[key]
        self.assertEqual(C.validate(doc), [])

    def test_status_objects_and_pins_are_gone(self):
        mathlib = {"type": "repository", "url": MATHLIB, "commit": COMMIT}
        for status in ({}, {"value": "not_formalized"}, {"pin": mathlib},
                       {"value": "partial", "extensions": {"x.y": 1}}):
            doc = document()
            doc["status"] = status
            with self.subTest(status=status):
                self.assertTrue(C.validate(doc))
        for side in ("subject", "object"):
            doc = document()
            doc[side][0]["pin"] = mathlib
            with self.subTest(side=side):
                self.assertTrue(C.validate(doc))

    def test_an_unlinked_passage_and_a_checked_absence_are_both_valid(self):
        unlinked = {"subject": [end("pdf", {"page": 8})], "object": []}
        absence = {"subject": [end("pdf", {"page": 8})],
                   "object": [{"type": "lean", "uri": MATHLIB, "version": COMMIT}], "relation": "noMatch"}
        self.assertEqual((C.validate(unlinked), C.validate(absence)), ([], []))
        # Validation does not judge a relation: noMatch over one declaration, or over nothing, is still valid.
        self.assertEqual(C.validate({**unlinked, "relation": "noMatch"}), [])
        self.assertEqual(C.validate({**document(), "relation": "noMatch"}), [])


class TestEnds(unittest.TestCase):
    def test_every_end_field_on_either_side(self):
        for side in ("subject", "object"):
            doc = document()
            doc[side][0].update(copy.deepcopy(END_FIELDS))
            with self.subTest(side=side):
                self.assertEqual(C.validate(doc), [])

    def test_end_field_shapes(self):
        valid = [("version", "1374776629"), ("version", "v2"), ("version", " "), ("version", "main"),
                 ("sha256", "0" * 64), ("citation", {"id": "x", "type": "book"}),
                 ("citation", {"id": "a", "type": "not-a-csl-type", "URL": "a b", "author": [1], "issued": None}),
                 ("identifiers", {}), ("identifiers", {"doi": "10.0000/x", "100%": "x", "α": " "}),
                 ("title", "α"), ("role", "uses"), ("extensions", {}), ("extensions", {"x.y": None})]
        for key, value in valid:
            doc = document()
            doc["subject"][0][key] = value
            with self.subTest(key=key, value=value):
                self.assertEqual(C.validate(doc), [])
        invalid = [("version", ""), ("version", None), ("version", 1), ("version", []),
                   ("sha256", "0" * 63), ("sha256", "0" * 65), ("sha256", "A" * 64), ("sha256", "0" * 64 + "\n"),
                   ("sha256", "g" * 64), ("sha256", ""), ("sha256", 1),
                   ("citation", {}), ("citation", {"id": "a"}), ("citation", {"type": "book"}),
                   ("citation", {"id": "", "type": "book"}), ("citation", {"id": "a", "type": ""}),
                   ("citation", {"id": 1, "type": "book"}), ("citation", "Notes, 2026"), ("citation", []),
                   ("citation", None),
                   ("identifiers", {"": "x"}), ("identifiers", {" ": "x"}), ("identifiers", {"a b": "x"}),
                   ("identifiers", {"a⁦": "x"}), ("identifiers", {"doi": 1}), ("identifiers", {"doi": ""}),
                   ("identifiers", {"doi": None}), ("identifiers", []), ("identifiers", "Q1"),
                   ("title", ""), ("title", None), ("title", 1), ("role", ""), ("role", ["states"]),
                   ("extensions", []), ("extensions", None), ("extensions", "x"), ("extensions", {"": 1})]
        for key, value in invalid:
            doc = document()
            doc["object"][0][key] = value
            with self.subTest(key=key, value=value):
                self.assertTrue(C.validate(doc))

    def test_junk_is_an_optional_list_of_nonempty_strings_on_an_end(self):
        doc = {**document(), "relation": "exactMatch"}
        doc["object"].append({**doc["object"][0], "location": {"declaration": "Subgroup.index_dvd_card"}})
        for junk in (["Nat.card of an infinite type is 0"], ["x / 0 = 0", "Real.log 0 = 0"], [" "], ["a", "a"]):
            for side, index in (("subject", 0), ("object", 0), ("object", 1)):
                end_with_junk = copy.deepcopy(doc)
                end_with_junk[side][index]["junk"] = junk
                self.assertEqual(C.validate(end_with_junk), [], (side, index, junk))
        # Each object end lists its own.
        doc["object"][0]["junk"] = ["Nat.card of an infinite type is 0"]
        doc["object"][1]["junk"] = ["Nat.card of an infinite type is 0", "Subgroup.index of an infinite index is 0"]
        self.assertEqual(C.validate(doc), [])
        for junk in ([], [""], [1], [None], [["a"]], "x / 0 = 0", {"x / 0": "0"}, None, True):
            doc["object"][1]["junk"] = junk
            with self.subTest(junk=junk):
                self.assertTrue(C.validate(doc))
        del doc["object"][1]["junk"]
        self.assertEqual(C.validate(doc), [])
        # junk is not a record field.
        doc["junk"] = doc["object"][0].pop("junk")
        self.assertEqual([problem.code for problem in C.check(doc).problems], ["SCHEMA"])

    def test_every_optional_end_key_is_typed(self):
        for key in END_FIELDS:
            for value in (1, "", None, True):
                doc = document()
                doc["subject"][0][key] = value
                with self.subTest(key=key, value=value):
                    self.assertTrue(C.validate(doc))

    def test_ends_and_facts_are_not_verified(self):
        doc = document()
        doc["subject"][0].update({"uri": "https://unreachable.invalid/notes.pdf", "sha256": "0" * 64})
        doc["object"][0].update({"version": "0" * 40, "location": {"declaration": "No.such", "module": "No.Such",
                                                                   "lines": [99999]}})
        doc.update({"relation": "exactMatch", "status": "formalized"})
        with patch("urllib.request.urlopen", side_effect=AssertionError("network access")):
            self.assertEqual(C.validate(doc), [])


class TestReferencesAndExtensions(unittest.TestCase):
    def test_references_allow_relative_unicode_and_opaque_identifiers(self):
        references = ("groups.tex", "../docs/Groups.html#Lagrange", "#theorem", "/docs/α.html", "..",
                      "https://example.org/α?x=1#theorem", "urn:lean:Nat.add_comm", "http://[x",
                      "git+https://example.org/repo", "custom:record/1", "javascript:alert(1)", "x")
        for reference in references:
            doc = document()
            doc["subject"][0]["uri"] = reference
            doc["object"][0]["uri"] = reference
            doc["$schema"] = reference
            with self.subTest(reference=reference):
                self.assertEqual(C.validate(doc), [])

    def test_references_disallow_literal_whitespace_controls_and_wrong_types(self):
        invalid = ("", " ", "a b", "url\n", "\turl", "url\x00", "url\x7f", "url\x85", "url ", None, 1, [], {})
        for value in invalid:
            for place in ("subject", "object", "$schema", "profile"):
                doc = document("generic", {"profile": "urn:x"})
                if place == "$schema":
                    doc["$schema"] = value
                elif place == "profile":
                    doc["subject"][0]["location"]["profile"] = value
                else:
                    doc[place][0]["uri"] = value
                with self.subTest(value=value, place=place):
                    self.assertTrue(C.validate(doc))

    def test_no_references_or_selector_payloads_are_fetched_or_executed(self):
        doc = document("generic", {"profile": "https://unreachable.invalid/schema", "script": "arbitrary content"})
        doc["$schema"] = "https://unreachable.invalid/companion.json"
        doc["subject"][0]["uri"] = "https://unreachable.invalid/source"
        doc["object"][0]["uri"] = "https://unreachable.invalid/target"
        with patch("socket.socket", side_effect=AssertionError("unexpected network access")):
            self.assertEqual(C.validate(doc), [])

    def test_extensions_are_available_without_registration_on_records_and_ends(self):
        doc = document()
        payload = {"org.example.tool": {"a key with spaces": [None, True, False, 1, 0.5, "α"]},
                   "local": None, "https://example.org/profile": {}}
        for node in (doc, doc["subject"][0], doc["object"][0]):
            node["extensions"] = copy.deepcopy(payload)
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), doc)

    def test_extension_keys_are_nonempty_without_whitespace_or_control(self):
        for key in ("", "tool name", "tool\n", "tool\x00", "tool\x7f", "tool\x85"):
            for node in ("record", "end"):
                doc = document()
                (doc if node == "record" else doc["object"][0])["extensions"] = {key: None}
                with self.subTest(key=key, node=node):
                    self.assertTrue(C.validate(doc))

    def test_references_and_keys_exclude_invisible_formatting_characters(self):
        # Bidirectional formatting, zero-width characters and U+FFFE/U+FFFF can make a link display as another.
        forbidden = "​‌‍‎‏‪‫‬‭‮⁦⁧⁨⁩﻿￾￿"
        for char in forbidden:
            for value in ("https://example.org/" + char + "gpj.exe", char + "x"):
                with self.subTest(codepoint=hex(ord(char)), value=value):
                    doc = document()
                    doc["object"][0]["uri"] = value
                    self.assertTrue(C.validate(doc))
                    doc = document()
                    doc["extensions"] = {value: None}
                    self.assertTrue(C.validate(doc))
                    doc = document()
                    doc["subject"][0]["identifiers"] = {value: "x"}
                    self.assertTrue(C.validate(doc))

    def test_a_percent_sign_in_a_reference_starts_a_percent_encoding(self):
        for value in ("a%20b", "%C3%A9", "x%2f%2F", "https://example.org/100%25"):
            doc = document()
            doc["object"][0]["uri"] = value
            with self.subTest(value=value):
                self.assertEqual(C.validate(doc), [])
        for value in ("%", "a%", "a%2", "%zz", "100%", "a%g0"):
            doc = document()
            doc["object"][0]["uri"] = value
            with self.subTest(value=value):
                self.assertTrue(C.validate(doc))
        # Extension keys, identifier names, fragments, versions, Lean names and citations are not references.
        doc = document("html", {"fragment": "100%"})
        doc["extensions"] = {"100%": None}
        doc["subject"][0].update({"identifiers": {"100%": "x"}, "version": "100%",
                                  "citation": {"id": "100%", "type": "book", "URL": "100%"}})
        doc["object"][0]["location"]["declaration"] = "100%"
        self.assertEqual(C.validate(doc), [])

    def test_extensions_require_objects(self):
        for value in (None, "extension", [1], True):
            for node in ("record", "end"):
                doc = document()
                (doc if node == "record" else doc["subject"][0])["extensions"] = value
                with self.subTest(value=value, node=node):
                    self.assertTrue(C.validate(doc))

    def test_whitespace_definition_is_explicit_and_unicode_stable(self):
        # These cover Unicode White_Space outside ASCII, including characters
        # whose treatment differs between common regex dialects.
        forbidden = "\u0085                 　"
        forbidden += "".join(map(chr, range(0x21))) + "".join(map(chr, range(0x7f, 0xa0)))
        for char in forbidden:
            for value in ("x" + char + "y", "xy" + char):
                doc = document()
                doc["object"][0]["uri"] = value
                with self.subTest(codepoint=ord(char), value=value):
                    self.assertTrue(C.validate(doc))
                    doc["object"][0]["uri"] = "urn:valid"
                    doc["extensions"] = {value: None}
                    self.assertTrue(C.validate(doc))
        for char in ("᠎", "⁠", "😀"):
            doc = document()
            doc["object"][0]["uri"] = "urn:" + char
            doc["extensions"] = {"tool" + char: None}
            with self.subTest(non_whitespace=char):
                self.assertEqual(C.validate(doc), [])


class TestStructuredDiagnostics(unittest.TestCase):
    def test_problem_is_frozen_and_has_a_readable_string(self):
        problem = C.Problem("SCHEMA", "$.subject[0].uri", "must be a string")
        self.assertEqual(str(problem), "$.subject[0].uri: must be a string")
        with self.assertRaises(FrozenInstanceError):
            problem.code = "OTHER"

    def test_stable_codes_paths_and_convenience_strings(self):
        bad_json = document("generic", {"payload": float("inf")})
        bad_shape = document()
        bad_shape["object"] = {}
        lean_lines = document()
        lean_lines["object"][0]["location"] = {"module": "Notes.Groups", "lines": [9, 3]}
        cases = [(bad_json, "JSON", '$["subject"][0]["location"]["payload"]'),
                 (bad_shape, "SCHEMA", "$.object"),
                 (document("pdf", {"page": 1, "rect": [0, 0, 0, 1]}), "PDF_RECT", "$.subject[0].location.rect"),
                 (document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]}), "PDF_RECT", "$.subject[0].location.rect"),
                 (document("latex", {"lines": [5, 2]}), "LINES", "$.subject[0].location.lines"),
                 (lean_lines, "LINES", "$.object[0].location.lines")]
        for doc, code, path in cases:
            with self.subTest(code=code, path=path):
                report = C.check(doc)
                self.assertEqual(report.warnings, [])
                self.assertTrue(report.problems)
                self.assertTrue(all(isinstance(problem, C.Problem) for problem in report.problems))
                self.assertIn((code, path), [(problem.code, problem.path) for problem in report.problems])
                self.assertEqual(C.validate(doc), [str(problem) for problem in report.problems])

    def test_a_rectangle_is_checked_in_a_second_subject_end(self):
        doc = document("pdf", {"page": 7, "rect": [0.1, 0.2, 0.6, 0.1]})
        doc["subject"].append(end("pdf", {"page": 8, "rect": [0.8, 0, 0.3, 1]}))
        self.assertEqual(C.check(doc).problems,
                         [C.Problem("PDF_RECT", "$.subject[1].location.rect", "rectangle must stay within the page")])

    def test_every_end_is_checked_subject_first(self):
        doc = {"subject": [end("latex", {"lines": [9, 2]}), end("pdf", {"page": 1, "rect": [0.5, 0, 0, 1]}),
                           end("latex", {"lines": [4]})],
               "object": [end("lean", {"declaration": "x", "module": "M", "lines": [9, 3]}), end("lean"),
                          end("pdf", {"page": 1, "rect": [0.5, 0.5, 0.6, -0.0]})]}
        self.assertEqual([(problem.code, problem.path, problem.message) for problem in C.check(doc).problems], [
            ("LINES", "$.subject[0].location.lines", "end must be greater than or equal to start"),
            ("PDF_RECT", "$.subject[1].location.rect", "width and height must be positive"),
            ("LINES", "$.object[0].location.lines", "end must be greater than or equal to start"),
            ("PDF_RECT", "$.object[2].location.rect", "width and height must be positive"),
            ("PDF_RECT", "$.object[2].location.rect", "rectangle must stay within the page")])

    def test_one_line_is_never_out_of_order(self):
        for location, mode in (({"lines": [12]}, "latex"), ({"lines": [2**100]}, "latex"),
                               ({"module": "Notes.Groups", "lines": [12]}, "lean"),
                               ({"declaration": "x", "module": "M", "lines": [1]}, "lean")):
            for side in ("subject", "object"):
                doc = document()
                doc[side] = [end(mode, location)]
                with self.subTest(location=location, side=side):
                    self.assertEqual(C.check(doc).problems, [])

    def test_a_profile_skips_the_checks_beyond_the_schema(self):
        profiled = [end("pdf", {"profile": "urn:example:figure", "page": 0, "rect": [0.9, 0.9, 0.5, 0.5]}),
                    end("latex", {"profile": "urn:example:environment", "lines": [9, 2]}),
                    end("lean", {"profile": "urn:example:tactic", "module": "M", "lines": [9, 3]}),
                    end("lean", {"profile": "urn:example:tactic", "lines": [9, 3]})]
        self.assertEqual(C.check({"subject": profiled, "object": copy.deepcopy(profiled)}).problems, [])
        # A generic location is opaque, so its lines are never checked either.
        self.assertEqual(C.check(document("generic", {"lines": [20, 1], "rect": [0.9, 0, 0.5, 0]})).problems, [])

    def test_malformed_structure_prevents_secondary_semantic_failures(self):
        report = C.check(document("pdf", {"page": 1, "rect": [0, None, 0, "width"]}))
        self.assertTrue(report.problems)
        self.assertEqual({problem.code for problem in report.problems}, {"SCHEMA"})
        # A schema problem anywhere stops the other checks everywhere.
        doc = document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]})
        doc["object"].append(end("latex", {"lines": [5, 2]}))
        doc["object"].append({"type": "lean"})
        self.assertEqual([(problem.code, problem.path) for problem in C.check(doc).problems],
                         [("SCHEMA", "$.object[2]")])


class TestLocatorBounds(unittest.TestCase):
    def test_empty_builtin_locations_are_not_whole_document_aliases(self):
        for mode in ("pdf", "latex", "html", "lean"):
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(document(mode, {})))
        self.assertEqual(C.validate(document("generic", {})), [])

    def test_null_location_is_invalid_in_every_type(self):
        for mode in VALID_LOCATIONS:
            doc = document(mode)
            doc["subject"][0]["location"] = None
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(doc))

    def test_pdf_physical_pages_are_positive_integers(self):
        for page in (0, -1, 1.5, True, False, "1", None):
            with self.subTest(page=page):
                self.assertTrue(C.validate(document("pdf", {"page": page})))

    def test_pdf_rectangles_require_page_positive_extent_and_page_bounds(self):
        invalid = ([0, 0, 0, 1], [0, 0, 1, 0], [-0.1, 0, 0.5, 0.5], [0, 0, 1.1, 0.5],
                   [0.7, 0, 0.4, 1], [0, 0.7, 1, 0.4], [1, 0, 0.1, 1],
                   [0.5, 0, 0.5000000000000002, 1], [0, 0.5, 1, 0.5000000000000002],
                   [0, 0, 1], [0, 0, 1, 1, 1], [True, 0, 1, 1], "0,0,1,1")
        for rectangle in invalid:
            for side in ("subject", "object"):
                doc = document()
                doc[side] = [end("pdf", {"page": 1, "rect": rectangle})]
                with self.subTest(rect=rectangle, side=side):
                    self.assertTrue(C.validate(doc))
        self.assertTrue(C.validate(document("pdf", {"rect": [0, 0, 1, 1]})))

    def test_a_pdf_rectangle_fits_when_the_double_sums_do(self):
        for rect in ([0.9, 0, 0.10000000000000002, 1], [1e-100, 0, 1, 1], [100 / 612, 0, 512 / 612, 1],
                     *([n / 997, n / 997, 1 - n / 997, 1 - n / 997] for n in range(1, 997))):
            with self.subTest(rect=rect):
                self.assertEqual(C.validate(document("pdf", {"page": 1, "rect": rect})), [])

    def test_pdf_quote_is_the_html_quote_beside_a_page_and_never_with_a_rect(self):
        quote = {"exact": "a finite group", "prefix": "Let ", "suffix": " be given."}
        self.assertEqual(C.validate(document("pdf", {"page": 3, "quote": quote})), [])
        self.assertEqual(C.validate(document("pdf", {"page": 3, "quote": {"exact": "α\nβ", "prefix": ""}})), [])
        invalid = ({"page": 3, "rect": [0, 0, 1, 1], "quote": quote}, {"quote": quote},
                   {"page": 3, "quote": {"exact": ""}}, {"page": 3, "quote": {}},
                   {"page": 3, "quote": {"exact": "a", "position": 4}}, {"page": 3, "quote": {"exact": "a", "suffix": 3}},
                   {"page": 3, "quote": "a finite group"}, {"page": 3, "quote": None},
                   {"page": 3, "quote": quote, "fragment": "a"}, {"page": 3, "quote": quote, "pages": [3, 4]})
        for location in invalid:
            with self.subTest(location=location):
                self.assertTrue(C.validate(document("pdf", location)))
        # Both is a structural problem, so the rect checks never run on it.
        report = C.check(document("pdf", {"page": 3, "rect": [0.8, 0, 0.3, 1], "quote": quote}))
        self.assertEqual([(p.code, p.path) for p in report.problems], [("SCHEMA", "$.subject[0].location")])
        self.assertEqual(C.validate(document("pdf", {"page": 3, "rect": [0, 0, 1, 1], "quote": quote})),
                         ["$.subject[0].location: must not have both 'rect' and 'quote'"])
        self.assertEqual(C.check(document("pdf", {"page": 3, "quote": quote})).problems, [])

    def test_latex_anchor_alternatives(self):
        invalid = ({"label": ""}, {"label": "a", "lines": [1, 2]}, {"label": "a", "lines": [1]}, {"lines": [2, 1]},
                   {"line": 1}, {"label": "a", "file": "other.tex"}, {"module": "M"}, {"declaration": "x"},
                   {"label": 3})
        for location in invalid:
            with self.subTest(location=location):
                self.assertTrue(C.validate(document("latex", location)))

    def test_lean_declaration_module_and_lines(self):
        invalid = ({"lines": [1]}, {"declaration": "x", "lines": [1]}, {"declaration": ""}, {"module": ""},
                   {"declaration": 1}, {"module": ["Mathlib"]}, {"declaration": None, "module": "M"},
                   {"declaration": "x", "path": "Mathlib/GroupTheory/Coset/Card.lean"}, {"declaration": "x", "line": 3},
                   {"module": "M", "lines": [9, 3]}, {"label": "x"}, {"fragment": "x"}, {"name": "x"},
                   {"declaration": "x", "commit": COMMIT})
        for location in invalid:
            for side in ("subject", "object"):
                doc = document()
                doc[side] = [end("lean", location)]
                with self.subTest(location=location, side=side):
                    self.assertTrue(C.validate(doc))

    def test_lines_are_one_or_two_positive_integers_in_latex_and_lean(self):
        valid = ([1], [12], [1, 1], [12, 18], [2**100], [1, 2**100])
        invalid = ([], [0], [0, 1], [1, 0], [-1], [1, 2, 3], [1, 1.5], [True], [1, False], [None], ["1"], "1", 1,
                   None, {"start": 1})
        for mode, location in (("latex", {}), ("lean", {"module": "Notes.Groups"}),
                               ("lean", {"declaration": "x", "module": "M"})):
            for lines in valid:
                with self.subTest(mode=mode, lines=lines):
                    self.assertEqual(C.validate(document(mode, {**location, "lines": lines})), [])
            for lines in invalid:
                with self.subTest(mode=mode, lines=lines):
                    self.assertTrue(C.validate(document(mode, {**location, "lines": lines})))

    def test_html_anchor_alternatives(self):
        invalid = ({"fragment": ""}, {"fragment": "#theorem"}, {"fragment": "a b"},
                   {"fragment": "a", "css": "#a"}, {"fragment": "a", "quote": {"exact": "a"}},
                   {"css": "a", "quote": {"exact": "a"}}, {"css": ""}, {"css": 3},
                   {"quote": {}}, {"quote": {"exact": ""}}, {"quote": {"exact": "a", "prefix": 3}},
                   {"quote": {"exact": "a", "position": 4}}, {"xpath": "//a"})
        for location in invalid:
            with self.subTest(location=location):
                self.assertTrue(C.validate(document("html", location)))

    def test_quote_whitespace_unicode_and_context_are_not_rewritten(self):
        doc = document("html", {"quote": {"exact": "α\nβ  γ", "prefix": "", "suffix": " "}})
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), doc)

    def test_generic_locations_stay_opaque_but_must_be_objects(self):
        doc = document("generic", {"page": -1, "lines": [20, 1], "fragment": "#x", "foreign": None})
        self.assertEqual(C.validate(doc), [])
        for value in (None, 2, "locator", [], True):
            doc["subject"][0]["location"] = value
            with self.subTest(location=value):
                self.assertTrue(C.validate(doc))

    def test_integer_valued_json_numbers_are_valid_page_and_line_indices(self):
        # JSON Schema's integer type describes a numeric value, not its spelling.
        for number in (1.0, 2**100, 1e100):
            with self.subTest(number=number):
                self.assertEqual(C.validate(document("pdf", {"page": number})), [])
                self.assertEqual(C.validate(document("latex", {"lines": [number, number]})), [])
                self.assertEqual(C.validate(document("latex", {"lines": [number]})), [])
                self.assertEqual(C.validate(document("lean", {"module": "M", "lines": [number, number]})), [])

    def test_profile_marks_an_application_defined_location_in_every_type(self):
        profiled = {"pdf": {"profile": "urn:example:figure", "page": 0, "rect": [0.9, 0.9, 0.5, 0.5]},
                    "latex": {"profile": "urn:example:environment", "lines": [9, 2]},
                    "html": {"profile": "urn:example:anchor:v3", "section": "Definition", "snippet": "a group"},
                    "lean": {"profile": "urn:example:tactic", "lines": [9, 3], "tactic": "calc"},
                    "generic": {"profile": "https://example.org/profiles/row", "row": 4}}
        for mode, location in profiled.items():
            with self.subTest(mode=mode):
                self.assertEqual(C.validate(document(mode, location)), [])
            for profile in ("", "a b", 1, None, [], {}):
                with self.subTest(mode=mode, profile=profile):
                    self.assertTrue(C.validate(document(mode, {"profile": profile})))
        for mode, location in (("html", {"fragmnet": "x"}), ("pdf", {"pag": 1}), ("latex", {"label": "a", "extra": 1}),
                               ("lean", {"declaraton": "x"})):
            with self.subTest(mode=mode, location=location):
                self.assertTrue(C.validate(document(mode, location)))

    def test_schema_looking_generic_payloads_are_never_interpreted(self):
        payload = {"$id": "../private.json", "$schema": "https://example.org/unknown",
                   "$ref": "https://example.org/execute", "type": "future-mode",
                   "properties": None, "\u0000": {"": [None, True, 2**100]}}
        doc = document("generic", payload)
        doc["extensions"] = {"tool": copy.deepcopy(payload)}
        doc["object"][0]["citation"] = {**copy.deepcopy(payload), "id": "x", "type": "book"}
        original = copy.deepcopy(doc)
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), original)


class TestStrictJson(unittest.TestCase):
    def test_duplicate_keys_are_rejected_at_every_depth(self):
        for text in ('{"version":2,"version":2}', '{"extensions":{"tool":1,"tool":2}}',
                     '{"subject":[{"location":{"nested":{"same":1,"same":2}}}]}',
                     '{"subject":1,"\\u0073ubject":2}', '{"😀":1,"\\ud83d\\ude00":2}'):
            with self.subTest(text=text), self.assertRaises(C.LoadError):
                C.loads(text)

    def test_nonfinite_json_literals_and_overflow_are_rejected(self):
        for text in ("NaN", "Infinity", "-Infinity", "1e999", '-1e999', '{"a":[1e999]}'):
            with self.subTest(text=text), self.assertRaises(C.LoadError):
                C.loads(text)

    def test_nonzero_float_underflow_is_a_codec_limit_not_silent_zero(self):
        for text in ("1e-10000", "-1E-10000", "2e-324", '{"opaque":[1e-10000]}',
                     "0." + "0" * 400 + "1"):
            with self.subTest(text=text), self.assertRaisesRegex(C.LoadError, "floating-point range"):
                C.loads(text)
        for text in ("0e-10000", "0e10000", "0.000e999999999999999999999", "-0.0e-10000"):
            with self.subTest(text=text):
                self.assertEqual(C.loads(text), 0.0)
        self.assertEqual(math.copysign(1.0, C.loads("-0.0e-10000")), -1.0)
        self.assertEqual(C.loads("5e-324"), 5e-324)
        self.assertEqual(C.loads("1.0000000000000001"), float("1.0000000000000001"))
        # The schema still permits tiny finite in-memory JSON values and zero.
        doc = document("generic", {"small": 5e-324, "zero": 0.0})
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), doc)

    def test_python_only_values_are_rejected_even_inside_extensions(self):
        for value in (float("nan"), float("inf"), float("-inf"), (1, 2), {1: "value"}, {1, 2}, b"value", object()):
            for node in ("record", "end"):
                doc = document()
                (doc if node == "record" else doc["object"][0])["extensions"] = {"tool": {"nested": value}}
                with self.subTest(value=repr(value), node=node):
                    self.assertTrue(C.validate(doc))
                    with self.assertRaises(C.LoadError):
                        C.dumps(doc)

    def test_cycles_are_rejected_but_shared_objects_are_valid(self):
        child = {"value": [1, 2]}
        doc = document("generic", {"first": child, "second": child})
        self.assertEqual(C.validate(doc), [])
        child["cycle"] = doc
        self.assertTrue(any("cyclic" in message for message in C.validate(doc)))
        with self.assertRaises(C.LoadError):
            C.dumps(doc)
        values = []
        values.append(values)
        with self.assertRaises(C.LoadError):
            C.dumps(values)

    def test_excessive_nesting_is_a_reported_error(self):
        value = None
        for _ in range(sys.getrecursionlimit() + 1):
            value = [value]
        self.assertTrue(C.validate(value))
        with self.assertRaises(C.LoadError):
            C.dumps(value)
        with self.assertRaises(C.LoadError):
            C.loads("[" * (sys.getrecursionlimit() + 1) + "0" + "]" * (sys.getrecursionlimit() + 1))

    def test_lone_unicode_surrogates_in_strings_and_keys_are_rejected(self):
        for text in ('"\\ud800"', '"\\udfff"', '{"\\ud800":"value"}'):
            with self.subTest(text=text), self.assertRaisesRegex(C.LoadError, "surrogate"):
                C.loads(text)
        for value in ("\ud800", {"\udfff": 2}):
            doc = document("generic", {"payload": value})
            self.assertTrue(C.validate(doc))
            with self.assertRaises(C.LoadError):
                C.dumps(doc)
        self.assertEqual(C.loads('"\\ud83d\\ude00"'), "😀")
        self.assertEqual(C.loads(C.dumps("😀")), "😀")

    def test_round_trip_preserves_large_integers_unicode_and_order(self):
        doc = document("generic", {"z": {"β": 2**100, "α": -2**100}, "a": [3, 2, 1]})
        text = C.dumps(doc)
        result = C.loads(text)
        self.assertEqual(result, doc)
        self.assertEqual(list(result["subject"][0]["location"]), ["z", "a"])
        self.assertEqual(list(result["subject"][0]["location"]["z"]), ["β", "α"])
        self.assertTrue(text.endswith("\n"))
        self.assertIn("β", text)
        self.assertEqual(C.dumps({"a": [1]}), '{\n  "a": [\n    1\n  ]\n}\n')

    def test_codecs_are_not_implicit_companion_validation(self):
        value = {"custom": [None, True, "text", 3.5]}
        self.assertEqual(C.loads(C.dumps(value)), value)
        self.assertTrue(C.validate(value))
        for malformed in ('{"a":}', "{", "not JSON"):
            with self.subTest(text=malformed), self.assertRaises(C.LoadError):
                C.loads(malformed)

    def test_parser_integer_limits_are_reported_without_a_traceback(self):
        if not hasattr(sys, "get_int_max_str_digits") or not sys.get_int_max_str_digits():
            self.skipTest("this interpreter has no integer string conversion limit")
        digits = sys.get_int_max_str_digits() + 1
        with self.assertRaises(C.LoadError):
            C.loads("1" * digits)
        large = 10 ** digits
        with self.assertRaises(C.LoadError):
            C.dumps(large)
        doc = document()
        doc["subject"][0]["type"] = large
        self.assertTrue(C.validate(doc))


class TestSchema(unittest.TestCase):
    def test_schema_has_one_source_and_matches_installed_bytes(self):
        repo = ROOT / "schema" / "companion.schema.json"
        source = ROOT / "src" / "literature_links" / "schema" / "companion.schema.json"
        self.assertFalse(source.exists())
        self.assertEqual(repo.read_bytes(), C.SCHEMA_PATH.read_bytes())
        self.assertEqual(C.load_schema()["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_semantic_invariants_are_additional_to_structure(self):
        structural = Validator(C.load_schema())
        lean = document()
        lean["object"][0]["location"] = {"module": "Notes.Groups", "lines": [9, 3]}
        invalid = [document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]}),
                   document("latex", {"lines": [4, 2]}), lean]
        for doc in invalid:
            with self.subTest(document=doc):
                self.assertTrue(structural.is_valid(doc))
                self.assertTrue(C.validate(doc))

    def test_the_case_table(self):
        cases = schema_cases()
        self.assertGreaterEqual(len(cases), 100)
        self.assertEqual(len({case["name"] for case in cases}), len(cases))
        structural = Validator(C.load_schema())
        for case in cases:
            with self.subTest(case=case["name"], rule=case["rule"]):
                self.assertEqual(structural.is_valid(case["record"]), case["schema_valid"])
                codes = [problem.code for problem in C.check(case["record"]).problems]
                if case["schema_valid"]:
                    self.assertEqual(codes, case["beyond"])
                else:
                    self.assertTrue(codes)
                    self.assertEqual(set(codes), {"SCHEMA"})
        # The table covers both outcomes and both checks beyond the schema.
        self.assertEqual({code for case in cases for code in case["beyond"]}, {"PDF_RECT", "LINES"})
        self.assertEqual({case["schema_valid"] for case in cases}, {True, False})

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema not installed")
    def test_agreement_with_reference_jsonschema_on_the_case_table_and_mutations(self):
        import jsonschema

        schema = C.load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        reference = jsonschema.Draft202012Validator(schema)
        ours = Validator(schema)
        cases = [case["record"] for case in schema_cases()]
        for mode, locations in VALID_LOCATIONS.items():
            for location in locations:
                cases += [document(mode, location), {"subject": [end("pdf")], "object": [end(mode, location)]}]
        cases += [document(mode) for mode in VALID_LOCATIONS]
        cases += [{"object": [], "location": {"page": 1}}, {"subject": "a.pdf", "object": []}]
        cases += [document("pdf", location) for location in (
            {"page": 1, "rect": [0, 0, 1, 1], "quote": {"exact": "a"}}, {"quote": {"exact": "a"}},
            {"page": 1, "quote": {"exact": ""}}, {"page": 1, "quote": {"exact": "a", "extra": 1}},
            {"page": 1, "quote": {"exact": "a"}, "extra": 1}, {"page": 1, "quote": []})]
        cases += [{"subject": [{"type": "html", "uri": uri}], "object": []}
                  for uri in ("a%20", "a%zz", "a%", "a‮b", "﻿a", "a​")]
        cases += [{"subject": [{"type": "html", "uri": "a", "identifiers": {name: "x"}}], "object": []}
                  for name in ("doi", "", "a b", "a⁦", "100%")]
        cases += [document("html", {"fragment": fragment}) for fragment in ("100%", "#a", "a#", "a　b", "a\n")]
        cases += [document(mode, {"module": "M", "lines": lines}) for mode in ("lean", "latex")
                  for lines in ([1], [1, 2], [], [0], [1, 2, 3], [1.0], [True])]
        randomizer = random.Random(917)
        values = [None, False, 0, 1, 1.5, "", "a", "a\n", "a b", "0" * 64, {}, [], [1], [1, 2], [2, 1], [0, 0, 1, 1],
                  [{}], ["a"], ["a", "b"], [""], {"type": "pdf", "uri": "a"}, [{"type": "pdf", "uri": "a"}],
                  {"uri": "a"}, {"type": "pdf"},
                  [{"type": "lean", "uri": "a", "location": {"module": "M", "lines": [1]}}],
                  {"id": "a", "type": "book"}, {"id": "a"}, {"wikidata": "Q1"}, {"doi": 1}, {"a b": "x"},
                  {"value": "a"}, {"pin": {"type": "book"}}, {"type": "book", "title": "Notes"},
                  {"profile": "urn:x"}, {"profile": "a b"}, {"profile": "urn:x", "page": 0},
                  {"page": 1, "quote": {"exact": "a"}}, {"page": 1, "rect": [0, 0, 1, 1], "quote": {"exact": "a"}},
                  {"declaration": "x"}, {"declaration": "x", "lines": [1]}, {"module": "M", "lines": [3]},
                  {"lines": [1]}, {"label": "a"}, {"fragment": "a"}]
        for _ in range(240):
            mode = randomizer.choice(list(VALID_LOCATIONS))
            doc = document(mode, copy.deepcopy(randomizer.choice(VALID_LOCATIONS[mode])))
            first, last = doc["subject"][0], doc["object"][0]
            node, key = randomizer.choice([
                (doc, "subject"), (doc, "object"), (doc, "relation"), (doc, "status"), (doc, "kind"), (doc, "id"),
                (doc, "note"), (doc, "junk"), (doc, "extensions"), (doc, "$schema"), (doc, "version"), (doc, "source"),
                (doc, "target"), (first, "junk"), (first, "type"), (first, "uri"), (first, "location"),
                (first, "version"), (first, "sha256"), (first, "citation"), (first, "identifiers"), (first, "title"),
                (first, "role"), (first, "extensions"), (first, "pin"),
                (last, "type"), (last, "location"), (last, "citation"), (last, "junk")])
            node[key] = copy.deepcopy(randomizer.choice(values))
            cases.append(doc)
        for doc in cases:
            with self.subTest(document=doc):
                self.assertEqual(ours.is_valid(doc), reference.is_valid(doc))


class TestSchemaEvaluator(unittest.TestCase):
    def test_supported_empty_and_boolean_rules_still_work(self):
        cases = [(True, None, True), (False, None, False), ({}, {}, True),
                 ({"$schema": "https://json-schema.org/draft/2020-12/schema#"}, None, True),
                 ({"required": []}, {}, True), ({"enum": []}, None, False),
                 ({"enum": [True, 1, 1.0]}, 1, True),
                 # jsonschema before 4.21 wrongly accepts this nested True.
                 ({"enum": [{"n": [1, None]}]}, {"n": [True, None]}, False),
                 ({"uniqueItems": False}, [1, 1], True),
                 ({"type": ["null", "number"]}, False, False),
                 ({"minLength": 1.0}, "😀", True),
                 ({"minItems": 0.0, "maxItems": 0.0}, [], True),
                 ({"allOf": [True, {"not": False}]}, {}, True),
                 ({"additionalProperties": {"type": "integer"}}, {"a": "x"}, False),
                 ({"type": "null"}, None, True)]
        for schema, value, expected in cases:
            with self.subTest(schema=schema, value=value):
                self.assertEqual(Validator(schema).is_valid(value), expected)

    def test_unimplemented_keywords_are_refused(self):
        for schema in ({"properties": {"a": {"format": "date-time"}}}, {"allOf": [{"format": "date-time"}]},
                       {"not": {"format": "date-time"}}, {"$ref": "other.json"}, {"$ref": "#/$defs/missing"}):
            with self.subTest(schema=schema), self.assertRaises(SchemaError):
                Validator(schema)
        with self.assertRaises(SchemaError):
            Validator({"type": "nul"}).is_valid(1)

    def test_a_banned_set_of_keys_is_named(self):
        self.assertEqual(Validator({"not": {"required": ["a", "b", "c"]}}).errors({"a": 1, "b": 2, "c": 3}),
                         [("$", "must not have all of 'a', 'b' and 'c'")])
        generic = [("$", "matches a shape that is not allowed here (not)")]
        self.assertEqual(Validator({"not": {"required": ["a", "b"]}}).errors(3), generic)
        self.assertEqual(Validator({"not": {"required": ["a"]}}).errors({"a": 1}), generic)
        self.assertEqual(Validator({"not": {"required": ["a", "b"], "type": "object"}}).errors({"a": 1, "b": 2}),
                         generic)

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema not installed")
    def test_supported_applicators_agree_with_reference_on_json_values(self):
        import jsonschema

        schemas = [
            {"enum": [True, {"n": [1, None]}, "😀"]}, {"const": {"n": [1, None]}},
            {"type": "array", "items": {"type": "integer"}, "uniqueItems": True},
            {"type": "string", "minLength": 1, "maxLength": 2, "pattern": "😀|a"},
            {"type": "object", "properties": {"a": {"type": "number"}},
             "patternProperties": {"a": {"minimum": 2}}, "additionalProperties": False},
            {"if": {"type": "integer"}, "then": {"minimum": 2}, "else": {"const": None}},
            {"anyOf": [{"type": "integer"}, {"type": "string"}]},
            {"oneOf": [{"type": "integer"}, {"type": "number"}]},
            {"allOf": [{"not": {"type": "boolean"}}, {"enum": [1, 1.0, False]}]},
            {"$defs": {"a/b": {"type": "number"}}, "$ref": "#/$defs/a~1b", "minimum": 2},
        ]
        values = [None, False, True, 0, 1, 1.0, 2, 1.5, "", "a", "😀", "😀a", "aaa",
                  [], [1, True], [1, 1.0], [{"n": 1}, {"n": 1.0}], {"n": [1, None]},
                  {}, {"a": 1}, {"a": 2}, {"a": "2"}, {"b": 2}]
        for schema in schemas:
            jsonschema.Draft202012Validator.check_schema(schema)
            reference = jsonschema.Draft202012Validator(schema)
            ours = Validator(schema)
            for value in values:
                with self.subTest(schema=schema, value=value):
                    self.assertEqual(ours.is_valid(value), reference.is_valid(value))


if __name__ == "__main__":
    unittest.main()
