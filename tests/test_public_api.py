"""Explicit module exports, annotations, and the names other tools use."""
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
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(SRC))

import literature_links                                  # noqa: E402

PACKAGE = "literature_links"
MODULES = ("schemacheck", "companion", "cli", "discovery")

# Names other tools import. Removing or renaming one breaks them.
STABLE_API = {
    "companion": ("SCHEMA_PATH", "LoadError", "Problem", "Report", "check", "dumps", "load_schema", "loads",
                  "merge", "rebase", "validate"),
    "discovery": ("DEFAULTS", "Collection", "Problem", "Record", "collect", "inherit"),
    "schemacheck": ("SchemaError", "Validator"),
}


def module(name: str):
    return importlib.import_module(f"{PACKAGE}.{name}")


class TestAll(unittest.TestCase):

    def test_the_package_exports_its_version_and_modules(self):
        self.assertEqual(literature_links.__all__, ["__version__", *MODULES])
        namespace: dict = {}
        exec(f"from {PACKAGE} import *", namespace)
        for attr in literature_links.__all__:
            with self.subTest(name=attr):
                self.assertIn(attr, namespace)
        self.assertIs(namespace["companion"], module("companion"))

    def test_the_entry_point_exports_nothing(self):
        self.assertEqual(module("__main__").__all__, [])

    def test_a_star_import_gives_exactly_all(self):
        for name in MODULES:
            with self.subTest(module=name):
                namespace: dict = {}
                exec(f"from {PACKAGE}.{name} import *", namespace)
                namespace.pop("__builtins__", None)
                self.assertEqual(set(namespace), set(module(name).__all__))


class TestTyped(unittest.TestCase):

    def test_py_typed_ships_with_the_package(self):
        marker = Path(literature_links.__file__).resolve().parent / "py.typed"
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


class TestStableApi(unittest.TestCase):

    def test_used_names_remain_exported(self):
        for name, used in STABLE_API.items():
            exported = set(module(name).__all__)
            for attr in used:
                with self.subTest(module=name, name=attr):
                    self.assertIn(attr, exported, f"other tools use {name}.{attr}, which is not in __all__")

    def test_the_record_types_keep_their_fields(self):
        companion, discovery = module("companion"), module("discovery")
        expected = {companion.Problem: ["code", "path", "message"], companion.Report: ["problems", "warnings"],
                    discovery.Record: ["annotation", "path", "pointer", "line", "defaults"],
                    discovery.Collection: ["records", "problems", "files"]}
        for record, names in expected.items():
            with self.subTest(record=f"{record.__module__}.{record.__name__}"):
                self.assertEqual([f.name for f in dataclasses.fields(record)], names)
        self.assertTrue(issubclass(companion.LoadError, ValueError))
        self.assertIs(discovery.Problem, companion.Problem)


if __name__ == "__main__":
    unittest.main()
