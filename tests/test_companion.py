"""Validation and JSON reading and writing of one annotation."""
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
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

from literature_links import companion as C
from literature_links.schemacheck import SchemaError, Validator


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
    def test_every_builtin_and_generic_location(self):
        for mode, locations in VALID_LOCATIONS.items():
            for location in locations:
                with self.subTest(mode=mode, location=location):
                    self.assertEqual(C.validate(document(mode, location)), [])

    def test_omitted_location_means_whole_resource_in_all_modes(self):
        for mode in VALID_LOCATIONS:
            with self.subTest(mode=mode):
                self.assertEqual(C.validate(document(mode)), [])

    def test_a_missing_source_is_the_only_problem_it_causes(self):
        for location in ({"page": 3, "rect": [0.1, 0.2, 0.3, 0.4]}, {"label": "a"}, {"fragment": "a"}):
            for source in ({}, {"source": {"uri": "a"}}, {"source": None}, {"source": "a.pdf"}):
                with self.subTest(location=location, source=source):
                    self.assertEqual(len(C.validate({"location": location, "target": "x.html", **source})), 1)

    def test_required_fields_and_object_shapes(self):
        cases = [None, [], 2, "document", {}, {"version": 2}]
        doc = document()
        del doc["source"]
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
                      "git+https://example.org/repo", "custom:record/1", "javascript:alert(1)", "x")
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
                   [0.5, 0, 0.5000000000000002, 1], [0, 0.5, 1, 0.5000000000000002],
                   [0, 0, 1], [0, 0, 1, 1, 1], [True, 0, 1, 1], "0,0,1,1")
        for rectangle in invalid:
            with self.subTest(rect=rectangle):
                self.assertTrue(C.validate(document("pdf", {"page": 1, "rect": rectangle})))
        self.assertTrue(C.validate(document("pdf", {"rect": [0, 0, 1, 1]})))

    def test_a_pdf_rectangle_fits_when_the_double_sums_do(self):
        for rect in ([0.9, 0, 0.10000000000000002, 1], [1e-100, 0, 1, 1], [100 / 612, 0, 512 / 612, 1],
                     *([n / 997, n / 997, 1 - n / 997, 1 - n / 997] for n in range(1, 997))):
            with self.subTest(rect=rect):
                self.assertEqual(C.validate(document("pdf", {"page": 1, "rect": rect})), [])

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

    def test_profile_marks_an_application_defined_location_in_every_mode(self):
        profiled = {"pdf": {"profile": "urn:example:figure", "page": 0, "rect": [0.9, 0.9, 0.5, 0.5]},
                    "latex": {"profile": "urn:example:environment", "lines": [9, 2]},
                    "html": {"profile": "urn:example:anchor:v3", "section": "Definition", "snippet": "a group"},
                    "generic": {"profile": "https://example.org/profiles/row", "row": 4}}
        for mode, location in profiled.items():
            with self.subTest(mode=mode):
                self.assertEqual(C.validate(document(mode, location)), [])
            for profile in ("", "a b", 1, None, [], {}):
                with self.subTest(mode=mode, profile=profile):
                    self.assertTrue(C.validate(document(mode, {"profile": profile})))
        for mode, location in (("html", {"fragmnet": "x"}), ("pdf", {"pag": 1}), ("latex", {"label": "a", "extra": 1})):
            with self.subTest(mode=mode, location=location):
                self.assertTrue(C.validate(document(mode, location)))

    def test_schema_looking_generic_payloads_are_never_interpreted(self):
        payload = {"$id": "../private.json", "$schema": "https://example.org/unknown",
                   "$ref": "https://example.org/execute", "type": "future-mode",
                   "properties": None, "\u0000": {"": [None, True, 2**100]}}
        doc = document("generic", payload)
        doc["extensions"] = {"tool": copy.deepcopy(payload)}
        original = copy.deepcopy(doc)
        self.assertEqual(C.validate(doc), [])
        self.assertEqual(C.loads(C.dumps(doc)), original)


PINS = {
    "website": {"title": "C*-algebra", "owner": "Wikipedia", "revision": "1374776629", "date": "2026-09-30",
                "url": "https://en.wikipedia.org/w/index.php?title=C*-algebra&oldid=1374776629",
                "retrieved": "2026-10-01", "sha256": "0" * 64, "identifiers": {"wikidata": "Q263809"}},
    "book": {"title": "Notes", "author": ["A. Author", "B. Coauthor"], "publisher": "Example Press", "edition": "2",
             "date": "2026", "isbn": "978-0-00-000000-0", "url": "urn:isbn:9780000000000", "retrieved": "2026-10-01",
             "sha256": "f" * 64, "identifiers": {"zbl": "0000.00001"}},
    "paper": {"title": "A note", "author": "A. Author", "venue": "Journal of Examples", "volume": "1", "number": "2",
              "pages": "1-12", "date": "2026-01", "doi": "10.0000/example.0001", "arxiv": "0000.00000",
              "url": "https://example.org/paper.pdf", "retrieved": "2026-10-01", "sha256": "a" * 64, "identifiers": {}},
    "repository": {"url": "https://github.com/leanprover-community/mathlib4", "commit": "9e6b3aac" * 5,
                   "path": "Mathlib/Analysis/CStarAlgebra/Classes.lean", "line": 38,
                   "module": "Mathlib.Analysis.CStarAlgebra.Classes", "declaration": "CStarAlgebra",
                   "sha256": "4c4df77d40d71b3b3e0058720dce489e704789582f0ebb4ce464b3d5d4cfae6b", "identifiers": {}},
    "generic": {"catalogue": {"shelf": 3, "tags": ["x", None]}, "anything": 1},
}


class TestPinsAndFacts(unittest.TestCase):
    def test_target_is_optional_and_may_be_an_object(self):
        doc = document("html", {"fragment": "Quotients_and_approximate_identities"})
        del doc["target"]
        self.assertEqual(C.validate(doc), [])
        doc["status"] = "not_formalized"
        self.assertEqual(C.validate(doc), [])
        for target in ({"uri": "Mathlib/Analysis/CStarAlgebra/Classes.lean#CStarAlgebra"},
                       {"uri": "urn:lean:CStarAlgebra", "pin": {"type": "repository", **PINS["repository"]}},
                       {"uri": "a", "extensions": {"org.example": {"line": 38}}}):
            doc["target"] = target
            with self.subTest(target=target):
                self.assertEqual(C.validate(doc), [])
        for target in (None, 1, [], ["a"], {}, {"pin": {"type": "book"}}, {"uri": ""}, {"uri": "a b"},
                       {"uri": "a", "extra": 1}, {"uri": "a", "pin": {}}, {"uri": "a", "pin": "book"}):
            doc["target"] = target
            with self.subTest(target=target):
                self.assertTrue(C.validate(doc))

    def test_facts_are_optional_nonempty_strings(self):
        doc = document()
        for key in ("status", "kind", "label", "note"):
            for value in ("formalized", "definition", "A label with spaces", "α", "anything applications agree on"):
                doc[key] = value
                self.assertEqual(C.validate(doc), [], (key, value))
            for value in ("", None, 1, True, [], ["formalized"]):
                doc[key] = value
                with self.subTest(key=key, value=value):
                    self.assertTrue(C.validate(doc))
            del doc[key]
        self.assertEqual(C.validate(doc), [])

    def test_status_may_be_an_object_with_value_pin_and_extensions(self):
        doc = document("html", {"fragment": "Quotients_and_approximate_identities"})
        del doc["target"]
        mathlib = {"type": "repository", "url": "https://github.com/leanprover-community/mathlib4",
                   "commit": "9e6b3aac99b624d10c84653ab9c5357283b9b3b8"}
        for status in ({}, {"value": "not_formalized"}, {"pin": mathlib}, {"value": "not_formalized", "pin": mathlib},
                       {"value": "partial", "pin": {"type": "generic", "searched": ["Mathlib", "Batteries"]},
                        "extensions": {"org.example": {"checked": "2026-10-08"}}}):
            doc["status"] = copy.deepcopy(status)
            with self.subTest(status=status):
                self.assertEqual(C.validate(doc), [])
        for status in ({"value": ""}, {"value": 1}, {"value": None}, {"value": ["a"]}, {"pin": {}},
                       {"pin": {"type": "web"}}, {"pin": "repository"}, {"pin": {**mathlib, "author": "x"}},
                       {"extensions": []}, {"value": "a", "uri": "b"}, {"status": "a"}, [{"value": "a"}]):
            doc["status"] = status
            with self.subTest(status=status):
                self.assertTrue(C.validate(doc))
        del doc["status"]
        for key in ("kind", "label", "note"):
            doc[key] = {"value": "x"}
            with self.subTest(key=key):
                self.assertTrue(C.validate(doc))
            del doc[key]

    def test_every_pin_type_with_all_keys_and_with_type_alone(self):
        for kind, keys in PINS.items():
            for pin in ({"type": kind}, {"type": kind, **keys}):
                doc = document()
                doc["source"]["pin"] = copy.deepcopy(pin)
                doc["target"] = {"uri": "formal.html#x", "pin": copy.deepcopy(pin)}
                with self.subTest(kind=kind, pin=pin):
                    self.assertEqual(C.validate(doc), [])

    def test_pins_need_a_known_type_and_reject_unknown_keys_except_in_generic(self):
        doc = document()
        for pin in ({}, {"title": "no type"}, {"type": "web"}, {"type": None}, {"type": ""}, "book", [], None,
                    {"type": "website", "publisher": "sites have owners"}, {"type": "book", "owner": "x"},
                    {"type": "paper", "commit": "x"}, {"type": "repository", "author": "x"}):
            doc["source"]["pin"] = pin
            with self.subTest(pin=pin):
                self.assertTrue(C.validate(doc))
        doc["source"]["pin"] = {"type": "generic", "owner": "x", "commit": "y", "nested": {"a": [1, None]}}
        self.assertEqual(C.validate(doc), [])

    def test_pin_value_shapes(self):
        doc = document()
        valid = [("book", "author", "One Author"), ("book", "author", ["A", "B"]), ("book", "author", []),
                 ("repository", "line", 1), ("repository", "line", 38.0), ("website", "sha256", "0" * 64),
                 ("paper", "identifiers", {}), ("paper", "identifiers", {"doi": "10.0000/x", "arxiv": "0000.00000"}),
                 ("website", "url", "urn:example:site"), ("website", "revision", "1374776629"),
                 ("generic", "url", "catalogue/17"), ("generic", "shelf", 3)]
        for kind, key, value in valid:
            doc["source"]["pin"] = {"type": kind, key: value}
            with self.subTest(kind=kind, key=key, value=value):
                self.assertEqual(C.validate(doc), [])
        invalid = [("book", "author", ""), ("book", "author", ["A", ""]), ("book", "author", [1]), ("book", "author", None),
                   ("repository", "line", 0), ("repository", "line", "38"), ("repository", "line", 1.5),
                   ("website", "sha256", "0" * 63), ("website", "sha256", "A" * 64), ("website", "sha256", "0" * 64 + "\n"),
                   ("paper", "identifiers", {"doi": 1}), ("paper", "identifiers", {"doi": ""}), ("paper", "identifiers", []),
                   ("website", "url", "a b"), ("website", "title", ""), ("repository", "commit", 123),
                   ("generic", "url", "a b"), ("generic", "url", 5)]
        for kind, key, value in invalid:
            doc["source"]["pin"] = {"type": kind, key: value}
            with self.subTest(kind=kind, key=key, value=value):
                self.assertTrue(C.validate(doc))

    def test_every_key_of_a_builtin_pin_is_typed(self):
        wrong = {"line": (0, "1"), "author": ("", [1]), "identifiers": ([], {"a": 1})}
        for kind, keys in PINS.items():
            for key in keys if kind != "generic" else ():
                for value in wrong.get(key, (1, "")):
                    doc = document()
                    doc["source"]["pin"] = {"type": kind, key: value}
                    with self.subTest(kind=kind, key=key, value=value):
                        self.assertTrue(C.validate(doc))

    def test_pins_and_facts_are_not_verified(self):
        doc = document()
        doc["source"]["pin"] = {"type": "website", "url": "https://unreachable.invalid/", "sha256": "0" * 64}
        doc["target"] = {"uri": "urn:nothing", "pin": {"type": "repository", "commit": "not-a-commit", "line": 99999}}
        doc["status"] = "formalized"
        with patch("urllib.request.urlopen", side_effect=AssertionError("network access")):
            self.assertEqual(C.validate(doc), [])


class TestNormalize(unittest.TestCase):
    PIN = {"type": "repository", "url": "https://github.com/leanprover-community/mathlib4",
           "commit": "9e6b3aac99b624d10c84653ab9c5357283b9b3b8"}

    def test_string_target_and_status_become_objects_in_place(self):
        doc = {"source": {"type": "pdf", "uri": "a.pdf"}, "target": "A.html#x", "status": "partial", "kind": "lemma"}
        normal = C.normalize(doc)
        self.assertEqual(normal, {"source": {"type": "pdf", "uri": "a.pdf"}, "target": {"uri": "A.html#x"},
                                  "status": {"value": "partial"}, "kind": "lemma"})
        self.assertEqual(list(normal), list(doc))
        self.assertEqual(C.validate(normal), [])

    def test_object_forms_come_back_equal(self):
        doc = {"source": {"type": "generic", "uri": "a"},
               "target": {"uri": "A.html", "pin": self.PIN, "extensions": {"x.y": "B.html"}},
               "status": {"value": "not_formalized", "pin": self.PIN}}
        self.assertEqual(C.normalize(doc), doc)
        self.assertEqual(C.normalize({"status": {}}), {"status": {}})

    def test_absent_fields_stay_absent_and_nothing_else_changes(self):
        doc = {"source": {"type": "generic", "uri": "a", "extensions": {"target": "t"}},
               "extensions": {"x.y": {"target": "t", "status": "s"}}, "label": "Lemma 1"}
        self.assertEqual(C.normalize(doc), doc)
        self.assertNotIn("target", C.normalize(doc))
        self.assertEqual(C.normalize({}), {})

    def test_it_does_not_validate(self):
        for value in (None, 1, True, [], ["a"], {}, {"pin": "x"}):
            with self.subTest(value=value):
                self.assertEqual(C.normalize({"target": value, "status": value}), {"target": value, "status": value})
        self.assertEqual(C.normalize({"target": "", "status": ""}), {"target": {"uri": ""}, "status": {"value": ""}})

    def test_it_is_idempotent_and_keeps_valid_records_valid(self):
        examples = sorted((ROOT / "examples" / "companion").glob("*.json"))
        self.assertTrue(examples)
        for path in examples:
            with self.subTest(example=path.name):
                once = C.normalize(C.loads(path.read_text(encoding="utf-8")))
                self.assertEqual(C.normalize(once), once)
                self.assertEqual(C.validate(once), [])
                self.assertTrue(all(isinstance(once[key], dict) for key in ("target", "status") if key in once))

    def test_the_input_is_not_changed_or_shared(self):
        doc = {"source": {"type": "generic", "uri": "a"}, "target": "A.html",
               "status": {"value": "partial", "pin": copy.deepcopy(self.PIN)}, "extensions": {"x.y": [1]}}
        before = copy.deepcopy(doc)
        normal = C.normalize(doc)
        self.assertEqual(doc, before)
        normal["source"]["uri"] = "b"
        normal["status"]["pin"]["commit"] = "c"
        normal["extensions"]["x.y"].append(2)
        self.assertEqual(doc, before)


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
        self.assertEqual(list(result["location"]), ["z", "a"])
        self.assertEqual(list(result["location"]["z"]), ["β", "α"])
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
        doc["source"]["type"] = large
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
        cases += [{"target": "x", "location": {"page": 1}}, {"source": "a.pdf", "location": {"page": 1}}]
        cases += [{"source": {"type": "html", "uri": "a", "pin": {"type": "generic", "url": url}}} for url in (5, "a b", "a")]
        randomizer = random.Random(917)
        values = [None, False, 0, 1, 1.5, "", "a", "a\n", {}, [], [1], [1, 2], [0, 0, 1, 1],
                  {"type": "website"}, {"type": "book", "author": ["x", "y"]}, {"type": "book", "author": [1]},
                  {"type": "paper", "sha256": "ab"}, {"type": "repository", "line": 0}, {"type": "nope"},
                  {"type": "generic", "anything": [1, {}]}, {"title": "no type"}, {"type": "website", "owner": ""},
                  {"uri": "a"}, {"uri": "a", "pin": {"type": "generic"}, "extensions": {"k": 1}}, {"pin": {"type": "book"}},
                  {"uri": "a", "extra": 1}, {"type": "paper", "identifiers": {"doi": 1}},
                  {"value": "a"}, {"value": ""}, {"value": "a", "pin": {"type": "repository", "line": 1}},
                  {"value": "a", "extra": 1},
                  {"profile": "urn:x"}, {"profile": "a b"}, {"profile": "urn:x", "page": 0}]
        for _ in range(160):
            mode = randomizer.choice(list(VALID_LOCATIONS))
            doc = document(mode, copy.deepcopy(randomizer.choice(VALID_LOCATIONS[mode])))
            node, key = randomizer.choice([(doc, "version"), (doc, "source"),
                                           (doc["source"], "type"), (doc["source"], "uri"),
                                           (doc["source"], "pin"), (doc, "target"), (doc, "id"),
                                           (doc, "status"), (doc, "kind"), (doc, "label"), (doc, "note"),
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
