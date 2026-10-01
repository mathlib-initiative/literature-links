"""The stable Python API: exactly each module's ``__all__``.

The stable API of each module is its ``__all__``; a name leaves it only in a
major release.  ``EXPECTED_ALL`` pins the names of every module, so a name
cannot appear in or leave ``__all__`` unnoticed.
"""
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
# The copy under test is the one Python imports (see test_packaging.py).
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                  # noqa: E402

PACKAGE = "formal_companion_annotations"
MODULES = ("ids", "schemacheck", "validate", "vocab")

#: The public names of each module (docs/annotations.md section 11.6 and README.md).
EXPECTED_ALL = {
    "validate": {
        "LINTS", "LoadError", "PROFILES", "Problem", "RECORD_ARRAYS", "Report", "SCHEMA_DIR", "SCHEMA_PATH",
        "canonical_dumps", "canonicalize", "check", "loads", "main", "order_key", "schema_path",
        "site_sha256", "validate",
    },
    "schemacheck": {"SchemaError", "Validator"},
    "ids": {
        "AnonymousDecl", "scan_file", "assign_ids", "ordinal_ids", "statement_sha256", "hash_form",
        "normalize_statement", "anonymous_id", "private_id", "signature_at", "item_label_id",
        "passage_quote_id", "passage_page_id", "normalize_text", "HASH_ID", "DECLARED_ID",
    },
    "vocab": {
        "ANNOTATION_ARTIFACT_KINDS", "ANNOTATION_CHANGELOG_EVENTS", "ANNOTATION_CHANGELOG_REASONS",
        "ANNOTATION_CHANGELOG_SUBJECTS", "ANNOTATION_CONFORMS_TO", "ANNOTATION_COORDINATE_ORIGINS",
        "ANNOTATION_COORDINATE_UNITS", "ANNOTATION_COORDINATE_X_AXES", "ANNOTATION_COORDINATE_Y_AXES",
        "ANNOTATION_COVERAGE", "ANNOTATION_DESTINATION_RESOLUTIONS", "ANNOTATION_DESTINATION_SITES",
        "ANNOTATION_ID_SOURCES", "ANNOTATION_ITEM_FORMS", "ANNOTATION_ITEM_ID_SOURCES",
        "ANNOTATION_ITEM_RELATIONS", "ANNOTATION_LEAN_KINDS", "ANNOTATION_LINK_RELATIONS",
        "ANNOTATION_LINK_ROLES", "ANNOTATION_MEMBER_PARENT_KINDS", "ANNOTATION_MEMBERSHIP_ROLES",
        "ANNOTATION_ORIGIN_Y_AXIS", "ANNOTATION_PAGE_ANCHORS", "ANNOTATION_PAGE_BASES", "ANNOTATION_PAGE_BOXES",
        "ANNOTATION_PROFILE_VERSIONS", "ANNOTATION_PROFILES", "ANNOTATION_PROVENANCE_ACTORS",
        "ANNOTATION_PROVENANCE_METHODS", "ANNOTATION_RESOLUTION_STATES", "ANNOTATION_SCHEMA",
        "ANNOTATION_SCHEMA_ID_BASE", "ANNOTATION_SCHEMA_MAJOR", "ANNOTATION_SCHEMA_VERSION",
        "ANNOTATION_SELECTOR_TYPES", "ANNOTATION_SEVERITIES", "ANNOTATION_SORRY_CLASSES",
        "ANNOTATION_SOURCE_KINDS", "ANNOTATION_SOURCE_ROLES", "ANNOTATION_SOURCE_SCOPES",
        "ANNOTATION_TEXT_CASE", "ANNOTATION_TEXT_ORIGINS", "ANNOTATION_TEXT_UNICODE",
        "ANNOTATION_TEXT_WHITESPACE", "ANNOTATION_UNATTRIBUTED_CLAIMS", "ANNOTATION_VERDICT_STATUSES",
        "ANNOTATION_VERDICTS", "ANNOTATION_XREF_DATABASES", "ANONYMOUS_KEYWORDS", "CONFORMS_TO_HTML",
        "CONFORMS_TO_MEDIA", "CONFORMS_TO_PDF", "CONFORMS_TO_PDF_RFC3778", "CONFORMS_TO_TEXT",
        "DECLARED_ID_PATTERN", "DECLARED_SLUG_PATTERN", "HASH_ID_PATTERN", "PASSAGE_PAGE_ID_PATTERN",
        "PASSAGE_QUOTE_ID_PATTERN",
    },
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
        self.assertEqual(formal_companion_annotations.__version__, "1.0.0rc2")
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

    def test_all_is_exactly_the_documented_names(self):
        for name, expected in EXPECTED_ALL.items():
            with self.subTest(module=name):
                self.assertEqual(set(module(name).__all__), expected)
        self.assertEqual(set(EXPECTED_ALL), set(MODULES))

    def test_the_old_scanner_names_are_private(self):
        ids = module("ids")
        for name in ("strip_comments", "blank_literals", "token_at", "named_signature", "comment_tags",
                     "statement_span", "declared_tag"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(ids, name), f"ids.{name} is not public")


class TestTyped(unittest.TestCase):
    """The package ships ``py.typed``, so every public function and method is fully annotated."""

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


class TestTheCheckersApi(unittest.TestCase):

    def test_the_record_types_keep_their_fields(self):
        """A reader takes these fields of the records the API returns."""
        validate = module("validate")
        self.assertEqual([f.name for f in dataclasses.fields(validate.Problem)], ["code", "path", "message"])
        self.assertEqual([f.name for f in dataclasses.fields(validate.Report)], ["problems", "warnings"])
        self.assertTrue(issubclass(validate.LoadError, ValueError))
        problem = validate.Problem("I3", "$.links[0].item", "'x' is not an id in items[]")
        self.assertEqual(str(problem), "$.links[0].item: 'x' is not an id in items[]")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            problem.code = "I4"                                         # type: ignore[misc]
        report = validate.Report()
        self.assertTrue(report.ok)
        report.problems.append(problem)
        self.assertFalse(report.ok)
        self.assertEqual(validate.LINTS, frozenset({"external-urls"}))
        self.assertIsInstance(validate.LINTS, frozenset)

    def test_check_and_validate_take_the_documented_keywords(self):
        validate = module("validate")
        for fn in (validate.check, validate.validate):
            with self.subTest(function=fn.__name__):
                params = inspect.signature(fn).parameters
                self.assertEqual(list(params), ["doc", "text", "canonical", "lints", "schema"])
                self.assertTrue(all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in list(params.values())[1:]))
        self.assertEqual(list(inspect.signature(validate.loads).parameters), ["text"])
        self.assertEqual(list(inspect.signature(validate.schema_path).parameters), ["major", "minor"])

    def test_profiles_is_the_complete_ownership_table(self):
        validate, vocab = module("validate"), module("vocab")
        self.assertEqual(set(validate.PROFILES), set(vocab.ANNOTATION_PROFILES))
        for name, owned in validate.PROFILES.items():
            with self.subTest(profile=name):
                self.assertEqual(set(owned), {"arrays", "fields"})
                self.assertTrue(all(a in validate.RECORD_ARRAYS for a in owned["arrays"]))
                for dotted in owned["fields"]:
                    head, _, field_name = dotted.partition(".")
                    self.assertTrue(head == "companion" or head in validate.RECORD_ARRAYS, dotted)
                    self.assertTrue(field_name)


if __name__ == "__main__":
    unittest.main()
