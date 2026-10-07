"""Explicit module exports, annotations, and retained legacy API compatibility."""
from __future__ import annotations

import dataclasses
import importlib
import importlib.util
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                  # noqa: E402

PACKAGE = "formal_companion_annotations"
MODULES = ("ids", "schemacheck", "validate", "vocab", "companion", "migration", "cli", "discovery")

SHARED_SETS = ("FINDING_KINDS", "LEDGER_VERDICTS", "RESOLUTION_PREFIXES", "SORRY_CLASSES", "SOURCE_ROLES",
               "STATIC_RESOLUTIONS", "VIEWER_SEVERITIES", "VIEWER_STATUS", "VIEWER_VERDICTS")

# Names consumed by the original formal-companion tooling. Keep this compatibility
# surface explicit while new integrations use companion and discovery.
LEGACY_API = {
    "ids": (
        "AnonymousDecl", "DECLARED_ID", "assign_ids", "blank_literals", "item_label_id", "named_signature",
        "normalize_text", "ordinal_ids", "passage_page_id", "passage_quote_id", "private_id", "scan_file",
        "statement_sha256", "strip_comments", "token_at",
    ),
    "validate": (
        "LoadError", "RECORD_ARRAYS", "canonical_dumps", "canonicalize", "check", "loads", "order_key",
        "site_sha256", "validate",
    ),
    "schemacheck": ("SchemaError", "Validator"),
    "vocab": (
        "ANNOTATION_SCHEMA", "ANNOTATION_SCHEMA_VERSION", "CONFORMS_TO_HTML", "CONFORMS_TO_PDF",
        "ANNOTATION_RESOLUTION_STATES", "ANNOTATION_SCHEMA_MAJOR", *SHARED_SETS,
    ),
}


def module(name: str):
    return importlib.import_module(f"{PACKAGE}.{name}")


class TestAll(unittest.TestCase):

    def test_every_module_declares_its_api(self):
        for name in (*MODULES, "__main__"):
            with self.subTest(module=name):
                exported = module(name).__all__
                self.assertIsInstance(exported, list)
                self.assertEqual(len(exported), len(set(exported)), "a name is listed twice")

    def test_every_exported_name_exists(self):
        for name in MODULES:
            mod = module(name)
            for attr in mod.__all__:
                with self.subTest(module=name, name=attr):
                    self.assertTrue(hasattr(mod, attr))

    def test_the_package_exports_its_version_and_modules(self):
        self.assertEqual(formal_companion_annotations.__all__, ["__version__", *MODULES])
        namespace: dict = {}
        exec(f"from {PACKAGE} import *", namespace)
        for attr in formal_companion_annotations.__all__:
            with self.subTest(name=attr):
                self.assertIn(attr, namespace)
        self.assertIs(namespace["validate"], module("validate"))

    def test_the_entry_point_exports_nothing(self):
        self.assertEqual(module("__main__").__all__, [])

    def test_a_star_import_gives_exactly_all(self):
        for name in MODULES:
            with self.subTest(module=name):
                namespace: dict = {}
                exec(f"from {PACKAGE}.{name} import *", namespace)
                namespace.pop("__builtins__", None)
                self.assertEqual(set(namespace), set(module(name).__all__))

    def test_every_vocab_constant_is_public(self):
        vocab = module("vocab")
        constants = {n for n in vars(vocab) if n.isupper() and not n.startswith("_")}
        self.assertEqual(constants, set(vocab.__all__))


class TestTyped(unittest.TestCase):

    def test_py_typed_ships_with_the_package(self):
        marker = Path(formal_companion_annotations.__file__).resolve().parent / "py.typed"
        self.assertTrue(marker.is_file(), marker)

    def test_every_public_callable_is_annotated(self):
        for name in MODULES:
            mod = module(name)
            for attr in mod.__all__:
                obj = getattr(mod, attr)
                if inspect.isclass(obj):
                    functions = [(f"{attr}.{n}", f) for n, f in vars(obj).items()
                                 if inspect.isfunction(f) and (not n.startswith("_") or n == "__init__")]
                elif inspect.isfunction(obj):
                    functions = [(attr, obj)]
                else:
                    continue
                for label, fn in functions:
                    signature = inspect.signature(fn)
                    with self.subTest(module=name, name=label):
                        self.assertIsNot(signature.return_annotation, inspect.Signature.empty)
                        for p in signature.parameters.values():
                            if p.name in ("self", "cls"):
                                continue
                            self.assertIsNot(p.annotation, inspect.Parameter.empty, p.name)


class TestLegacyCompatibility(unittest.TestCase):

    def test_existing_legacy_imports_remain_exported(self):
        for name, used in LEGACY_API.items():
            exported = set(module(name).__all__)
            for attr in used:
                with self.subTest(module=name, name=attr):
                    self.assertIn(attr, exported, f"legacy tooling uses {name}.{attr}, which is not in __all__")

    def test_the_record_types_keep_their_fields(self):
        ids, validate = module("ids"), module("validate")
        self.assertEqual([f.name for f in dataclasses.fields(ids.AnonymousDecl)],
                         ["file", "line", "keyword", "statement_sha256", "typed", "declared_id", "signature",
                          "rejected_tag", "comment_tags"])
        self.assertEqual([f.name for f in dataclasses.fields(validate.Report)], ["problems", "warnings"])
        self.assertTrue(issubclass(validate.LoadError, ValueError))


if __name__ == "__main__":
    unittest.main()
