"""Reusable annotation cases agree with both structural and complete validation."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import companion as C
from formal_companion_annotations.schemacheck import Validator


class TestConformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = C.loads((ROOT / "conformance" / "annotations.json").read_text(encoding="utf-8"))["cases"]

    def test_corpus_expectations_are_well_formed_and_distinguish_semantics(self):
        identities = [case["id"] for case in self.cases]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(all(isinstance(identity, str) and identity for identity in identities))
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(set(case), {"id", "description", "annotation", "schema_valid", "valid", "problem_codes"})
                self.assertIsInstance(case["schema_valid"], bool)
                self.assertIsInstance(case["valid"], bool)
                self.assertEqual(case["valid"], not case["problem_codes"])
                self.assertEqual(len(case["problem_codes"]), len(set(case["problem_codes"])))
                self.assertFalse(case["valid"] and not case["schema_valid"])
        semantic_codes = {code for case in self.cases if case["schema_valid"] and not case["valid"]
                          for code in case["problem_codes"]}
        self.assertEqual(semantic_codes, {"PDF_RECT", "LATEX_LINES"})

    def test_complete_reference_validation(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                annotation = copy.deepcopy(case["annotation"])
                report = C.check(annotation)
                self.assertEqual(not report.problems, case["valid"], report.problems)
                self.assertEqual({problem.code for problem in report.problems}, set(case["problem_codes"]))
                self.assertEqual(annotation, case["annotation"], "validation must not mutate input")

    def test_bundled_structural_validation(self):
        validator = Validator(C.load_schema())
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(validator.is_valid(case["annotation"]), case["schema_valid"])

    @unittest.skipUnless(importlib.util.find_spec("jsonschema"), "optional jsonschema not installed")
    def test_independent_jsonschema_validation(self):
        import jsonschema

        schema = C.load_schema()
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(validator.is_valid(case["annotation"]), case["schema_valid"])


if __name__ == "__main__":
    unittest.main()
