"""Robustness of the checker: I-JSON limits, regex dialects, hostile input, the CLI's contract.

Each test here pins a robustness rule of the specification
(docs/annotations.md sections 4, 6 and 8): the strict I-JSON loader and the same limits on in-memory objects, the
dialect-neutral schema patterns and the checker's own ``fullmatch`` grammars,
the CLI that checks every document and never shows a traceback, ``--canonical``
on exact bytes, ``--print-canonical`` that validates first and writes UTF-8,
the stable codes, the ``--format json`` output, and the passes that must stay
linear.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                                 # noqa: E402
from formal_companion_annotations import ids                                        # noqa: E402
from formal_companion_annotations import schemacheck as S                           # noqa: E402
from formal_companion_annotations import validate as V                              # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402

PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
EXAMPLES = ROOT / "examples" / "annotations"
SCHEMA = ROOT / "schema" / "annotations-v1.0.schema.json"
VALID = ("graph-profile.json", "minimal.json", "mixed.json", "other-media.json", "pdf-region.json",
         "site-pages.json", "tex-lines.json", "web-passage.json")
#: The statement-hash id of pdf-region.json's anonymous example.
PDF_EXAMPLE = ids.anonymous_id("example", ids.statement_sha256("example : volume (Box.unit 2) = 1"))

# Characters the tests need, built from code points so the source stays ASCII.
NBSP = chr(0xA0)
BOM = chr(0xFEFF)
FILE_SEPARATOR = chr(0x1C)
ARABIC_INDIC_ZERO = chr(0x660)
LONE_SURROGATE = chr(0xD800)
JSON_LONE_SURROGATE = "\\u" + "d800"                     # the JSON escape of a lone surrogate
CS = {"origin": "top_left", "page_box": "CropBox", "units": "normalized", "x_axis": "right", "y_axis": "down"}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def by_id(records: list[dict], rid: str) -> dict:
    return next(r for r in records if r["id"] == rid)


def resort(doc: dict) -> dict:
    return V.canonicalize(doc)


def codes(doc: dict, **kwargs) -> list[str]:
    return [p.code for p in V.check(doc, **kwargs).problems]


def lines(doc: dict, **kwargs) -> list[str]:
    return [f"{p} [{p.code}]" for p in V.check(doc, **kwargs).problems]


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            status = V.main(list(argv))
        except SystemExit as exc:
            status = exc.code
    return status, out.getvalue(), err.getvalue()


def subprocess_env(**extra: str) -> dict:
    """A child ``python3 -m`` imports the copy under test (see test_packaging.py)."""
    path = os.pathsep.join(p for p in (str(PACKAGE.parent), os.environ.get("PYTHONPATH", "")) if p)
    env = dict(os.environ, PYTHONPATH=path, PYTHONDONTWRITEBYTECODE="1")
    env.pop("PYTHONIOENCODING", None)
    env.update(extra)
    return env


def run_child(*argv: str, **extra_env: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "formal_companion_annotations.validate", *argv],
                          capture_output=True, env=subprocess_env(**extra_env), cwd=ROOT, check=False)


class Temp(unittest.TestCase):
    """A temporary directory per test, and a writer of documents into it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, content: str | bytes | dict) -> Path:
        path = self.tmp / name
        if isinstance(content, dict):
            content = V.canonical_dumps(V.canonicalize(content))
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.write_bytes(content)
        return path


# ---------------------------------------------------------------------------
# 1. --canonical compares exact bytes
# ---------------------------------------------------------------------------

class TestCanonicalBytes(Temp):

    def test_crlf_and_cr_line_ends_are_not_canonical(self):
        text = (EXAMPLES / "pdf-region.json").read_text(encoding="utf-8")
        for label, body in (("crlf", text.replace("\n", "\r\n")), ("cr", text.replace("\n", "\r")),
                            ("no final newline", text.rstrip("\n")), ("two final newlines", text + "\n")):
            path = self.write(f"{label}.json", body)
            with self.subTest(label=label):
                status, out, err = run_cli(str(path), "--canonical")
                self.assertEqual(status, 1, out + err)
                self.assertIn("$: the file is not in canonical form", out)
                self.assertTrue(out.rstrip().endswith("[I11]"), out)
                self.assertEqual(run_cli(str(path))[0], 0, "the same bytes are valid without --canonical")
        path = self.write("lf.json", text)
        self.assertEqual(run_cli(str(path), "--canonical")[0], 0)

    def test_a_byte_order_mark_is_unreadable(self):
        path = self.write("bom.json", b"\xef\xbb\xbf" + (EXAMPLES / "pdf-region.json").read_bytes())
        status, out, err = run_cli(str(path), "--canonical")
        self.assertEqual(status, 2)
        self.assertIn("byte-order mark", err)
        self.assertEqual(out, "")

    def test_check_takes_the_text_as_bytes_or_str(self):
        data = (EXAMPLES / "pdf-region.json").read_bytes()
        doc = V.loads(data)
        self.assertTrue(V.check(doc, text=data, canonical=True).ok)
        self.assertTrue(V.check(doc, text=data.decode("utf-8"), canonical=True).ok)
        self.assertEqual(codes(doc, text=data.replace(b"\n", b"\r\n"), canonical=True), ["I11"])
        self.assertEqual(codes(doc, text=data.decode("utf-8").replace("\n", "\r\n"), canonical=True), ["I11"])

    def test_every_valid_example_is_its_own_canonical_form(self):
        for name in VALID:
            with self.subTest(example=name):
                data = (EXAMPLES / name).read_bytes()
                self.assertEqual(V.canonical_dumps(V.canonicalize(V.loads(data))).encode("utf-8"), data)

    def test_the_canonical_writer_refuses_what_loads_would_not_return(self):
        """canonical_dumps and canonicalize are public: a value outside I-JSON gets a TypeError or
        ValueError naming it, never an OverflowError, an AttributeError or a TypeError from inside a sort."""
        with self.assertRaisesRegex(ValueError, "too large for a double"):
            V.canonical_dumps({"a": 10 ** 400})
        with self.assertRaisesRegex(TypeError, "an object key must be a string, not int: 1"):
            V.canonical_dumps({1: 2})
        with self.assertRaisesRegex(TypeError, "object is not JSON"):
            V.canonical_dumps({"a": object()})
        with self.assertRaisesRegex(ValueError, "NaN and Infinity are not JSON"):
            V.canonical_dumps([float("nan")])
        # beyond 2^53 an integer is written as the double it becomes, with the shortest digits that
        # round-trip (JSON.stringify(2 ** 60) gives the same text); 9.1 keeps such integers out of a document
        self.assertEqual(V.canonical_dumps({"a": 2 ** 60}), '{\n  "a": 1152921504606847000\n}\n')
        doc = load("minimal.json")
        doc["items"][0]["legacy_ids"] = [{"a": 1}, "x", "x"]            # not a set of strings: left for the schema
        self.assertEqual(V.canonicalize(doc)["items"][0]["legacy_ids"], [{"a": 1}, "x", "x"])
        self.assertTrue(lines(doc) and all(line.endswith("[SCHEMA]") for line in lines(doc)), lines(doc))
        doc = load("mixed.json")
        doc["companion"]["packages"] = [{"name": 5}, {"name": "a"}, {"name": None}, {}]
        self.assertEqual([p.get("name") for p in V.canonicalize(doc)["companion"]["packages"]], ["a", 5, None, None])
        doc = load("site-pages.json")
        site = next(s for s in doc["sources"] if s.get("scope") == "site")
        site["page_hashes"] = [{"path": 1, "sha256": "0" * 64}, {"path": "a", "sha256": "0" * 64}]
        V.canonical_dumps(V.canonicalize(doc))
        # single-value mutations of the valid examples: the writer either writes or refuses, never crashes
        rng = random.Random(1)
        values = [10 ** 400, {1: 2}, [{"a": 1}], [[1], [1]], object(), float("nan"), 1e400, "", None, True,
                  {"id": 3}, [None, "a"], {"name": []}]

        def paths(x, p=()):
            yield p
            if isinstance(x, dict):
                for k, v in x.items():
                    yield from paths(v, p + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from paths(v, p + (i,))
        for _ in range(300):
            doc = load(rng.choice(VALID))
            where = rng.choice(list(paths(doc))[1:])
            parent = doc
            for key in where[:-1]:
                parent = parent[key]
            parent[where[-1]] = rng.choice(values)
            with self.subTest(path=where):
                try:
                    V.canonical_dumps(V.canonicalize(doc))
                except (TypeError, ValueError):
                    pass


# ---------------------------------------------------------------------------
# 2. one regex dialect: the schema's patterns and the checker's own grammars
# ---------------------------------------------------------------------------

def schema_patterns() -> list[tuple[str, str]]:
    """Every ``pattern`` and ``patternProperties`` key in the schema, with where it sits."""
    found = []

    def walk(node, where):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "pattern" and isinstance(value, str):
                    found.append((f"{where}/pattern", value))
                elif key == "patternProperties":
                    for pat, sub in value.items():
                        found.append((f"{where}/patternProperties", pat))
                        walk(sub, f"{where}/patternProperties/{pat}")
                else:
                    walk(value, f"{where}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{where}/{i}")
    walk(json.loads(SCHEMA.read_text(encoding="utf-8")), "#")
    return found


class TestRegexHygiene(unittest.TestCase):

    FORBIDDEN = re.compile(r"\\[dDwWsSbBAZpP]|\(\?P<|\(\?<[A-Za-z]|\(\?[a-zA-Z]+[:)]|\(\?#")

    def test_every_schema_pattern_is_dialect_neutral(self):
        patterns = schema_patterns()
        self.assertGreater(len(patterns), 20)
        for where, pattern in patterns:
            with self.subTest(where=where, pattern=pattern):
                self.assertIsNone(self.FORBIDDEN.search(pattern), "a construct the two dialects read differently")
                self.assertTrue(pattern.isascii(), "escapes, so no editor can change a character unseen")
                # an unescaped '.' outside a class skips different line terminators in each dialect
                outside = re.sub(r"\[(?:\\.|[^\]\\])*\]", "", pattern)
                self.assertNotRegex(outside, r"(?<!\\)\.", "'.' outside a class")
                S._translate(pattern, where)                              # what schemacheck enforces
                re.compile(pattern)

    def test_no_whitespace_is_the_one_explicit_class(self):
        """Where 1.0.0 wrote ``\\S``, the schema now writes schemacheck's class, and only that one."""
        by_where = dict(schema_patterns())
        for where in ("#/$defs/id/pattern", "#/$defs/ref/pattern", "#/$defs/http_url/pattern",
                      "#/$defs/repo_path/pattern", "#/$defs/repo_ref/pattern",
                      "#/$defs/FragmentSelector/properties/conformsTo/pattern"):
            with self.subTest(where=where):
                self.assertIn(S._NO_WHITESPACE, by_where[where])
        for where in ("#/$defs/site_path/pattern", "#/$defs/declaration/properties/module/pattern",
                      "#/$defs/destination/properties/fragment/pattern"):
            with self.subTest(where=where):
                self.assertIn("[^" + S._WHITESPACE, by_where[where])
        self.assertTrue(S._WHITESPACE.isascii())
        # the class is the ECMA-262 WhiteSpace and LineTerminator sets, plus every control character
        compiled = re.compile("[" + S._WHITESPACE + "]")
        for cp in (0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, 0x2000, 0x200A, 0x2028, 0x2029, 0x202F,
                   0x205F, 0x3000, 0xFEFF, 0x00, 0x1C, 0x1F, 0x7F, 0x85):
            self.assertTrue(compiled.fullmatch(chr(cp)), hex(cp))
        for cp in (0x21, 0x41, 0x200B, 0x2060, 0x3001, 0x1F600):
            self.assertFalse(compiled.fullmatch(chr(cp)), hex(cp))

    def test_schemacheck_refuses_the_dialect_dependent_constructs(self):
        for pattern in (r"^\d+$", r"^\S+$", r"^\s*x", r"^\w+$", r"a\b", r"^x\Z", r"\Ax", r"(?P<n>a)", r"(?<n>a)",
                        r"(?i)abc", r"(?i:abc)", r"(?#c)a", r"^a.b$", r"[]", r"[^]", r"\p{L}", r"\u12", r"\xZ"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(S.SchemaError):
                    S.Validator({"type": "string", "pattern": pattern})
                with self.assertRaises(S.SchemaError):
                    S.Validator({"type": "object", "patternProperties": {pattern: {}}})
        for pattern in (r"^[0-9]+$", r"^(?!x)(?:a|b)(?=c)[^" + S._WHITESPACE + r"]+$", r"\.lean$",
                        r"^[a-z][a-z0-9_]*$", r"^a\.b$", r"^[.]$", r"(?<!x)y", r"^\u0041$", r"^\x41$"):
            with self.subTest(pattern=pattern):
                S.Validator({"type": "string", "pattern": pattern})

    def test_a_dollar_is_the_end_of_the_string_not_before_a_final_newline(self):
        checker = S.Validator({"type": "string", "pattern": "^[a-z]+$"})
        self.assertTrue(checker.is_valid("abc"))
        self.assertFalse(checker.is_valid("abc\n"), "Python's $ would accept this; ECMA-262's does not")
        self.assertTrue(re.search("^[a-z]+$", "abc\n"), "the trap this guards against")
        checker = S.Validator({"type": "string", "pattern": "^(a|$)(/|$)"})       # a $ inside a group too
        self.assertTrue(checker.is_valid("a/"))
        self.assertFalse(checker.is_valid("\n"))
        checker = S.Validator({"type": "string", "pattern": r"^\$$"})            # an escaped $ is literal
        self.assertTrue(checker.is_valid("$"))
        self.assertFalse(checker.is_valid("$\n"))
        checker = S.Validator({"type": "string", "pattern": "^[$]$"})            # a $ in a class is literal
        self.assertTrue(checker.is_valid("$"))

    def test_the_trap_inputs_are_refused(self):
        """A trailing newline, U+FEFF and U+001C in ids and other no-whitespace fields, a non-ASCII digit."""
        doc = load("pdf-region.json")
        doc["companion"]["commit"] += "\n"
        self.assertEqual(lines(doc), ['$.companion.commit: "ed00b5dc6b11040ed2f9baf475edc9b48e1c7f4a\\n" does not '
                                      'match ^([0-9a-f]{40}|[0-9a-f]{64})$ [SCHEMA]'])
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.0\n"
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = load("pdf-region.json")
        doc["companion"]["x_note\n"] = 1
        found = lines(doc)
        self.assertEqual(len(found), 1, found)
        self.assertIn("is not an allowed key here [SCHEMA]", found[0])
        for bad in ("foo\n", "foo" + BOM, "foo" + FILE_SEPARATOR, BOM + "foo", "foo" + NBSP + "bar", "foo bar",
                    "foo\tbar", "foo" + chr(0x2028), "foo" + chr(0x85), "foo" + chr(0x3000)):
            doc = load("pdf-region.json")
            decl = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
            for link in doc["links"]:
                if link["declaration"] == decl["id"]:
                    link["declaration"] = bad
            decl["id"] = decl["name"] = bad
            doc = resort(doc)
            with self.subTest(id=ascii(bad)):
                found = V.check(doc).problems
                self.assertTrue(found)
                self.assertTrue(all(p.code == "SCHEMA" for p in found), found)
                self.assertTrue(any(p.path.endswith(".id") for p in found), found)
        for good in ("foo" + chr(0x200B), "Foo.bar" + chr(0x1F600), "x" + chr(0x2060)):   # not whitespace
            doc = load("pdf-region.json")
            decl = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
            for link in doc["links"]:
                if link["declaration"] == decl["id"]:
                    link["declaration"] = good
            decl["id"] = decl["name"] = good
            with self.subTest(id=ascii(good)):
                self.assertEqual(codes(resort(doc)), [])
        doc = load("pdf-region.json")
        loc = by_id(doc["locations"], "passage-p6-ef94b64f@p010")
        loc["target"]["selector"][0]["value"] = "page=1" + ARABIC_INDIC_ZERO
        found = lines(doc)
        self.assertTrue(any("is not a positive integer (ASCII digits, at most 9) [I7]" in p for p in found), found)
        loc["target"]["selector"][0]["value"] = "page=10\n"
        self.assertTrue(any("is not a positive integer" in p for p in lines(doc)))
        loc["target"]["selector"][0]["value"] = "page=" + chr(0xFF11) + chr(0xFF10)     # fullwidth 10
        self.assertTrue(any("is not a positive integer" in p for p in lines(doc)))

    def test_the_checkers_own_grammars_use_fullmatch_and_ascii_digits(self):
        self.assertIsNone(V._RFC5147.fullmatch("line=41,47\n"))
        self.assertIsNone(V._RFC5147.fullmatch("line=" + ARABIC_INDIC_ZERO + ",47"))
        self.assertIsNotNone(V._RFC5147.fullmatch("line=41,47;md5=0123456789ABCDEF0123456789abcdef"))
        self.assertIsNone(V._XYWH.fullmatch("1,2,3,4\n"))
        self.assertIsNone(V._XYWH.fullmatch("percent:" + ARABIC_INDIC_ZERO + ",10,80,60"))
        self.assertIsNone(V._MEDIA_T.fullmatch("10,20\n"))
        self.assertIsNone(V._MEDIA_T.fullmatch(ARABIC_INDIC_ZERO + ",20"))
        self.assertIsNone(V._PAGE.fullmatch("1" + ARABIC_INDIC_ZERO))
        self.assertIsNone(V._NAMED_ID.fullmatch("Foo.bar\n"))
        self.assertIsNone(V._NAMED_ID.fullmatch("Foo" + FILE_SEPARATOR))
        self.assertIsNone(V._NAMED_ID.fullmatch("Foo" + BOM))
        self.assertIsNotNone(V._NAMED_ID.fullmatch("Foo.bar'"))
        self.assertIsNone(V._VERSION.fullmatch("1.0\n"))
        self.assertIsNone(V._DATE.fullmatch("2026-09-05\n"))
        self.assertIsNone(V._DATE.fullmatch("2026-09-05T12:00:00Z\n"))
        self.assertIsNone(V._DATE.fullmatch("2026-09-05T12:00:00." + ARABIC_INDIC_ZERO + "Z"))
        self.assertIsNone(V._RESERVED_PASSAGE.fullmatch("passage-0123abcd\n"))
        code = (PACKAGE / "validate.py").read_text(encoding="utf-8")
        self.assertNotIn("\\d", code)
        self.assertNotIn("\\s", code)
        self.assertNotIn("\\S", code)
        self.assertNotIn("\\w", code)
        self.assertNotIn("re.match(", code)
        self.assertNotIn(".match(", code.replace("fullmatch(", ""))
        self.assertIn("re.split(", code)

    def test_a_python_only_dollar_in_the_checker_would_have_passed(self):
        """The defect: a hash id with a trailing newline matched ``^...$``; the compiled
        grammar (``\\A...\\Z``, used with ``fullmatch``) does not."""
        self.assertTrue(re.match("^(?:" + vocab.HASH_ID_PATTERN + ")$", PDF_EXAMPLE + "\n"), "the trap")
        self.assertFalse(ids.HASH_ID.match(PDF_EXAMPLE + "\n"))
        self.assertFalse(ids.HASH_ID.fullmatch(PDF_EXAMPLE + "\n"))
        self.assertTrue(ids.HASH_ID.fullmatch(PDF_EXAMPLE))
        doc = load("pdf-region.json")
        decl = by_id(doc["declarations"], PDF_EXAMPLE)
        decl["id"] += "\n"
        for link in doc["links"]:
            if link["declaration"] == PDF_EXAMPLE:
                link["declaration"] = decl["id"]
        self.assertTrue(all(code == "SCHEMA" for code in codes(resort(doc))))
        self.assertTrue(codes(resort(doc)))

    def test_jsonschema_disagrees_only_on_pythons_dollar(self):
        """Python's ``jsonschema`` evaluates patterns with ``re.search``, where ``$`` matches before a
        final newline; ajv (ECMA-262) and this package do not.  The one known divergence, pinned."""
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        real = jsonschema.Draft202012Validator(schema)
        doc = load("pdf-region.json")
        doc["companion"]["commit"] += "\n"
        self.assertTrue(real.is_valid(doc))
        self.assertEqual(codes(doc), ["SCHEMA"])


# ---------------------------------------------------------------------------
# 3. I-JSON: the loader and the pre-pass; nothing crashes
# ---------------------------------------------------------------------------

class TestIJsonLoader(unittest.TestCase):

    def test_loads_takes_str_or_bytes_and_refuses_the_rest(self):
        self.assertEqual(V.loads('{"a": [1, 2.5, "x", null, true]}'), {"a": [1, 2.5, "x", None, True]})
        self.assertEqual(V.loads(b'{"a": 1}'), {"a": 1})
        self.assertEqual(V.loads(bytearray(b'[1]')), [1])
        with self.assertRaises(TypeError):
            V.loads(3)                                                  # type: ignore[arg-type]
        with self.assertRaisesRegex(V.LoadError, "not UTF-8"):
            V.loads(b'{"a": "\xff"}')
        with self.assertRaisesRegex(V.LoadError, "not UTF-8"):
            V.loads('{"a": 1}'.encode("utf-16"))
        with self.assertRaisesRegex(V.LoadError, "not JSON"):
            V.loads("{")
        self.assertTrue(issubclass(V.LoadError, ValueError))

    def test_a_byte_order_mark_duplicate_keys_and_the_constants_are_refused(self):
        with self.assertRaisesRegex(V.LoadError, "byte-order mark"):
            V.loads(b"\xef\xbb\xbf{}")
        with self.assertRaisesRegex(V.LoadError, "byte-order mark"):
            V.loads(BOM + "{}")
        with self.assertRaisesRegex(V.LoadError, "duplicate key 'a'"):
            V.loads('{"a": 1, "a": 2}')
        with self.assertRaisesRegex(V.LoadError, "duplicate key 'b'"):
            V.loads('{"a": {"b": 1, "b": 1}}')
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal), self.assertRaisesRegex(V.LoadError, "is not JSON"):
                V.loads('{"a": ' + literal + "}")

    def test_numbers_are_finite_in_range_and_short(self):
        with self.assertRaisesRegex(V.LoadError, "1e400 is not a finite number"):
            V.loads('{"x_a": 1e400}')                                   # a number past the double range
        with self.assertRaisesRegex(V.LoadError, "not a finite number"):
            V.loads("-1e999")
        with self.assertRaisesRegex(V.LoadError, r"outside \+-\(2\^53 - 1\)"):
            V.loads("9007199254740992")
        with self.assertRaisesRegex(V.LoadError, r"outside \+-\(2\^53 - 1\)"):
            V.loads("-9007199254740992")
        with self.assertRaisesRegex(V.LoadError, r"outside \+-\(2\^53 - 1\)"):
            V.loads("1e300")
        self.assertEqual(V.loads("9007199254740991"), 2 ** 53 - 1)
        self.assertEqual(V.loads("-9007199254740991"), -(2 ** 53 - 1))
        with self.assertRaisesRegex(V.LoadError, "401 characters is longer than 400"):
            V.loads("1" * 401)
        with self.assertRaisesRegex(V.LoadError, "5000 characters is longer than 400"):
            V.loads("[" + "9" * 5000 + "]")                               # not int()'s 4300-digit ValueError
        with self.assertRaisesRegex(V.LoadError, "longer than 400"):
            V.loads("0." + "0" * 398 + "1")
        with self.assertRaisesRegex(V.LoadError, "longer than 400"):
            V.loads("1" + "0" * 396 + "e-400")                        # 402 characters, though only 1e-4
        self.assertEqual(V.loads("1" + "0" * 390 + "e-400"), 1e-10)   # 395 characters: read
        with self.assertRaisesRegex(V.LoadError, "outside"):
            V.loads("1" * 400)
        self.assertEqual(V.loads("0." + "0" * 300 + "1"), 1e-301)

    def test_integer_valued_numbers_come_back_as_int(self):
        parsed = V.loads("[6.0, 1e3, 1E3, -0.0, 0.5, 2.50, 1.0e2, 12345678901234.0]")
        self.assertEqual(parsed, [6, 1000, 1000, 0, 0.5, 2.5, 100, 12345678901234])
        self.assertEqual([type(v).__name__ for v in parsed], ["int"] * 4 + ["float", "float", "int", "int"])
        self.assertIs(type(V.loads("-0")), int)

    def test_lone_surrogates_in_strings_and_keys_are_refused(self):
        with self.assertRaisesRegex(V.LoadError, r"\$\.a: contains a lone surrogate"):
            V.loads('{"a": "' + JSON_LONE_SURROGATE + '"}')
        with self.assertRaisesRegex(V.LoadError, r"\$: key .* contains a lone surrogate"):
            V.loads('{"' + JSON_LONE_SURROGATE + '": 1}')
        with self.assertRaisesRegex(V.LoadError, r"\$\.a\[1\]\.b: contains a lone surrogate"):
            V.loads('{"a": [0, {"b": "x' + JSON_LONE_SURROGATE + 'y"}]}')
        with self.assertRaisesRegex(V.LoadError, "lone surrogate"):
            V.loads('{"a": "' + LONE_SURROGATE + '"}')
        self.assertEqual(V.loads('{"a": "\\ud83d\\ude00"}'), {"a": chr(0x1F600)})     # a pair is fine

    def test_nesting_deeper_than_64_is_refused(self):
        self.assertEqual(V.loads("[" * 64 + "]" * 64), json.loads("[" * 64 + "]" * 64))
        with self.assertRaisesRegex(V.LoadError, "nested deeper than 64 levels"):
            V.loads("[" * 65 + "]" * 65)
        with self.assertRaisesRegex(V.LoadError, "nested deeper than 64 levels"):
            V.loads("[" * 100000 + "]" * 100000)                       # json.loads alone raises RecursionError
        # 500: past the limit, and shallow enough for every supported json.loads (3.11 charges the C
        # decoder against the default recursion limit, so 1000 is a RecursionError there: no path)
        with self.assertRaisesRegex(V.LoadError, r"\$\.x_a(\[0\]){63}: nested deeper than 64"):
            V.loads('{"x_a": ' + "[" * 500 + "]" * 500 + "}")
        with self.assertRaisesRegex(V.LoadError, "nested deeper than 64"):
            V.loads('{"a": ' + '{"a": ' * 64 + "1" + "}" * 65)


class TestIJsonPrePass(unittest.TestCase):
    """``check()`` on an in-memory object reports the loader's limits with code IJSON, and stops there."""

    def test_the_limits_are_problems_with_code_ijson(self):
        doc = load("pdf-region.json")
        loc = by_id(doc["locations"], "definition-1.1@p007")
        loc["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = float("inf")           # 1e400 in memory
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].refinedBy.rect.x1: inf is not a finite "
                                      "number [IJSON]"])
        loc["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = float("nan")
        self.assertEqual(codes(doc), ["IJSON"])
        loc["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = 10 ** 400              # OverflowError in 1.0.0
        found = lines(doc)
        self.assertEqual(len(found), 1)
        self.assertIn("an integer of about 401 digits is outside +-(2^53 - 1), the I-JSON integer range [IJSON]",
                      found[0])
        loc["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = 2 ** 53
        self.assertIn("9007199254740992 is outside", lines(doc)[0])
        doc = load("pdf-region.json")
        doc["sources"][0]["physical_page_count"] = 10 ** 5000
        self.assertEqual(codes(doc), ["IJSON"])
        doc = load("pdf-region.json")
        doc["x_meta"] = {"a": (1, 2), "b": {1, 2}, "c": b"x", "d": 1j}
        found = lines(doc)
        self.assertEqual(found, ["$.x_meta.a: a tuple is not a JSON value [IJSON]",
                                 "$.x_meta.b: a set is not a JSON value [IJSON]",
                                 "$.x_meta.c: a bytes is not a JSON value [IJSON]",
                                 "$.x_meta.d: a complex is not a JSON value [IJSON]"])
        doc = load("pdf-region.json")
        doc["x_meta"] = {1: 2}
        self.assertEqual(lines(doc), ["$.x_meta: key 1 is not a string [IJSON]"])

    def test_lone_surrogates_anywhere_are_problems_not_crashes(self):
        cases = {
            "message": lambda d: d["provenance"][1].__setitem__("note", "x" + LONE_SURROGATE),
            "signature": lambda d: by_id(d["declarations"], "Notes.Box.volume_nonneg").__setitem__(
                "signature", "theorem " + LONE_SURROGATE),
            "quote": lambda d: by_id(d["locations"], "definition-1.1@p007")["target"]["selector"][2]["refinedBy"]
            .__setitem__("exact", LONE_SURROGATE),
            "id": lambda d: d["items"][0].__setitem__("id", "definition-" + LONE_SURROGATE),
            "key": lambda d: d.__setitem__("x_" + LONE_SURROGATE, 1),
            "title": lambda d: by_id(d["items"], "passage-p6-ef94b64f").__setitem__("title", LONE_SURROGATE),
        }
        for label, mutate in cases.items():
            doc = load("pdf-region.json")
            mutate(doc)
            with self.subTest(case=label):
                found = V.check(doc).problems
                self.assertEqual([p.code for p in found], ["IJSON"], found)
                self.assertIn("lone surrogate", found[0].message)
                self.assertTrue(found[0].message.isascii() and found[0].path.isascii(), "the message is printable")
        doc = load("site-pages.json")
        site = next(s for s in doc["sources"] if "page_hashes" in s)
        site["page_hashes"].append({"path": "q" + LONE_SURROGATE + ".html", "sha256": "0" * 64})
        self.assertEqual(codes(doc), ["IJSON"])

    def test_deep_nesting_in_memory_is_a_problem(self):
        doc = load("pdf-region.json")
        deep: list = []
        for _ in range(999):
            deep = [deep]
        doc["x_meta"] = deep
        found = V.check(doc).problems
        self.assertEqual([p.code for p in found], ["IJSON"])
        self.assertIn("nested deeper than 64 levels", found[0].message)
        doc = load("pdf-region.json")
        chain: dict = {"type": "TextQuoteSelector", "exact": "q"}
        for _ in range(200):
            chain = {"type": "TextQuoteSelector", "exact": "q", "refinedBy": chain}
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"] = [chain]
        self.assertEqual(codes(doc), ["IJSON"])

    def test_a_refinement_chain_within_the_limit_is_checked_not_crashed(self):
        doc = load("pdf-region.json")
        chain: dict = {"type": "TextQuoteSelector", "exact": "q"}
        for _ in range(40):
            chain = {"type": "TextQuoteSelector", "exact": "q", "refinedBy": chain}
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"] = [chain]
        report = V.check(doc)                                          # deep, but I-JSON: no exception
        self.assertNotIn("IJSON", [p.code for p in report.problems])

    def test_integer_valued_floats_are_read_as_integers(self):
        """``6.0`` in memory is the integer 6, as the loader would have read it."""
        doc = load("pdf-region.json")
        by_id(doc["items"], "passage-p6-ef94b64f")["pages"]["first"] = 6.0        # a ValueError in 1.0.0
        self.assertEqual(codes(doc), [])
        doc["sources"][0]["printed_page_offset"] = 4.0
        by_id(doc["items"], "passage-p6-ef94b64f")["pages"] = {"basis": "physical", "first": 10.0}
        self.assertEqual(codes(doc), [])
        doc["sources"][0]["physical_page_count"] = 40.0
        self.assertEqual(codes(doc), [])
        doc["sources"][0]["physical_page_count"] = 40.5
        self.assertEqual(codes(doc), ["SCHEMA"])
        self.assertEqual(by_id(doc["items"], "passage-p6-ef94b64f")["pages"]["first"], 10.0,
                         "the caller's object is not changed")

    def test_the_pre_pass_stops_everything_else(self):
        doc = load("pdf-region.json")
        doc["x_meta"] = float("inf")
        del doc["sources"]                                             # would be a SCHEMA problem
        self.assertEqual(codes(doc), ["IJSON"])
        self.assertEqual(codes(doc, lints=("external-urls",)), ["IJSON"])
        self.assertEqual(codes(doc, text="{}", canonical=True), ["IJSON"])


# ---------------------------------------------------------------------------
# 5, 6, 11, 12, 15 and rules that had no test before
# ---------------------------------------------------------------------------

class TestRules(unittest.TestCase):

    def assertProblem(self, doc: dict, fragment: str, code: str) -> None:
        found = V.check(doc).problems
        hits = [p for p in found if fragment in str(p)]
        self.assertTrue(hits, f"{fragment!r} not in {[str(p) for p in found]}")
        self.assertEqual({p.code for p in hits}, {code}, hits)

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def fragment(self, value: str, refined=None) -> dict:
        sel = {"type": "FragmentSelector", "conformsTo": vocab.CONFORMS_TO_PDF, "value": value}
        if refined is not None:
            sel["refinedBy"] = refined
        return sel

    def with_selector(self, sel: dict, loc: str = "definition-1.1@p007") -> dict:
        doc = load("pdf-region.json")
        by_id(doc["locations"], loc)["target"]["selector"] = [sel]
        return doc

    # 5. a repeated PDF parameter
    def test_a_pdf_fragment_names_each_parameter_once(self):
        for value in ("page=999&page=7", "page=7&page=999", "page=7#page=9", "page=7&zoom=100&zoom=50"):
            with self.subTest(value=value):
                doc = self.with_selector(self.fragment(value))
                found = lines(doc)
                self.assertEqual(len(found), 1, found)
                self.assertIn("= is given twice; a PDF fragment names each parameter once [I7]", found[0])
        self.assertValid(self.with_selector(self.fragment("page=7&zoom=100&view=FitH")))

    # 6. physical pages start at 1
    def test_every_physical_page_is_at_least_1(self):
        doc = load("pdf-region.json")
        doc["sources"][0]["printed_page_offset"] = -3
        for rec in doc["items"] + doc["links"] + doc["locations"]:
            if rec.get("pages", {}).get("basis") == "printed":
                rec["pages"]["basis"] = "physical"
                rec["pages"]["first"] += 4
                if "last" in rec["pages"]:
                    rec["pages"]["last"] += 4
        passage = by_id(doc["items"], "passage-p6-ef94b64f")
        old, passage["id"] = passage["id"], ids.passage_page_id(13, passage["title"])
        for loc in doc["locations"]:
            loc["items"] = [passage["id"] if i == old else i for i in loc["items"]]
        doc = resort(doc)
        self.assertValid(doc)
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 1}
        self.assertProblem(doc, "page 1 (printed) is physical page -2; with the source's printed_page_offset "
                                "every physical page is at least 1", "I6")
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 3}
        self.assertProblem(doc, "is physical page 0", "I6")
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 4}
        self.assertValid(doc)
        link = next(l for l in doc["links"] if "pages" in l)
        link["pages"] = {"basis": "printed", "first": 2}
        self.assertProblem(doc, "$.links[2].pages: page 2 (printed) is physical page -1", "I6")
        del link["pages"]
        loc = by_id(doc["locations"], "definition-1.1@p007")
        loc["pages"] = {"basis": "printed", "first": 2, "last": 10}
        found = lines(doc)
        self.assertTrue(any("$.locations[0].pages: page 2 (printed) is physical page -1" in p for p in found), found)
        self.assertFalse(any("outside" in p for p in found), "no second report against a range below 1")
        doc = load("pdf-region.json")
        doc["sources"][0]["printed_page_offset"] = 12
        by_id(doc["items"], "passage-p6-ef94b64f")["pages"] = {"basis": "physical", "first": 10}
        self.assertProblem(doc, "page_title_hash needs a printed page of at least 1; physical page 10 less the "
                                "source's printed_page_offset is -2", "I12")

    # 11. small false positives
    def test_an_rfc5147_md5_may_use_upper_case_hex(self):
        doc = load("tex-lines.json")
        sel = by_id(doc["locations"], "theorem-1.3@tex")["target"]["selector"][0]
        for suffix in (";md5=0123456789ABCDEF0123456789ABCDEF", ";md5=0123456789abcdef0123456789abcdef",
                       ";length=10", ";length=10,UTF-8", ";length=10;md5=0123456789abcdef0123456789ABCDEF"):
            sel["value"] = "line=41,47" + suffix
            with self.subTest(value=sel["value"]):
                self.assertValid(doc)
        for suffix in (";md5=0123456789abcdef0123456789abcde", ";md5=0123456789abcdef0123456789abcdeg", ";length=x"):
            sel["value"] = "line=41,47" + suffix
            with self.subTest(value=sel["value"]):
                self.assertProblem(doc, "is not an RFC 5147 fragment", "I7")

    def quad(self, *points) -> dict:
        quad = {}
        for i, (x, y) in enumerate(points):
            quad[f"x{i}"], quad[f"y{i}"] = x, y
        return {"type": "PdfRegionSelector", "page": 7, "coordinate_space": dict(CS), "quads": [quad]}

    def test_a_quad_needs_three_distinct_corners_that_are_not_collinear(self):
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)))
        self.assertValid(doc)
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.1)))   # a triangle
        self.assertValid(doc)
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.1), (0.1, 0.1)))
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].quads[0]: a quad needs at least three "
                                      "distinct corners [I7]"])
        doc = self.with_selector(self.quad((0.1, 0.1), (0.1, 0.1), (0.1, 0.1), (0.1, 0.1)))
        self.assertEqual(codes(doc), ["I7"])
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.1), (0.3, 0.1), (0.1, 0.1)))   # collinear
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].quads[0]: a quad's corners must not all "
                                      "lie on one line (it would enclose no area) [I7]"])
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.4)))   # a diagonal
        self.assertIn("lie on one line", lines(doc)[0])
        self.assertNotIn("a rect needs", " ".join(lines(doc)), "the rect rule is not the quad's message")
        doc = self.with_selector(self.quad((0.1, 0.1), (0.2, 0.1), (0.3, 1.5), (0.1, 0.1)))
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].quads[0]: coordinates must lie in "
                                      "[0, 1] for units normalized [I7]"])
        sel = self.quad((10, 10), (600, 10), (600, 700), (10, 700))
        sel["coordinate_space"]["units"] = "pt"
        self.assertValid(self.with_selector(sel))
        sel = self.quad((10, 10), (700, 10), (700, 700), (10, 700))
        sel["coordinate_space"]["units"] = "pt"
        self.assertEqual(lines(self.with_selector(sel)), ["$.locations[0].target.selector[0].quads[0]: the quad "
                                                           "leaves the 612 x 792 pt page [I7]"])

    # 12. page_hashes name files by the site_path grammar
    def test_page_hashes_use_the_site_path_grammar_and_name_files(self):
        def with_page(path: str) -> dict:
            doc = load("site-pages.json")
            site = next(s for s in doc["sources"] if "page_hashes" in s)
            site["page_hashes"] = sorted(site["page_hashes"] + [{"path": path, "sha256": "0" * 64}],
                                         key=lambda p: V.order_key(p["path"]))
            site["sha256"] = V.site_sha256(site["page_hashes"])
            return doc
        for path in ("style.css", "a/b.html", "Notes/Section_3/index.html", "x.y.z"):
            with self.subTest(path=path):
                self.assertValid(with_page(path))
        for path in ("/abs.html", "../up.html", "a/../b.html", "a#frag.html", "a:b.html", "a b.html", "x.html\n",
                     "#x", "a/./b.html"[:0] + "a\tb"):
            with self.subTest(path=ascii(path)):
                found = V.check(with_page(path)).problems
                self.assertEqual({p.code for p in found}, {"SCHEMA"}, found)
                self.assertTrue(all(".page_hashes[" in p.path and p.path.endswith(".path") for p in found), found)
        for path in ("Notes/", "a/b/"):
            with self.subTest(path=path):
                found = lines(with_page(path))
                self.assertEqual(len(found), 1, found)
                self.assertRegex(found[0], r"^\$\.sources\[[0-9]+\]\.page_hashes\[[0-9]+\]\.path: '.*' names a "
                                           r"directory; a page_hashes entry names a file \(write its index.html\) "
                                           r"\[I6\]$")
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$defs"]["page_hash"]["properties"]["path"]["$ref"], "#/$defs/site_path")

    # 15. declarations
    def test_an_example_is_always_anonymous(self):
        doc = load("pdf-region.json")
        doc["declarations"].append({"anonymous": False, "file": "Notes/Basic.lean", "id": "Notes.ex1",
                                    "id_source": "name", "kind": "example", "module": "Notes.Basic",
                                    "private": False})
        doc = resort(doc)
        self.assertEqual(lines(doc), ["$.declarations[3].anonymous: an example is always anonymous (a named "
                                      "example is refused) [I8]"])
        doc["declarations"][3]["kind"] = "theorem"
        self.assertValid(doc)

    def test_restated_may_name_a_private_id(self):
        doc = load("mixed.json")
        change = next(c for c in doc["changelog"] if c["event"] == "restated")
        private = next(d for d in doc["declarations"] if d["id_source"] == "private")
        change["subject"] = private["id"]
        change["id"] = "2026-09-25/restated/" + private["id"]
        self.assertValid(resort(doc))
        change["subject"] = PDF_EXAMPLE
        self.assertProblem(resort(doc), "is a statement-hash id", "I9")

    # 9. a field's full name without a name
    def test_a_fields_full_name_is_checked_through_its_id_when_name_is_absent(self):
        doc = load("pdf-region.json")
        field = by_id(doc["declarations"], "Notes.Box.lower")
        del field["name"]
        self.assertValid(doc)
        field["id"] = "Other.lower"
        doc = resort(doc)
        self.assertEqual(lines(doc), ["$.declarations[2].id: a field's full name is its namespace, a dot and its "
                                      "own name [I8]"])
        doc = load("pdf-region.json")
        field = by_id(doc["declarations"], "Notes.Box.lower")
        del field["namespace"]
        field["id"] = field["name"] = "Other.lower"
        doc = resort(doc)
        self.assertEqual(lines(doc), ["$.declarations[2].name: a field's full name is its parent's full name "
                                      "('Notes.Box'), a dot and its own name [I8]"])
        doc = load("pdf-region.json")
        field = by_id(doc["declarations"], "Notes.Box.lower")
        del field["namespace"]
        self.assertValid(doc)

    # rules that had no test before
    def test_link_keys_are_unique(self):
        doc = load("pdf-region.json")
        link = by_id(doc["links"], "definition-1.1/key/Notes.Box")
        doc["links"].append(dict(link, id="zz-again"))
        self.assertEqual(lines(doc), ["$.links[4]: repeats the link at $.links[0] (same item, target, role and "
                                      "sub) [I3]"])
        doc["links"][-1]["sub"] = "ii"
        self.assertValid(doc)
        doc["links"][-1]["role"] = "support"
        del doc["links"][-1]["sub"]
        self.assertValid(doc)

    def test_one_snippet_per_declaration(self):
        doc = load("mixed.json")
        doc["snippets"].append(dict(doc["snippets"][0], id="zz-second"))
        self.assertProblem(doc, "already has a snippet at $.snippets[0]", "I3")

    def test_a_fragment_is_written_without_its_leading_hash(self):
        doc = self.with_selector(self.fragment("#page=7"))
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].value: write the fragment without its "
                                      "leading # [I7]"])

    def test_highlight_is_left_right_top_bottom_in_order(self):
        self.assertValid(self.with_selector(self.fragment("page=7&highlight=90,522,140,260")))
        for value in ("page=7&highlight=522,90,140,260", "page=7&highlight=90,522,260,140"):
            with self.subTest(value=value):
                self.assertProblem(self.with_selector(self.fragment(value)),
                                   "highlight= is left,right,top,bottom with left <= right and top <= bottom", "I7")
        self.assertValid(self.with_selector(self.fragment("page=7&highlight=90,90,140,140")))

    def test_a_declaration_is_not_its_own_parent(self):
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box.lower")["parent"] = "Notes.Box.lower"
        found = lines(doc)
        self.assertIn("$.declarations[1].parent: a declaration is not its own parent [I8]", found)

    def test_id_source_name_flags_and_anonymity(self):
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box")["private"] = True
        self.assertProblem(doc, "a private or anonymous declaration is not identified by name", "I8")
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box")["anonymous"] = True
        self.assertTrue(V.check(doc).problems)                          # the schema and I8 both object
        doc = load("pdf-region.json")
        by_id(doc["declarations"], PDF_EXAMPLE)["name"] = "Notes.ex"
        self.assertProblem(doc, "an anonymous declaration has no name", "I8")
        doc = load("pdf-region.json")
        by_id(doc["declarations"], PDF_EXAMPLE)["anonymous"] = False
        found = lines(doc)
        self.assertIn("$.declarations[3].id_source: id_source statement_hash is for anonymous declarations [I8]",
                      found)
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "private:Notes.Basic:Notes.Box.volume_aux")["private"] = False
        self.assertProblem(doc, "id_source private needs private true and anonymous false", "I8")
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box")["id_source"] = "declared"
        self.assertProblem(doc, "id_source declared is for anonymous declarations", "I8")
        doc = load("pdf-region.json")
        decl = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
        decl["id"] = decl["name"] = "Notes.Box:volume_nonneg"
        for link in doc["links"]:
            if link["declaration"] == "Notes.Box.volume_nonneg":
                link["declaration"] = decl["id"]
        self.assertValid(resort(doc))                                   # a colon inside a name is Lean's business
        decl["id"] = decl["name"] = "private:Notes.Box"
        for link in doc["links"]:
            if link["declaration"] == "Notes.Box:volume_nonneg":
                link["declaration"] = decl["id"]
        self.assertProblem(resort(doc), "is not a fully qualified Lean name", "I8")


# ---------------------------------------------------------------------------
# 8. every date and timestamp (I9)
# ---------------------------------------------------------------------------

class TestDates(unittest.TestCase):

    def test_the_schema_walk_finds_every_date_field(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        chains = set(V._date_chains(schema))
        for chain in (("companion", "generated_at"), ("sources", "*", "retrieved_at"), ("provenance", "*", "at"),
                      ("locations", "*", "signoff", "at"), ("changelog", "*", "at")):
            self.assertIn(chain, chains)
        self.assertTrue(all(chain[-1] in ("at", "generated_at", "retrieved_at") for chain in chains), chains)
        self.assertGreaterEqual(len(chains), 5)

    def test_every_at_is_a_real_date_or_instant(self):
        cases = {
            "$.provenance[0].at": lambda d: d["provenance"][0].__setitem__("at", "2026-02-30"),
            "$.locations[0].signoff.at": lambda d: by_id(d["locations"], "definition-1.1@p007")["signoff"]
            .__setitem__("at", "2026-13-45"),
            "$.companion.generated_at": lambda d: d["companion"].__setitem__("generated_at",
                                                                             "2026-02-30T99:99:99Z"),
            "$.sources[0].retrieved_at": lambda d: d["sources"][0].__setitem__("retrieved_at",
                                                                               "2026-09-31T00:00:00Z"),
        }
        for path, mutate in cases.items():
            doc = load("pdf-region.json")
            mutate(doc)
            with self.subTest(path=path):
                found = lines(doc)
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith(f"{path}: '"), found[0])
                self.assertTrue(found[0].endswith("' is not a calendar date or UTC instant [I9]"), found[0])
        doc = load("graph-profile.json")
        doc["changelog"][3]["at"] = "2026-02-30"
        self.assertEqual(codes(doc), ["I9"])
        doc = load("pdf-region.json")
        doc["sources"][0]["retrieved_at"] = "2026-09-30T00:00:00Z"
        doc["provenance"][0]["at"] = "2024-02-29T23:59:59.5Z"          # a leap day, a fraction
        self.assertEqual(codes(doc), [])

    def test_a_leap_second_is_accepted_and_nothing_else_past_59(self):
        doc = load("graph-profile.json")
        for at, ok in (("2016-12-31T23:59:60Z", True), ("2016-12-31T23:59:60.5Z", True), ("2016-12-31T23:59:59Z", True),
                       ("2016-12-31T23:58:60Z", False), ("2016-12-31T22:59:60Z", False), ("2016-12-31T23:60:00Z", False),
                       ("2016-12-31T24:00:00Z", False), ("2016-12-31T23:59:61Z", False), ("0000-01-01", False),
                       ("2016-12-31T23:59:60", False), ("2016-12-31t23:59:60Z", False)):
            doc["changelog"][3]["at"] = at
            with self.subTest(at=at):
                self.assertEqual(V.check(doc).ok, ok, lines(doc))

    def test_instants_compare_with_their_full_fractional_precision(self):
        def with_records(first_file: str, second_file: str, first_at: str, second_at: str) -> dict:
            doc = load("graph-profile.json")
            record = doc["changelog"][0]
            self.assertEqual(record["event"], "ordinal_assigned")
            record["at"], record["file"] = first_at, first_file
            doc["changelog"].append(dict(record, id="2026-09-05b/ordinal/" + record["subject"], at=second_at,
                                         file=second_file))
            return resort(doc)
        right, wrong = "Notes/Basic.lean", "Notes/Other.lean"
        base = "2026-09-05T00:00:00."
        # the later record (by 800 ns) names the right file: valid
        self.assertEqual(codes(with_records(wrong, right, base + "0000001Z", base + "0000009Z")), [])
        # the later record names the wrong file: the ordinal moved
        found = lines(with_records(right, wrong, base + "0000001Z", base + "0000009Z"))
        self.assertEqual(len(found), 1, found)
        self.assertIn("the latest ordinal_assigned record gives", found[0])
        self.assertNotIn("name different files", found[0], "800 ns apart is not a tie")
        # equal instants spelled differently are a tie
        found = lines(with_records(right, wrong, base + "5Z", base + "50Z"))
        self.assertIn("name different files", found[0])
        found = lines(with_records(right, wrong, "2026-09-05", "2026-09-05T00:00:00Z"))
        self.assertIn("name different files", found[0])
        # more than 6 fractional digits are kept, not truncated
        self.assertEqual(codes(with_records(wrong, right, base + "1234567890123Z", base + "1234567890124Z")), [])
        self.assertLess(V._parse_at(base + "09Z"), V._parse_at(base + "1Z"))
        self.assertEqual(V._parse_at(base + "10Z"), V._parse_at(base + "1Z"))
        self.assertLess(V._parse_at("2016-12-31T23:59:59.999999999Z"), V._parse_at("2016-12-31T23:59:60Z"))
        self.assertLess(V._parse_at("2016-12-31T23:59:60Z"), V._parse_at("2017-01-01T00:00:00Z"))


# ---------------------------------------------------------------------------
# 7, 13 and the CLI contract: every document, exit statuses, no traceback, --format json
# ---------------------------------------------------------------------------

class TestTheCli(Temp):

    def test_every_document_is_checked_and_2_wins_over_1(self):
        good = EXAMPLES / "pdf-region.json"
        bad = EXAMPLES / "invalid-dangling-reference.json"
        unreadable = self.write("unreadable.json", '{"a": 1, "a": 2}')
        missing = self.tmp / "missing.json"
        status, out, err = run_cli(str(unreadable), str(bad), str(missing), str(good))
        self.assertEqual(status, 2)
        self.assertIn(f"{unreadable}: cannot read: duplicate key 'a' in one object", err)
        self.assertIn(f"{missing}: cannot read: ", err)
        self.assertIn(f"{bad}: {json.loads(bad.read_text(encoding='utf-8'))['x_expected_error']}", out)
        self.assertIn(f"{good}: ok (", out)
        self.assertEqual(run_cli(str(bad), str(good))[0], 1)
        self.assertEqual(run_cli(str(good), str(good))[0], 0)
        self.assertNotIn("Traceback", err)

    def test_text_lines_carry_the_code(self):
        bad = EXAMPLES / "invalid-reversed-line-range.json"
        status, out, err = run_cli(str(bad))
        self.assertEqual(status, 1)
        self.assertRegex(out, r"^.*: \$\.locations\[2\]\.target\.selector\[0\]\.value: RFC 5147 range .* \[I7\]\n$")
        status, out, err = run_cli(str(EXAMPLES / "other-media.json"))
        self.assertEqual(status, 0)
        self.assertRegex(out, r"^.*: warning: \$\.locations\[1\]\.target\.selector\[0\]\.conformsTo: .* \[W-CONFORMS\]\n"
                              r".*: ok \(.*\)\n$")
        self.assertEqual(err, "")

    def test_format_json_writes_one_object_per_document(self):
        good, bad = EXAMPLES / "other-media.json", EXAMPLES / "invalid-dangling-reference.json"
        unreadable = self.write("nan.json", '{"x": NaN}')
        status, out, err = run_cli(str(good), str(bad), str(unreadable), "--format", "json")
        self.assertEqual(status, 2)
        records = [json.loads(line) for line in out.splitlines()]
        self.assertEqual([r["file"] for r in records], [str(good), str(bad), str(unreadable)])
        self.assertEqual([r["ok"] for r in records], [True, False, False])
        self.assertEqual(set(records[0]), {"file", "ok", "problems", "warnings"})
        self.assertEqual(records[0]["problems"], [])
        self.assertEqual([w["code"] for w in records[0]["warnings"]], ["W-CONFORMS"])
        self.assertEqual(set(records[0]["warnings"][0]), {"code", "path", "message"})
        self.assertEqual(records[1]["problems"], [{"code": "I3", "path": "$.links[2].declaration",
                                                   "message": "'Notes.Box.volume_pos' is not an id in "
                                                              "declarations[]"}])
        self.assertEqual(records[2]["problems"][0]["code"], "IJSON")
        self.assertIn("NaN is not JSON", records[2]["problems"][0]["message"])
        self.assertEqual(err, "")

    def test_print_canonical_validates_first(self):
        """An invalid document: exit 1, the report on stderr and nothing on stdout (11.6: stdout is the
        canonical bytes and nothing else, so ``--print-canonical > fixed.json`` never writes a report)."""
        doc = load("mixed.json")
        doc["clusters"][0]["items"] = [[1]]                             # an unhashable list element: a TypeError
        path = self.write("bad.json", json.dumps(doc))
        status, out, err = run_cli(str(path), "--print-canonical")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("$.clusters[0].items[0]: must be of type string [SCHEMA]", err)
        doc = load("mixed.json")
        doc["provenance"][0]["inputs"] = [{"path": 1, "sha256": "0" * 64}, {"path": "a", "sha256": "0" * 64}]
        path = self.write("mixed-types.json", json.dumps(doc))
        status, out, err = run_cli(str(path), "--print-canonical")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("[SCHEMA]", err)
        path = self.write("surrogate.json", '{"schema_version": "' + JSON_LONE_SURROGATE + '"}')
        status, out, err = run_cli(str(path), "--print-canonical")
        self.assertEqual((status, out), (2, ""))
        self.assertIn("lone surrogate", err)
        status, out, err = run_cli(str(path), "--print-canonical", "--format", "json")
        self.assertEqual((status, out), (2, ""))
        self.assertEqual(json.loads(err)["problems"][0]["code"], "IJSON")
        path = self.write("dangling.json", load("invalid-dangling-reference.json"))
        status, out, err = run_cli(str(path), "--print-canonical")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("[I3]", err)
        self.assertEqual(err.count("\n"), 1, "the problem line, and nothing else")
        status, out, err = run_cli(str(path), "--print-canonical", "--format", "json")
        self.assertEqual((status, out), (1, ""))
        self.assertEqual(json.loads(err)["problems"][0]["code"], "I3")
        messy = self.write("messy.json", json.dumps(load("other-media.json"), indent=4))
        status, out, err = run_cli(str(messy), "--print-canonical")
        self.assertEqual(status, 0)
        self.assertEqual(out, (EXAMPLES / "other-media.json").read_text(encoding="utf-8"))
        self.assertIn("warning: ", err, "a warning goes to stderr: stdout is the canonical form")
        self.assertIn("[W-CONFORMS]", err)

    def test_print_canonical_sorts_before_it_validates(self):
        """An unsorted but otherwise valid document is repaired, not refused (section 10: a producer
        never has to hand-sort); the plain checker still reports the order (I2)."""
        doc = load("mixed.json")
        doc["declarations"].reverse()
        doc["items"][0]["legacy_ids"] = ["zz", "aa"]
        unsorted = self.write("unsorted.json", json.dumps(doc, indent=1))
        status, out, err = run_cli(str(unsorted))
        self.assertEqual(status, 1)
        self.assertIn("[I2]", out)
        status, out, err = run_cli(str(unsorted), "--print-canonical")
        self.assertEqual((status, err), (0, ""))
        fixed = V.loads(out)
        self.assertEqual([d["id"] for d in fixed["declarations"]], [d["id"] for d in load("mixed.json")["declarations"]])
        self.assertEqual(fixed["items"][0]["legacy_ids"], ["aa", "zz"])
        self.assertEqual(run_cli(str(self.write("fixed.json", out)), "--canonical")[0], 0)

    def test_print_canonical_writes_utf8_bytes_whatever_the_locale(self):
        source = EXAMPLES / "pdf-region.json"
        self.assertNotIn(source.read_text(encoding="utf-8"), [source.read_bytes().decode("latin-1")])
        for encoding in ("latin-1", "ascii", "utf-8"):
            with self.subTest(encoding=encoding):
                child = run_child(str(source), "--print-canonical", PYTHONIOENCODING=encoding, LC_ALL="C")
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertEqual(child.stdout, source.read_bytes())
                self.assertEqual(child.stderr, b"")

    def test_messages_the_locale_cannot_encode_do_not_crash(self):
        doc = load("pdf-region.json")
        item = doc["items"][0]
        doc["items"].insert(1, dict(item))                              # a duplicate id
        for rec in doc["items"][:2]:
            rec["id"] = "d" + chr(0xE9) + "finition-1.1"                  # an accented id in the message
        path = self.write("accent.json", json.dumps(doc, ensure_ascii=False))
        child = run_child(str(path), PYTHONIOENCODING="ascii", LC_ALL="C")
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertIn(b"duplicate id 'd\\xe9finition-1.1'", child.stdout)
        self.assertNotIn(b"Traceback", child.stderr)
        child = run_child(str(path), "--format", "json", PYTHONIOENCODING="ascii", LC_ALL="C")
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertIn("duplicate id", json.loads(child.stdout.decode("ascii"))["problems"][0]["message"])

    def test_an_internal_error_is_reported_never_a_traceback_never_invalid(self):
        good = EXAMPLES / "pdf-region.json"
        with mock.patch.object(V.Checker, "run", side_effect=KeyError("boom")):
            status, out, err = run_cli(str(good), str(good))
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, f"{good}: internal error: KeyError: 'boom'\n" * 2)
        shape = self.write("list.json", "[1]")                        # a SCHEMA problem: Checker never runs
        with mock.patch.object(V.Checker, "run", side_effect=RecursionError("deep")):
            status, out, err = run_cli(str(good), str(shape))
        self.assertEqual(status, 2, "2 wins over the invalid document's 1")
        self.assertIn("[SCHEMA]", out)
        # end to end: a schema the evaluator does not implement makes check() raise
        schema = self.write("odd.schema.json", json.dumps({"type": "object", "format": "email"}))
        child = run_child(str(good), "--schema", str(schema))
        self.assertEqual(child.returncode, 2)
        self.assertEqual(child.stdout, b"")
        self.assertIn(b"internal error: SchemaError: #: keyword 'format' is not implemented", child.stderr)
        self.assertNotIn(b"Traceback", child.stderr)

    def test_unreadable_documents_and_the_1e400_overflow_exit_2_not_1(self):
        for label, body in (("1e400", '{"x_a": 1e400}'), ("deep", "[" * 100000 + "]" * 100000),
                            ("digits", '{"x_a": ' + "1" * 5000 + "}"), ("nan", '{"x_a": NaN}'),
                            ("surrogate", '{"x_a": "' + JSON_LONE_SURROGATE + '"}'),
                            ("bom", b"\xef\xbb\xbf{}"), ("utf-16", '{"a": 1}'.encode("utf-16")),
                            ("not json", "{"), ("big int", '{"x_a": 9007199254740992}')):
            path = self.write(f"{label}.json", body)
            with self.subTest(label=label):
                status, out, err = run_cli(str(path))
                self.assertEqual(status, 2, out + err)
                self.assertEqual(out, "")
                self.assertTrue(err.startswith(f"{path}: cannot read: "), err)
                self.assertEqual(run_cli(str(path), "--canonical")[0], 2)
                self.assertEqual(run_cli(str(path), "--print-canonical")[0], 2)

    def test_a_document_that_is_not_an_object_is_invalid(self):
        path = self.write("list.json", "[1, 2]")
        status, out, err = run_cli(str(path))
        self.assertEqual(status, 1)
        self.assertIn(f"{path}: $: must be of type object [SCHEMA]", out)
        status, out, err = run_cli(str(path), "--print-canonical")
        self.assertEqual((status, out), (1, ""))
        self.assertIn("[SCHEMA]", err)

    def test_a_newer_minor_version_warns_with_a_code(self):
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.9"
        report = V.check(doc)
        self.assertTrue(report.ok)
        self.assertEqual([w.code for w in report.warnings], ["W-NEWER"])
        doc["schema_version"] = "2.0"
        report = V.check(doc)
        self.assertEqual([(p.code, p.path) for p in report.problems], [("SCHEMA", "$.schema_version")])

    def test_validate_returns_strings_and_check_problems(self):
        doc = load("invalid-dangling-reference.json")
        self.assertEqual(V.validate(doc), ["$.links[2].declaration: 'Notes.Box.volume_pos' is not an id in "
                                           "declarations[]"])
        (problem,) = V.check(doc).problems
        self.assertEqual((problem.code, problem.path), ("I3", "$.links[2].declaration"))
        self.assertEqual(str(problem), V.validate(doc)[0])
        self.assertFalse(V.check(doc).ok)
        self.assertTrue(V.check(load("pdf-region.json")).ok)


# ---------------------------------------------------------------------------
# 10. no quadratic passes
# ---------------------------------------------------------------------------

class TestScaling(unittest.TestCase):

    def test_unique_items_is_linear(self):
        schema = {"type": "array", "uniqueItems": True,
                  "items": {"type": "object", "properties": {"id": {"type": "string"}}}}
        checker = S.Validator(schema)
        big = [{"id": f"x{i}", "n": [i, i + 0.5, {"k": True}]} for i in range(20000)]
        start = time.perf_counter()
        self.assertEqual(checker.errors(big), [])
        self.assertLess(time.perf_counter() - start, 5.0, "20000 elements: quadratic would take minutes")
        big.append(dict(big[7]))
        self.assertEqual(checker.errors(big), [("$[20000]", "duplicates an earlier entry")])
        checker = S.Validator({"type": "array", "uniqueItems": True})
        self.assertEqual(checker.errors([1, 1.0]), [("$[1]", "duplicates an earlier entry")])
        self.assertEqual(checker.errors([1, True]), [])
        self.assertEqual(checker.errors([0, False, None, "", []]), [])
        self.assertEqual(checker.errors([{"a": [1, {"b": None}]}, {"a": [1, {"b": None}]}]),
                         [("$[1]", "duplicates an earlier entry")])
        self.assertEqual(checker.errors([{"a": 1, "b": 2}, {"b": 2, "a": 1}]), [("$[1]", "duplicates an earlier entry")])
        self.assertEqual(checker.errors([[1, 2], [2, 1]]), [])

    def test_quote_hash_items_are_checked_in_linear_time(self):
        doc = load("pdf-region.json")
        doc["sources"][0]["physical_page_count"] = 100000
        doc["items"], doc["locations"], doc["links"] = [], [], []
        doc["declarations"] = [d for d in doc["declarations"] if d["id"] == "Notes.Box"]
        for i in range(3000):
            quote = f"quote number {i}"
            rid = ids.passage_quote_id(quote)
            doc["items"].append({"form": "passage", "id": rid, "id_source": "quote_hash", "kind": "passage",
                                 "source": "notes-pdf", "title": f"t{i}", "coverage": "formalized"})
            doc["locations"].append({"id": f"{rid}@loc", "items": [rid], "target": {
                "source": "notes-pdf", "selector": [{"type": "FragmentSelector", "conformsTo": vocab.CONFORMS_TO_PDF,
                                                     "value": f"page={i % 90000 + 1}",
                                                     "refinedBy": {"type": "TextQuoteSelector", "exact": quote}}]}})
            doc["links"].append({"declaration": "Notes.Box", "id": f"{rid}/key/Notes.Box", "item": rid,
                                 "provenance": "prov-docstrings", "role": "key"})
        doc = resort(doc)
        start = time.perf_counter()
        self.assertTrue(V.check(doc).ok)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 4.0, f"3000 quote items took {elapsed:.1f}s: locations are indexed by item once")


if __name__ == "__main__":
    unittest.main()
