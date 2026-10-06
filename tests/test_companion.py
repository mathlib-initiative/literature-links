"""The v2 companion contract: small associations, opaque data, offline checks."""
from __future__ import annotations

import copy
import importlib.util
import json
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import companion as C
from formal_companion_annotations.schemacheck import Validator


def document(mode: str = "latex", location: dict | None = None) -> dict:
    annotation = {"target": "../formal/Groups.html#Lagrange"}
    if location is not None:
        annotation["location"] = location
    return {"version": 2, "source": {"type": mode, "uri": "chapters/groups.tex"},
            "annotations": [annotation]}


VALID_LOCATIONS = {
    "pdf": [{"page": 1}, {"page": 7, "rect": [0.1, 0.2, 0.6, 0.1]},
            {"page": 2, "rect": [0, 0, 1, 1]}, {"page": 2, "rect": [0.9, 0.9, 0.1, 0.1]}],
    "latex": [{"label": "thm:α_2.1"}, {"lines": [1, 1]}, {"lines": [12, 18]}],
    "html": [{"fragment": "thm-lagrange"}, {"fragment": "thm:α%20"},
             {"css": "article > h2[data-kind='theorem']"},
             {"quote": {"exact": "a finite group", "prefix": "Let ", "suffix": " be given."}}],
    "generic": [{}, {"profile": "https://example.org/image-v1", "rect": [0, 1, 20, 30]},
                {"database": {"row": 4, "cell": "A", "values": [None, True, 2.5, "text"]}}],
}


class TestSmallContract(unittest.TestCase):
    def test_every_builtin_and_generic_location(self):
        for mode, locations in VALID_LOCATIONS.items():
            for location in locations:
                with self.subTest(mode=mode, location=location):
                    self.assertEqual(C.validate(document(mode, location)), [])

    def test_omitted_location_means_whole_resource_in_all_modes(self):
        for mode in VALID_LOCATIONS:
            with self.subTest(mode=mode):
                self.assertEqual(C.validate(document(mode)), [])

    def test_an_empty_companion_needs_no_invented_declarations(self):
        doc = document()
        doc["annotations"] = []
        self.assertEqual(C.validate(doc), [])

    def test_required_fields_and_object_shapes(self):
        cases = [None, [], 2, "document", {}, {"version": 2}]
        for field in ("version", "source", "annotations"):
            doc = document()
            del doc[field]
            cases.append(doc)
        for field in ("type", "uri"):
            doc = document()
            del doc["source"][field]
            cases.append(doc)
        doc = document()
        doc["annotations"] = [{}]
        cases.append(doc)
        for bad in cases:
            with self.subTest(document=bad):
                self.assertTrue(C.validate(bad))

    def test_only_explicit_version_two_and_supported_modes(self):
        for version in (None, True, False, "2", 1, 3, 2.1, "2.0"):
            doc = document()
            doc["version"] = version
            with self.subTest(version=version):
                self.assertTrue(C.validate(doc))
        for mode in ("markdown", "wikitext", "tex", "web", "PDF", "", None):
            doc = document()
            doc["source"]["type"] = mode
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(doc))

    def test_core_typos_and_legacy_inventories_are_rejected(self):
        for place, key in (("root", "sources"), ("root", "mode"), ("source", "format"),
                           ("annotation", "targets"), ("annotation", "locaton")):
            doc = document()
            node = doc if place == "root" else (doc["source"] if place == "source" else doc["annotations"][0])
            node[key] = []
            with self.subTest(place=place, key=key):
                self.assertTrue(C.validate(doc))

    def test_multiple_sources_are_separate_documents(self):
        first, second = document("pdf", {"page": 1}), document("html", {"fragment": "a"})
        second["source"]["uri"] = "chapter.html"
        self.assertEqual(C.validate(first), [])
        self.assertEqual(C.validate(second), [])
        self.assertTrue(C.validate([first, second]))
        first["source"] = [first["source"], second["source"]]
        self.assertTrue(C.validate(first))

    def test_multiple_targets_repeat_the_association(self):
        doc = document("latex", {"label": "thm:lagrange"})
        second = copy.deepcopy(doc["annotations"][0])
        second["target"] = "urn:lean:other_declaration"
        doc["annotations"].append(second)
        self.assertEqual(C.validate(doc), [])
        doc["annotations"][0]["target"] = ["urn:lean:first", "urn:lean:second"]
        self.assertTrue(C.validate(doc))

    def test_annotation_ids_are_optional_but_unique_when_present(self):
        doc = document()
        doc["annotations"].append(copy.deepcopy(doc["annotations"][0]))
        self.assertEqual(C.validate(doc), [])
        for annotation in doc["annotations"]:
            annotation["id"] = "a"
        self.assertTrue(any("duplicates" in error for error in C.validate(doc)))
        doc["annotations"][1]["id"] = "b"
        doc["extensions"] = {"id": "a", "tool": {"id": "a"}}
        doc["source"]["extensions"] = {"id": "a"}
        self.assertEqual(C.validate(doc), [])
        for invalid in ("", None, 3, True):
            doc["annotations"][1]["id"] = invalid
            with self.subTest(id=invalid):
                self.assertTrue(C.validate(doc))

    def test_check_does_not_mutate_or_sort(self):
        doc = document("generic", {"z": [3, 2, 1], "a": {"key": "value"}})
        doc["annotations"] = [{"id": "z", "target": "urn:z"}, *doc["annotations"], {"id": "a", "target": "urn:a"}]
        before = copy.deepcopy(doc)
        self.assertEqual(C.check(doc), C.Report())
        self.assertEqual(doc, before)
        self.assertEqual(list(doc["annotations"][1]["location"]), ["z", "a"])


class TestReferencesAndExtensions(unittest.TestCase):
    def test_references_allow_relative_unicode_and_opaque_identifiers(self):
        references = ("groups.tex", "../docs/Groups.html#Lagrange", "#theorem", "/docs/α.html",
                      "https://example.org/α?x=1#theorem", "urn:lean:Nat.add_comm",
                      "git+https://example.org/repo", "custom:record/1", "javascript:alert(1)")
        for reference in references:
            doc = document()
            doc["source"]["uri"] = reference
            doc["annotations"][0]["target"] = reference
            with self.subTest(reference=reference):
                self.assertEqual(C.validate(doc), [])

    def test_references_disallow_literal_whitespace_controls_and_wrong_types(self):
        invalid = ("", " ", "a b", "url\n", "\turl", "url\x00", "url\x7f", "url\x85", "url\u00a0", None, 1, [], {})
        for value in invalid:
            for key in ("source", "target"):
                doc = document()
                if key == "source":
                    doc["source"]["uri"] = value
                else:
                    doc["annotations"][0]["target"] = value
                with self.subTest(value=value, key=key):
                    self.assertTrue(C.validate(doc))

    def test_no_references_or_selector_payloads_are_fetched_or_executed(self):
        doc = document("generic", {"profile": "https://unreachable.invalid/schema", "script": "arbitrary content"})
        doc["$schema"] = "https://unreachable.invalid/companion.json"
        doc["source"]["uri"] = "https://unreachable.invalid/source"
        doc["annotations"][0]["target"] = "https://unreachable.invalid/target"
        with patch("socket.socket", side_effect=AssertionError("unexpected network access")):
            self.assertEqual(C.validate(doc), [])

    def test_extensions_are_available_without_registration_at_all_three_levels(self):
        doc = document()
        payload = {"org.example.tool": {"a key with spaces": [None, True, False, 1, 0.5, "α"]},
                   "local": None, "https://example.org/profile": {}}
        for node in (doc, doc["source"], doc["annotations"][0]):
            node["extensions"] = copy.deepcopy(payload)
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), doc)

    def test_extension_keys_are_nonempty_without_whitespace_or_control(self):
        for key in ("", "tool name", "tool\n", "tool\x00", "tool\x7f", "tool\x85"):
            doc = document()
            doc["extensions"] = {key: None}
            with self.subTest(key=key):
                self.assertTrue(C.validate(doc))

    def test_extensions_require_objects(self):
        for value in (None, "extension", [1], True):
            doc = document()
            doc["extensions"] = value
            with self.subTest(value=value):
                self.assertTrue(C.validate(doc))


class TestLocatorBounds(unittest.TestCase):
    def test_empty_builtin_locations_are_not_whole_resource_aliases(self):
        for mode in ("pdf", "latex", "html"):
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(document(mode, {})))
        self.assertEqual(C.validate(document("generic", {})), [])

    def test_pdf_physical_pages_are_positive_integers(self):
        for page in (0, -1, 1.5, True, False, "1", None):
            with self.subTest(page=page):
                self.assertTrue(C.validate(document("pdf", {"page": page})))

    def test_pdf_rectangles_require_page_positive_extent_and_page_bounds(self):
        invalid = ([0, 0, 0, 1], [0, 0, 1, 0], [-0.1, 0, 0.5, 0.5], [0, 0, 1.1, 0.5],
                   [0.7, 0, 0.4, 1], [0, 0.7, 1, 0.4], [1, 0, 0.1, 1],
                   [0.9, 0, 0.10000000000000002, 1], [1e-100, 0, 1, 1],
                   [0, 0, 1], [0, 0, 1, 1, 1], [True, 0, 1, 1], "0,0,1,1")
        for rectangle in invalid:
            with self.subTest(rect=rectangle):
                self.assertTrue(C.validate(document("pdf", {"page": 1, "rect": rectangle})))
        self.assertTrue(C.validate(document("pdf", {"rect": [0, 0, 1, 1]})))

    def test_latex_anchor_alternatives_and_inclusive_ranges(self):
        invalid = ({"label": ""}, {"label": "a", "lines": [1, 2]}, {"lines": [2, 1]},
                   {"lines": [0, 1]}, {"lines": [1, 1.5]}, {"lines": [True, 2]},
                   {"lines": [1]}, {"lines": [1, 2, 3]}, {"line": 1}, {"label": "a", "file": "other.tex"})
        for location in invalid:
            with self.subTest(location=location):
                self.assertTrue(C.validate(document("latex", location)))

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
            doc["annotations"][0]["location"] = value
            with self.subTest(location=value):
                self.assertTrue(C.validate(doc))


class TestStrictJson(unittest.TestCase):
    def test_duplicate_keys_are_rejected_at_every_depth(self):
        for text in ('{"version":2,"version":2}', '{"extensions":{"tool":1,"tool":2}}',
                     '{"location":{"nested":{"same":1,"same":2}}}'):
            with self.subTest(text=text), self.assertRaises(C.LoadError):
                C.loads(text)

    def test_nonfinite_json_literals_and_overflow_are_rejected(self):
        for text in ("NaN", "Infinity", "-Infinity", "1e999", '-1e999', '{"a":[1e999]}'):
            with self.subTest(text=text), self.assertRaises(C.LoadError):
                C.loads(text)

    def test_python_only_values_are_rejected_even_inside_extensions(self):
        for value in (float("nan"), float("inf"), float("-inf"), (1, 2), {1: "value"}, {1, 2}, b"value", object()):
            doc = document()
            doc["extensions"] = {"tool": {"nested": value}}
            with self.subTest(value=repr(value)):
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
            with self.subTest(text=text), self.assertRaises(C.LoadError):
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
        self.assertEqual(list(result["annotations"][0]["location"]), ["z", "a"])
        self.assertEqual(list(result["annotations"][0]["location"]["z"]), ["β", "α"])
        self.assertTrue(text.endswith("\n"))
        self.assertIn("β", text)

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
        doc["source"]["type"] = large
        self.assertTrue(C.validate(doc))


class TestSchema(unittest.TestCase):
    def test_both_repository_and_installed_schema_copies_match(self):
        repo = ROOT / "schema" / "companion-v2.schema.json"
        source = ROOT / "src" / "formal_companion_annotations" / "schema" / "companion-v2.schema.json"
        self.assertEqual(repo.read_bytes(), source.read_bytes())
        self.assertEqual(repo.read_bytes(), C.SCHEMA_PATH.read_bytes())
        self.assertEqual(C.load_schema()["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_semantic_invariants_are_additional_to_structure(self):
        structural = Validator(C.load_schema())
        invalid = [document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]}),
                   document("latex", {"lines": [4, 2]})]
        duplicate = document()
        duplicate["annotations"] = [{"id": "same", "target": "urn:a"}, {"id": "same", "target": "urn:b"}]
        invalid.append(duplicate)
        for doc in invalid:
            with self.subTest(document=doc):
                self.assertTrue(structural.is_valid(doc))
                self.assertTrue(C.validate(doc))

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema not installed")
    def test_agreement_with_reference_jsonschema_on_boundary_mutations(self):
        import jsonschema

        schema = C.load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        reference = jsonschema.Draft202012Validator(schema)
        ours = Validator(schema)
        cases = [document(mode, location) for mode, locations in VALID_LOCATIONS.items() for location in locations]
        cases += [document(mode) for mode in VALID_LOCATIONS]
        randomizer = random.Random(917)
        values = [None, False, 0, 1, 1.5, "", "a", "a\n", {}, [], [1], [1, 2], [0, 0, 1, 1]]
        for _ in range(160):
            mode = randomizer.choice(list(VALID_LOCATIONS))
            doc = document(mode, copy.deepcopy(randomizer.choice(VALID_LOCATIONS[mode])))
            annotation = doc["annotations"][0]
            node, key = randomizer.choice([(doc, "version"), (doc, "annotations"),
                                           (doc["source"], "type"), (doc["source"], "uri"),
                                           (annotation, "target"), (annotation, "id"),
                                           (annotation, "location"), (doc, "extensions")])
            node[key] = copy.deepcopy(randomizer.choice(values))
            cases.append(doc)
        for doc in cases:
            with self.subTest(document=doc):
                self.assertEqual(ours.is_valid(doc), reference.is_valid(doc))


if __name__ == "__main__":
    unittest.main()
