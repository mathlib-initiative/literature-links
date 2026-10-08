"""The single-annotation companion contract: small associations, opaque data, offline checks."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
import importlib.util
import math
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import companion as C
from formal_companion_annotations.schemacheck import SchemaError, Validator


def document(mode: str = "latex", location: dict | None = None) -> dict:
    annotation = {"source": {"type": mode, "uri": "chapters/groups.tex"},
                  "target": "../formal/Groups.html#Lagrange"}
    if location is not None:
        annotation["location"] = location
    return annotation


VALID_LOCATIONS = {
    "pdf": [{"page": 1}, {"page": 7, "rect": [0.1, 0.2, 0.6, 0.1]},
            {"page": 2, "rect": [0, 0, 1, 1]}, {"page": 2, "rect": [0.9, 0.9, 0.1, 0.1]}],
    "latex": [{"label": "thm:α_2.1"}, {"lines": [1, 1]}, {"lines": [12, 18]}],
    "html": [{"fragment": "thm-lagrange"}, {"fragment": "thm:α%20"},
             {"css": "article > h2[data-kind='theorem']"}, {"css": "["},
             {"quote": {"exact": "a finite group", "prefix": "Let ", "suffix": " be given."}}],
    "generic": [{}, {"profile": "https://example.org/image-v1", "rect": [0, 1, 20, 30]},
                {"database": {"row": 4, "cell": "A", "values": [None, True, 2.5, "text"]}}],
}


class TestSmallContract(unittest.TestCase):
    def test_only_source_and_target_are_required(self):
        schema = C.load_schema()
        self.assertEqual(set(schema["required"]), {"source", "target"})
        self.assertNotIn("version", schema["properties"])
        self.assertEqual(set(document()), {"source", "target"})
        self.assertEqual(C.validate(document()), [])

    def test_every_builtin_and_generic_location(self):
        for mode, locations in VALID_LOCATIONS.items():
            for location in locations:
                with self.subTest(mode=mode, location=location):
                    self.assertEqual(C.validate(document(mode, location)), [])

    def test_omitted_location_means_whole_resource_in_all_modes(self):
        for mode in VALID_LOCATIONS:
            with self.subTest(mode=mode):
                self.assertEqual(C.validate(document(mode)), [])

    def test_collection_shapes_are_not_single_annotations(self):
        single = document()
        for records in ([], [single], [single, copy.deepcopy(single)]):
            for carrier in (records, {"source": single["source"], "annotations": records}):
                with self.subTest(carrier=carrier):
                    self.assertTrue(C.validate(carrier))
        with_extra = document()
        with_extra["annotations"] = []
        self.assertTrue(C.validate(with_extra))

    def test_required_fields_and_object_shapes(self):
        cases = [None, [], 2, "document", {}, {"version": 2}]
        for field in ("source", "target"):
            doc = document()
            del doc[field]
            cases.append(doc)
        for field in ("type", "uri"):
            doc = document()
            del doc["source"][field]
            cases.append(doc)
        for bad in cases:
            with self.subTest(document=bad):
                self.assertTrue(C.validate(bad))

    def test_version_fields_and_unsupported_modes_are_rejected(self):
        for key in ("version", "schema_version"):
            for version in (None, True, False, "2", 1, 2, 3, 2.1, "2.0"):
                doc = document()
                doc[key] = version
                with self.subTest(key=key, version=version):
                    self.assertTrue(C.validate(doc))
        for mode in ("markdown", "wikitext", "tex", "web", "PDF", "", None):
            doc = document()
            doc["source"]["type"] = mode
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(doc))

    def test_core_typos_and_wrappers_are_rejected(self):
        for place, key in (("root", "sources"), ("root", "mode"), ("source", "format"),
                           ("root", "targets"), ("root", "locaton"), ("root", "annotations")):
            doc = document()
            node = doc if place == "root" else doc["source"]
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

    def test_multiple_targets_are_separate_complete_annotations(self):
        first = document("latex", {"label": "thm:lagrange"})
        second = copy.deepcopy(first)
        second["target"] = "urn:lean:other_declaration"
        self.assertEqual(C.validate(first), [])
        self.assertEqual(C.validate(second), [])
        for targets in ([], ["urn:lean:first"], ["urn:lean:first", "urn:lean:second"]):
            first["target"] = targets
            with self.subTest(targets=targets):
                self.assertTrue(C.validate(first))

    def test_annotation_id_is_an_optional_nonempty_application_label(self):
        doc = document()
        self.assertEqual(C.validate(doc), [])
        for identity in ("a", "a label", " ", "α", "https://example.org/annotation/1"):
            doc["id"] = identity
            duplicate = copy.deepcopy(doc)
            duplicate["target"] = "urn:another"
            self.assertEqual(C.validate(doc), [])
            self.assertEqual(C.validate(duplicate), [])
        doc["extensions"] = {"id": "a", "tool": {"id": "a"}}
        doc["source"]["extensions"] = {"id": "a"}
        self.assertEqual(C.validate(doc), [])
        for invalid in ("", None, 3, True, []):
            doc["id"] = invalid
            with self.subTest(id=invalid):
                self.assertTrue(C.validate(doc))

    def test_check_does_not_mutate_or_sort(self):
        doc = document("generic", {"z": [3, 2, 1], "a": {"key": "value"}})
        doc["extensions"] = {"z": {"target": "urn:embedded", "annotations": [3, 2, 1]}, "a": 0}
        before = copy.deepcopy(doc)
        self.assertEqual(C.check(doc), C.Report())
        self.assertEqual(doc, before)
        self.assertEqual(list(doc["location"]), ["z", "a"])
        self.assertEqual(list(doc["extensions"]), ["z", "a"])


class TestReferencesAndExtensions(unittest.TestCase):
    def test_references_allow_relative_unicode_and_opaque_identifiers(self):
        references = ("groups.tex", "../docs/Groups.html#Lagrange", "#theorem", "/docs/α.html",
                      "https://example.org/α?x=1#theorem", "urn:lean:Nat.add_comm",
                      "git+https://example.org/repo", "custom:record/1", "javascript:alert(1)")
        for reference in references:
            doc = document()
            doc["source"]["uri"] = reference
            doc["target"] = reference
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
                    doc["target"] = value
                with self.subTest(value=value, key=key):
                    self.assertTrue(C.validate(doc))

    def test_no_references_or_selector_payloads_are_fetched_or_executed(self):
        doc = document("generic", {"profile": "https://unreachable.invalid/schema", "script": "arbitrary content"})
        doc["$schema"] = "https://unreachable.invalid/companion.json"
        doc["source"]["uri"] = "https://unreachable.invalid/source"
        doc["target"] = "https://unreachable.invalid/target"
        with patch("socket.socket", side_effect=AssertionError("unexpected network access")):
            self.assertEqual(C.validate(doc), [])

    def test_extensions_are_available_without_registration_at_both_levels(self):
        doc = document()
        payload = {"org.example.tool": {"a key with spaces": [None, True, False, 1, 0.5, "α"]},
                   "local": None, "https://example.org/profile": {}}
        for node in (doc, doc["source"]):
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

    def test_whitespace_definition_is_explicit_and_unicode_stable(self):
        # These cover Unicode White_Space outside ASCII, including characters
        # whose treatment differs between common regex dialects.
        forbidden = "\u0085\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
        forbidden += "".join(map(chr, range(0x21))) + "".join(map(chr, range(0x7f, 0xa0)))
        for char in forbidden:
            for value in ("x" + char + "y", "xy" + char):
                doc = document()
                doc["target"] = value
                with self.subTest(codepoint=ord(char), value=value):
                    self.assertTrue(C.validate(doc))
                    doc["target"] = "urn:valid"
                    doc["extensions"] = {value: None}
                    self.assertTrue(C.validate(doc))
        for char in ("\u180e", "\ufeff", "😀"):
            doc = document()
            doc["target"] = "urn:" + char
            doc["extensions"] = {"tool" + char: None}
            with self.subTest(non_whitespace=char):
                self.assertEqual(C.validate(doc), [])


class TestStructuredDiagnostics(unittest.TestCase):
    def test_problem_is_frozen_and_has_a_readable_string(self):
        problem = C.Problem("SCHEMA", "$.target", "must be a string")
        self.assertEqual(str(problem), "$.target: must be a string")
        with self.assertRaises(FrozenInstanceError):
            problem.code = "OTHER"

    def test_stable_codes_paths_and_convenience_strings(self):
        bad_json = document("generic", {"payload": float("inf")})
        bad_shape = document()
        bad_shape["target"] = []
        cases = [(bad_json, "JSON", '$["location"]["payload"]'),
                 (bad_shape, "SCHEMA", "$.target"),
                 (document("pdf", {"page": 1, "rect": [0, 0, 0, 1]}), "PDF_RECT", "$.location.rect"),
                 (document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]}), "PDF_RECT", "$.location.rect"),
                 (document("latex", {"lines": [5, 2]}), "LATEX_LINES", "$.location.lines")]
        for doc, code, path in cases:
            with self.subTest(code=code, path=path):
                report = C.check(doc)
                self.assertEqual(report.warnings, [])
                self.assertTrue(report.problems)
                self.assertTrue(all(isinstance(problem, C.Problem) for problem in report.problems))
                self.assertIn((code, path), [(problem.code, problem.path) for problem in report.problems])
                self.assertEqual(C.validate(doc), [str(problem) for problem in report.problems])

    def test_malformed_structure_prevents_secondary_semantic_failures(self):
        report = C.check(document("pdf", {"page": 1, "rect": [0, None, 0, "width"]}))
        self.assertTrue(report.problems)
        self.assertEqual({problem.code for problem in report.problems}, {"SCHEMA"})


class TestLocatorBounds(unittest.TestCase):
    def test_empty_builtin_locations_are_not_whole_resource_aliases(self):
        for mode in ("pdf", "latex", "html"):
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(document(mode, {})))
        self.assertEqual(C.validate(document("generic", {})), [])

    def test_null_location_is_invalid_in_every_mode(self):
        for mode in VALID_LOCATIONS:
            doc = document(mode)
            doc["location"] = None
            with self.subTest(mode=mode):
                self.assertTrue(C.validate(doc))

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
            doc["location"] = value
            with self.subTest(location=value):
                self.assertTrue(C.validate(doc))

    def test_integer_valued_json_numbers_are_valid_page_and_line_indices(self):
        # JSON Schema's integer type describes a numeric value, not its spelling.
        for number in (1.0, 2**100, 1e100):
            with self.subTest(number=number):
                self.assertEqual(C.validate(document("pdf", {"page": number})), [])
                self.assertEqual(C.validate(document("latex", {"lines": [number, number]})), [])

    def test_schema_looking_generic_payloads_are_never_interpreted(self):
        payload = {"$id": "../private.json", "$schema": "https://example.org/unknown",
                   "$ref": "https://example.org/execute", "type": "future-mode",
                   "properties": None, "\u0000": {"": [None, True, 2**100]}}
        doc = document("generic", payload)
        doc["extensions"] = {"tool": copy.deepcopy(payload)}
        original = copy.deepcopy(doc)
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), original)


class TestStrictJson(unittest.TestCase):
    def test_duplicate_keys_are_rejected_at_every_depth(self):
        for text in ('{"version":2,"version":2}', '{"extensions":{"tool":1,"tool":2}}',
                     '{"location":{"nested":{"same":1,"same":2}}}',
                     '{"source":1,"\\u0073ource":2}', '{"😀":1,"\\ud83d\\ude00":2}'):
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
        self.assertEqual(list(result["location"]), ["z", "a"])
        self.assertEqual(list(result["location"]["z"]), ["β", "α"])
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
    def test_schema_has_one_source_and_matches_installed_bytes(self):
        repo = ROOT / "schema" / "companion.schema.json"
        source = ROOT / "src" / "formal_companion_annotations" / "schema" / "companion.schema.json"
        self.assertFalse(source.exists())
        self.assertEqual(repo.read_bytes(), C.SCHEMA_PATH.read_bytes())
        self.assertEqual(C.load_schema()["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_semantic_invariants_are_additional_to_structure(self):
        structural = Validator(C.load_schema())
        invalid = [document("pdf", {"page": 1, "rect": [0.8, 0, 0.3, 1]}),
                   document("latex", {"lines": [4, 2]})]
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
            node, key = randomizer.choice([(doc, "version"), (doc, "source"),
                                           (doc["source"], "type"), (doc["source"], "uri"),
                                           (doc, "target"), (doc, "id"),
                                           (doc, "location"), (doc, "extensions")])
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
                 # Older jsonschema (4.19) wrongly accepts this nested True.
                 ({"enum": [{"n": [1, None]}]}, {"n": [True, None]}, False),
                 ({"uniqueItems": False}, [1, 1], True),
                 ({"type": ["null", "number"]}, False, False),
                 ({"minLength": 1.0}, "😀", True),
                 ({"minItems": 0.0, "maxItems": 0.0}, [], True),
                 ({"allOf": [True, {"not": False}]}, {}, True)]
        for schema, value, expected in cases:
            with self.subTest(schema=schema, value=value):
                self.assertEqual(Validator(schema).is_valid(value), expected)

    def test_unimplemented_keywords_are_refused(self):
        with self.assertRaises(SchemaError):
            Validator({"type": "string", "format": "date-time"})

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
