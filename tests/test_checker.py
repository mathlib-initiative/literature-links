"""The checker against the specification: schema, invariants, warnings, lint, I-JSON, canonical form, CLI.

The documents are the examples under examples/annotations/ and small documents
built here from minimal.json.  Each test breaks one in one place and checks the
code, path and message it must fail with.  When ``jsonschema`` is importable
the package's own schema evaluator is also checked against it.
"""
from __future__ import annotations

import copy
import hashlib
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

ROOT = Path(__file__).resolve().parent.parent
# The copy under test is the one Python imports: an installed package when there
# is one, else the source tree, so a checkout runs with nothing installed.
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

import formal_companion_annotations                                                 # noqa: E402
from formal_companion_annotations import ids                                        # noqa: E402
from formal_companion_annotations import schemacheck as S                           # noqa: E402
from formal_companion_annotations import validate as V                              # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402

PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
EXAMPLES = ROOT / "examples" / "annotations"
SCHEMA = ROOT / "schema" / "annotations-v1.0.schema.json"
SCHEMA_ID = ("https://raw.githubusercontent.com/mathlib-initiative/formal-companion-annotations/main/schema/"
             "annotations-v1.0.schema.json")
VALID = ("minimal.json", "mixed.json", "pdf-region.json", "site-pages.json")
INVALID = ("invalid-dangling-reference.json",)
ALL_PROFILES = {"audit": "1.0", "graph": "1.0", "history": "1.0", "site": "1.0"}
EPUB_CFI = "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"
PDF_EXAMPLE = "example:a3be9ccfbb38"               # pdf-region.json's anonymous example
ORDINAL = "example:7c01be3bbde5"                   # mixed.json's twice-stated example (and ~2)
CS = {"origin": "top_left", "page_box": "CropBox", "units": "normalized", "x_axis": "right", "y_axis": "down"}
LONE_SURROGATE = chr(0xD800)
JSON_LONE_SURROGATE = "\\u" + "d800"
BOM, NBSP, FILE_SEPARATOR, ARABIC_INDIC_ZERO = chr(0xFEFF), chr(0xA0), chr(0x1C), chr(0x660)


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def by_id(records: list[dict], rid: str) -> dict:
    return next(r for r in records if r["id"] == rid)


def lines(doc, **kwargs) -> list[str]:
    """Each problem as the CLI prints it after the file name: ``<path>: <message> [<code>]``."""
    return [f"{p} [{p.code}]" for p in V.check(doc, **kwargs).problems]


def codes(doc, **kwargs) -> list[str]:
    return [p.code for p in V.check(doc, **kwargs).problems]


def warnings(doc) -> list[tuple[str, str]]:
    return [(w.code, w.path) for w in V.check(doc).warnings]


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            status = V.main(list(argv))
        except SystemExit as exc:
            status = exc.code
    return status, out.getvalue(), err.getvalue()


def run_child(*argv: str, **env: str) -> subprocess.CompletedProcess:
    """``python -m formal_companion_annotations.validate`` in a child that imports the copy under test."""
    path = os.pathsep.join(p for p in (str(PACKAGE.parent), os.environ.get("PYTHONPATH", "")) if p)
    child_env = dict(os.environ, PYTHONPATH=path, PYTHONDONTWRITEBYTECODE="1")
    child_env.pop("PYTHONIOENCODING", None)
    child_env.update(env)
    return subprocess.run([sys.executable, "-m", "formal_companion_annotations.validate", *argv],
                          capture_output=True, env=child_env, cwd=ROOT, check=False)


# --- small documents built from minimal.json

PROV = {"actor": "author", "confirmed_by_human": True, "id": "prov", "method": "blueprint_macro"}
TEXT, HTML_ID, MEDIA = vocab.CONFORMS_TO_TEXT, vocab.CONFORMS_TO_HTML, vocab.CONFORMS_TO_MEDIA


def doc_from(**arrays) -> dict:
    """minimal.json with root keys replaced, in canonical order."""
    doc = load("minimal.json")
    doc.update(copy.deepcopy(arrays))
    return V.canonicalize(doc)


def decl(name: str, kind: str = "theorem", **more) -> dict:
    return {"anonymous": False, "file": "Notes/Basic.lean", "id": name, "id_source": "name", "kind": kind,
            "module": "Notes.Basic", "name": name, "private": False, **more}


def numbered(kind: str, number: str, source: str, **more) -> dict:
    return {"form": "numbered", "id": ids.item_label_id(kind, number), "id_source": "label", "kind": kind,
            "number": number, "source": source, **more}


def link(item: str, target: str, role: str = "key", **more) -> dict:
    return {"declaration": target, "id": f"{item}/{role}/{target}", "item": item, "provenance": "prov",
            "role": role, **more}


def frag(conforms: str | None, value: str, refined: dict | None = None) -> dict:
    sel = {"type": "FragmentSelector", "value": value}
    if conforms is not None:
        sel["conformsTo"] = conforms
    if refined is not None:
        sel["refinedBy"] = refined
    return sel


def malformed_records() -> dict:
    """mixed.json with a record that is not an object and keyed-list entries the sorts cannot key by a string."""
    doc = load("mixed.json")
    doc["companion"]["packages"] = [{"name": 5}, {"name": "a"}, {"name": None}, {}]
    doc["items"].insert(1, 1)
    next(i for i in doc["items"] if "xrefs" in i)["xrefs"] += ["x", {"database": 1, "tag": []}, {"tag": {}}]
    next(p for p in doc["provenance"] if "inputs" in p)["inputs"] += [{"path": {}}, {"path": []}, 3]
    return doc


def quote(exact: str, refined: dict | None = None, **context: str) -> dict:
    sel = {"type": "TextQuoteSelector", "exact": exact, **context}
    if refined is not None:
        sel["refinedBy"] = refined
    return sel


def loc(rid: str, source: str, selectors: list[dict], items: tuple = (), **more) -> dict:
    return {"id": rid, "items": sorted(items), "target": {"selector": selectors, "source": source}, **more}


def tex_doc() -> dict:
    """A LaTeX source and a Lean file: RFC 5147 line ranges, quotes and a declaration's own anchor."""
    return doc_from(
        sources=[{"git_blob": "1" * 40, "id": "blueprint", "kind": "tex", "path": "blueprint/ch1.tex",
                  "revision": "2" * 40, "text_layer": {"case": "sensitive", "unicode": "none", "whitespace": "exact"},
                  "title": "Blueprint, chapter 1 (synthetic)", "url": "https://notes.example.org/ch1.tex"},
                 {"git_blob": "3" * 40, "id": "lean-basic", "kind": "lean", "path": "Notes/Basic.lean",
                  "title": "Notes/Basic.lean"}],
        items=[numbered("Theorem", "1.3", "blueprint")],
        declarations=[decl("Notes.sum_comm", anchors=["lean-basic@sum_comm"], doc_line=110, line=113)],
        locations=[loc("lean-basic@sum_comm", "lean-basic",
                       [frag(TEXT, "line=112,114"), quote("theorem sum_comm", suffix=" (f : Fin m -> Fin n -> Nat) :")]),
                   loc("theorem-1.3@tex", "blueprint",
                       [frag(TEXT, "line=41,47"), quote("\\begin{theorem}\\label{thm:sum-comm}")], ("theorem-1.3",))],
        links=[link("theorem-1.3", "Notes.sum_comm")], provenance=[PROV])


def media_doc() -> dict:
    """Other media: a video by Media Fragments, an e-book by a grammar the checker does not know, Markdown by lines."""
    epub = numbered("Theorem", "3", "notes-epub", coverage="out_of_scope", id="theorem-3-epub", id_source="declared",
                    coverage_note="The e-book edition is not formalised.", relations={"same_as": ["theorem-3"]})
    return doc_from(
        sources=[{"bytes": 1000, "id": "lecture", "kind": "other", "media_type": "video/mp4", "sha256": "4" * 64,
                  "title": "Lecture 3, a recording (synthetic)"},
                 {"id": "notes-epub", "kind": "other", "media_type": "application/epub+zip", "sha256": "5" * 64,
                  "title": "Notes, e-book edition (synthetic)"},
                 {"git_blob": "6" * 40, "id": "notes-md", "kind": "other", "media_type": "text/markdown",
                  "path": "notes/lecture3.md", "revision": "7" * 40, "title": "Lecture 3 notes (synthetic)"}],
        items=[{"coverage": "support_only", "form": "passage", "id": "passage-sketch", "id_source": "declared",
                "kind": "passage", "source": "lecture", "title": "Proof sketch on the board",
                "title_source": "producer"},
               numbered("Theorem", "3", "notes-md"), epub],
        declarations=[decl("Lecture.sum_sq")],
        locations=[loc("passage-sketch@t", "lecture", [frag(MEDIA, "t=1830,1905&xywh=percent:10,10,80,60")],
                       ("passage-sketch",)),
                   loc("theorem-3-epub@cfi", "notes-epub", [frag(EPUB_CFI, "epubcfi(/6/4!/4/2/1:0)"),
                                                            quote("Theorem 3.")], ("theorem-3-epub",)),
                   loc("theorem-3@md", "notes-md", [frag(TEXT, "line=9,12"), quote("**Theorem 3.**")],
                       ("theorem-3",))],
        links=[link("passage-sketch", "Lecture.sum_sq", "support", relation="invocation"),
               link("theorem-3", "Lecture.sum_sq", relation="exact")],
        provenance=[PROV])


WEB_QUOTE = "an ideal whose complement is closed under multiplication"


def web_doc() -> dict:
    """A web page pinned by revision: passages by quote and by CSS, a projection, a doc-gen4 destination."""
    mathlib = {"file": "Mathlib/RingTheory/Ideal/Defs.lean", "module": "Mathlib.RingTheory.Ideal.Defs",
               "package": "mathlib"}
    passage = ids.passage_quote_id(WEB_QUOTE)
    return doc_from(
        profiles={"site": "1.0"},
        sources=[{"alternate_urls": ["https://mirror.example.org/wiki/Prime_ideal"], "id": "wiki", "kind": "web",
                  "retrieved_at": "2026-09-01T08:00:00Z", "revision": "1234567",
                  "text_layer": {"case": "sensitive", "unicode": "nfc", "whitespace": "collapse"},
                  "title": "Prime ideal, an encyclopedia article (synthetic)",
                  "url": "https://wiki.example.org/wiki/Prime_ideal"}],
        items=[{"form": "passage", "id": passage, "id_source": "quote_hash", "kind": "passage",
                "kind_source": "producer", "quote": {"exact": WEB_QUOTE, "prefix": "a prime ideal is "},
                "section": "Definition", "source": "wiki", "title": "The lead definition", "title_source": "producer"},
               {"coverage": "formalized", "form": "passage", "id": "passage-lead", "id_source": "declared",
                "kind": "passage", "source": "wiki", "title": "The lead paragraph", "title_source": "producer"}],
        declarations=[decl("Ideal.IsPrime", "class", namespace="Ideal", **mathlib),
                      decl("Ideal.IsPrime.ne_top'", "projection", namespace="Ideal.IsPrime", parent="Ideal.IsPrime",
                           **mathlib),
                      decl("Ideal.span_singleton_prime", **mathlib)],
        locations=[loc("passage-lead@lead", "wiki", [quote(WEB_QUOTE, prefix="a prime ideal is "),
                                                    {"type": "CssSelector", "value": "#content > p:nth-of-type(2)"}],
                       ("passage-lead",))],
        links=[link("passage-lead", "Ideal.IsPrime", relation="generalization"),
               link("passage-lead", "Ideal.span_singleton_prime", "attributed", relation="related"),
               link(passage, "Ideal.IsPrime.ne_top'", relation="exact")],
        destinations=[{"declaration": "Ideal.IsPrime", "fragment": "Ideal.IsPrime",
                       "href": "https://docs.example.org/Mathlib/RingTheory/Ideal/Defs.html", "id": "Ideal.IsPrime@docs",
                       "resolution": "exact", "site": "doc_gen4"}],
        provenance=[PROV])


INLINE = {"tex": tex_doc, "media": media_doc, "web": web_doc}


def all_docs() -> list[dict]:
    return [load(n) for n in VALID] + [make() for make in INLINE.values()]


def walk_selectors(sel: dict):
    yield sel
    if "refinedBy" in sel:
        yield from walk_selectors(sel["refinedBy"])


class Case(unittest.TestCase):
    """Assertions shared by the tests below."""

    def assertValid(self, doc) -> None:
        self.assertEqual(lines(doc), [])

    def assertProblem(self, doc, fragment: str, code: str | None = None) -> None:
        found = V.check(doc).problems
        hits = [p for p in found if fragment in str(p)]
        self.assertTrue(hits, f"{fragment!r} not in {[str(p) for p in found]}")
        if code is not None:
            self.assertEqual({p.code for p in hits}, {code}, hits)


# --- the schema file and the vocabulary

def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def schema_properties(node: dict):
    """(where, node) for every definition's and the root's properties, outside conditionals."""
    def walk(n, where, conditional):
        if isinstance(n, dict):
            for key, value in n.items():
                if key == "properties" and not conditional:
                    for name, sub in value.items():
                        yield f"{where}/{name}", sub
                        yield from walk(sub, f"{where}/{name}", conditional)
                elif key == "$defs":
                    for name, sub in value.items():
                        yield from walk(sub, name, False)
                elif key in ("items", "additionalProperties"):
                    yield from walk(value, where, conditional)
                elif key in ("allOf", "anyOf", "oneOf", "if", "then", "else", "not"):
                    yield from walk(value, where, True)
        elif isinstance(n, list):
            for sub in n:
                yield from walk(sub, where, conditional)
    yield from walk(node, "$root", False)


class TestTheSchemaFile(Case):

    def test_it_is_draft_2020_12_with_an_id_per_minor_that_is_never_fetched(self):
        s = schema()
        self.assertEqual(s["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(s["$id"], SCHEMA_ID)
        self.assertEqual(s["$id"], V.schema_id(1, 0))
        self.assertEqual(s["$id"], f"{vocab.ANNOTATION_SCHEMA_ID_BASE}/{SCHEMA.name}")
        self.assertEqual(SCHEMA.name, f"annotations-v{vocab.ANNOTATION_SCHEMA_VERSION}.schema.json")
        self.assertEqual(sorted(p.name for p in SCHEMA.parent.iterdir()), [SCHEMA.name])
        self.assertNotIn("$schema", s["required"])
        self.assertIn("formal-companion-annotations-validate", s["description"])
        for module in PACKAGE.glob("*.py"):                 # nothing can fetch a $id or $schema
            with self.subTest(module=module.name):
                self.assertNotRegex(module.read_text(encoding="utf-8"),
                                    r"(?m)^\s*(import|from)\s+(urllib|http|socket|ssl)\b")

    def test_the_checker_loads_this_file(self):
        self.assertEqual(V.SCHEMA_PATH, V.schema_path(1, 0))
        self.assertEqual(V.SCHEMA_PATH.name, SCHEMA.name)
        self.assertEqual(V.SCHEMA_PATH.read_bytes(), SCHEMA.read_bytes())
        self.assertEqual(V.SCHEMA_PATH.parent, V.SCHEMA_DIR)

    def test_it_is_in_canonical_form(self):
        text = SCHEMA.read_text(encoding="utf-8")
        self.assertEqual(text, V.canonical_dumps(json.loads(text)))

    def test_every_property_says_what_it_means_and_names_its_values(self):
        found = list(schema_properties(schema()))
        self.assertGreater(len(found), 250)
        for where, node in found:
            with self.subTest(property=where):
                self.assertGreaterEqual(len(node.get("description", "").split()), 2)
                for value in node.get("enum", ()):
                    self.assertIn(value, node["description"])

    def test_every_record_is_closed_and_takes_x_keys(self):
        d = schema()["$defs"]
        for name in ("source", "item", "declaration", "artifact", "membership", "link", "provenance",
                     "location", "destination", "snippet", "verdict", "unattributed", "cluster", "change"):
            with self.subTest(record=name):
                self.assertIs(d[name]["additionalProperties"], False)
                self.assertEqual(list(d[name]["patternProperties"]), ["^x_[a-z0-9_]+$"])
                self.assertIn("id", d[name]["required"])
        for name in ("pages", "quote", "signoff", "target", "relations", "resolution", "graph_lock", "input_lock",
                     "page_size", "page_hash", "identifiers", "xref", "package", *vocab.ANNOTATION_SELECTOR_TYPES):
            with self.subTest(sub_object=name):
                self.assertIs(d[name]["additionalProperties"], False)
                self.assertNotIn("patternProperties", d[name])
        root = schema()["properties"]
        self.assertEqual({k for k, v in root.items() if v.get("type") == "array"}, set(V.RECORD_ARRAYS))

    def test_the_profiles_object_is_closed_and_versioned(self):
        profiles = schema()["properties"]["profiles"]
        self.assertIs(profiles["additionalProperties"], False)
        self.assertEqual(set(profiles["properties"]), set(vocab.ANNOTATION_PROFILES))
        for name, sub in profiles["properties"].items():
            self.assertEqual(sub["pattern"], "^1\\.(0|[1-9][0-9]*)$")
            self.assertRegex(vocab.ANNOTATION_PROFILE_VERSIONS[name], sub["pattern"])

    def test_the_evaluator_refuses_a_keyword_it_does_not_implement(self):
        with self.assertRaises(S.SchemaError):
            S.Validator({"type": "string", "format": "date-time"})
        with self.assertRaises(S.SchemaError):
            S.Validator({"$ref": "https://example.org/other.json"})

    def test_a_site_page_path_and_a_relative_href_share_one_grammar(self):
        d = schema()["$defs"]
        self.assertEqual(d["SitePageSelector"]["properties"]["path"]["$ref"], "#/$defs/site_path")
        self.assertEqual(d["page_hash"]["properties"]["path"]["$ref"], "#/$defs/site_path")
        self.assertIn({"$ref": "#/$defs/site_path"}, d["destination"]["properties"]["href"]["anyOf"])
        ours = S.Validator(schema())
        for path in ("Notes/Section_2/", "a/b.html", "a:b.html", "/abs", "../up", "a#frag", "a b"):
            doc = load("site-pages.json")
            doc["locations"][0]["target"]["selector"][0]["path"] = path
            doc["destinations"][0]["href"] = path
            errors = [p for p, _m in ours.errors(doc)]
            with self.subTest(path=path):
                self.assertEqual(any(".path" in p for p in errors), any(".href" in p for p in errors), errors)
                self.assertEqual(bool(errors), path not in ("Notes/Section_2/", "a/b.html"))


class TestOneVocabulary(unittest.TestCase):
    """Every enum of the schema is a set of vocab, and the other closed sets agree."""

    #: Every enum of the schema, by its property, and the vocab set ``ANNOTATION_<name>`` it must be.
    ENUMS = {
        "source/kind": "SOURCE_KINDS", "source/scope": "SOURCE_SCOPES", "source/role": "SOURCE_ROLES",
        "item/form": "ITEM_FORMS", "item/id_source": "ITEM_ID_SOURCES", "item/kind_source": "TEXT_ORIGINS",
        "item/title_source": "TEXT_ORIGINS", "item/coverage": "COVERAGE", "pages/basis": "PAGE_BASES",
        "pages/anchor": "PAGE_ANCHORS", "declaration/kind": "LEAN_KINDS", "declaration/id_source": "ID_SOURCES",
        "declaration/sorry": "SORRY_CLASSES", "artifact/kind": "ARTIFACT_KINDS", "membership/role": "MEMBERSHIP_ROLES",
        "link/role": "LINK_ROLES", "provenance/actor": "PROVENANCE_ACTORS", "provenance/method": "PROVENANCE_METHODS",
        "destination/site": "DESTINATION_SITES", "destination/resolution": "DESTINATION_RESOLUTIONS",
        "coordinate_space/origin": "COORDINATE_ORIGINS", "coordinate_space/units": "COORDINATE_UNITS",
        "coordinate_space/x_axis": "COORDINATE_X_AXES", "coordinate_space/y_axis": "COORDINATE_Y_AXES",
        "coordinate_space/page_box": "PAGE_BOXES", "text_layer/unicode": "TEXT_UNICODE",
        "text_layer/whitespace": "TEXT_WHITESPACE", "text_layer/case": "TEXT_CASE", "verdict/verdict": "VERDICTS",
        "verdict/declarations/verdict": "VERDICTS", "verdict/severity": "SEVERITIES",
        "verdict/status": "VERDICT_STATUSES", "resolution/state": "RESOLUTION_STATES",
        "unattributed/claim": "UNATTRIBUTED_CLAIMS", "change/event": "CHANGELOG_EVENTS",
        "change/subject_kind": "CHANGELOG_SUBJECTS", "change/reason": "CHANGELOG_REASONS",
        "selector/type": "SELECTOR_TYPES",
    }

    def test_every_enum_in_the_schema_is_a_vocab_set(self):
        found = {where: node["enum"] for where, node in schema_properties(schema()) if "enum" in node}
        self.assertEqual(set(found), set(self.ENUMS))
        for where, values in found.items():
            with self.subTest(enum=where):
                self.assertEqual(set(values), set(getattr(vocab, "ANNOTATION_" + self.ENUMS[where])))
                self.assertEqual(values, sorted(values))

    def test_the_other_closed_and_open_sets(self):
        s = schema()
        d = s["$defs"]
        self.assertEqual(set(d["relations"]["properties"]), set(vocab.ANNOTATION_ITEM_RELATIONS))
        self.assertEqual(s["properties"]["schema"]["const"], vocab.ANNOTATION_SCHEMA)
        self.assertEqual(set(vocab.ANNOTATION_PROFILE_VERSIONS), set(vocab.ANNOTATION_PROFILES))
        self.assertEqual(set(V.PROFILES), set(vocab.ANNOTATION_PROFILES))
        self.assertEqual(set(vocab.ANNOTATION_ORIGIN_Y_AXIS), set(vocab.ANNOTATION_COORDINATE_ORIGINS))
        self.assertEqual(set(vocab.ANNOTATION_ORIGIN_Y_AXIS.values()), set(vocab.ANNOTATION_COORDINATE_Y_AXES))
        for kinds in vocab.ANNOTATION_MEMBER_PARENT_KINDS.values():
            self.assertLessEqual(kinds, vocab.ANNOTATION_LEAN_KINDS)
        members = [rule for rule in d["declaration"]["allOf"]
                   if "kind" in rule["if"].get("properties", {}) and rule["then"].get("required") == ["parent"]]
        self.assertEqual(set(members[0]["if"]["properties"]["kind"]["enum"]), set(vocab.ANNOTATION_MEMBER_PARENT_KINDS))
        for name in vocab.ANNOTATION_SELECTOR_TYPES:
            self.assertEqual(d[name]["properties"]["type"]["const"], name)
        # open fields with a documented core: an IRI and two snake_case tokens
        self.assertNotIn("enum", d["FragmentSelector"]["properties"]["conformsTo"])
        self.assertNotIn("enum", d["link"]["properties"]["relation"])
        self.assertNotIn("enum", d["xref"]["properties"]["database"])
        self.assertEqual(set(V.CONFORMS), set(vocab.ANNOTATION_CONFORMS_TO))
        for token in vocab.ANNOTATION_LINK_RELATIONS | vocab.ANNOTATION_XREF_DATABASES:
            self.assertRegex(token, d["link"]["properties"]["relation"]["pattern"])

    def test_one_id_grammar_for_the_writer_and_the_checker(self):
        self.assertIs(V._DECLARED_ID, ids.DECLARED_ID)
        self.assertIs(V._HASH_ID, ids.HASH_ID)
        self.assertIn(vocab.HASH_ID_PATTERN, ids.HASH_ID.pattern)
        self.assertIn(vocab.DECLARED_ID_PATTERN, ids.DECLARED_ID.pattern)


# --- one regex dialect: the schema's patterns and the checker's own grammars

def schema_patterns() -> list[tuple[str, str]]:
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
    walk(schema(), "#")
    return found


class TestRegexHygiene(Case):

    FORBIDDEN = re.compile(r"\\[dDwWsSbBAZpP]|\(\?P<|\(\?<[A-Za-z]|\(\?[a-zA-Z]+[:)]|\(\?#")

    def test_every_schema_pattern_is_dialect_neutral(self):
        patterns = schema_patterns()
        self.assertGreater(len(patterns), 20)
        for where, pattern in patterns:
            with self.subTest(where=where, pattern=pattern):
                self.assertIsNone(self.FORBIDDEN.search(pattern))
                self.assertTrue(pattern.isascii())
                outside = re.sub(r"\[(?:\\.|[^\]\\])*\]", "", pattern)
                self.assertNotRegex(outside, r"(?<!\\)\.", "'.' outside a class")
                S._translate(pattern, where)

    def test_no_whitespace_is_the_one_explicit_class(self):
        by_where = dict(schema_patterns())
        for where in ("#/$defs/id/pattern", "#/$defs/ref/pattern", "#/$defs/http_url/pattern",
                      "#/$defs/repo_path/pattern", "#/$defs/FragmentSelector/properties/conformsTo/pattern"):
            self.assertIn(S._NO_WHITESPACE, by_where[where])
        for where in ("#/$defs/site_path/pattern", "#/$defs/destination/properties/fragment/pattern"):
            self.assertIn("[^" + S._WHITESPACE, by_where[where])
        compiled = re.compile("[" + S._WHITESPACE + "]")
        for cp in (0x09, 0x0A, 0x0B, 0x0D, 0x20, 0xA0, 0x1680, 0x2000, 0x2028, 0x202F, 0x3000, 0xFEFF, 0x00, 0x1C,
                   0x7F, 0x85):
            self.assertTrue(compiled.fullmatch(chr(cp)), hex(cp))
        for cp in (0x21, 0x41, 0x200B, 0x2060, 0x1F600):
            self.assertFalse(compiled.fullmatch(chr(cp)), hex(cp))

    def test_schemacheck_refuses_the_dialect_dependent_constructs(self):
        for pattern in (r"^\d+$", r"^\S+$", r"^\w+$", r"a\b", r"\Ax", r"(?P<n>a)", r"(?<n>a)", r"(?i)abc",
                        r"(?#c)a", r"^a.b$", r"[]", r"[^]", r"\p{L}", r"\u12", r"\xZ"):
            with self.subTest(pattern=pattern):
                with self.assertRaises(S.SchemaError):
                    S.Validator({"type": "string", "pattern": pattern})
                with self.assertRaises(S.SchemaError):
                    S.Validator({"type": "object", "patternProperties": {pattern: {}}})
        for pattern in (r"^[0-9]+$", r"^(?!x)(?:a|b)(?=c)[^" + S._WHITESPACE + r"]+$", r"^a\.b$", r"^[.]$",
                        r"(?<!x)y", r"^\u0041$", r"^\x41$"):
            S.Validator({"type": "string", "pattern": pattern})

    def test_a_dollar_is_the_end_of_the_string(self):
        checker = S.Validator({"type": "string", "pattern": "^[a-z]+$"})
        self.assertTrue(checker.is_valid("abc"))
        self.assertFalse(checker.is_valid("abc\n"), "Python's $ would accept it; ECMA-262's does not")
        self.assertFalse(S.Validator({"type": "string", "pattern": "^(a|$)(/|$)"}).is_valid("\n"))
        self.assertTrue(S.Validator({"type": "string", "pattern": r"^\$$"}).is_valid("$"))
        self.assertTrue(S.Validator({"type": "string", "pattern": "^[$]$"}).is_valid("$"))

    def test_the_trap_inputs_are_refused(self):
        """A trailing newline, U+FEFF and U+001C in a no-whitespace field, a non-ASCII digit."""
        doc = load("pdf-region.json")
        doc["companion"]["commit"] += "\n"
        self.assertEqual(lines(doc), ['$.companion.commit: "ed00b5dc6b11040ed2f9baf475edc9b48e1c7f4a\\n" does not '
                                      'match ^([0-9a-f]{40}|[0-9a-f]{64})$ [SCHEMA]'])
        doc = load("pdf-region.json")
        doc["companion"]["x_note\n"] = 1
        self.assertEqual(codes(doc), ["SCHEMA"])
        for bad, ok in (("foo\n", False), ("foo" + BOM, False), ("foo" + FILE_SEPARATOR, False), (BOM + "foo", False),
                        ("foo" + NBSP + "bar", False), ("foo\tbar", False), ("foo" + chr(0x2028), False),
                        ("foo" + chr(0x200B), True), ("Foo.bar" + chr(0x1F600), True)):
            doc = load("pdf-region.json")
            decl_ = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
            by_id(doc["links"], "lemma-1.2/key/Notes.Box.volume_nonneg")["declaration"] = bad
            decl_["id"] = decl_["name"] = bad
            found = V.check(V.canonicalize(doc)).problems
            with self.subTest(id=ascii(bad)):
                self.assertEqual(not found, ok, found)
                self.assertTrue(all(p.code == "SCHEMA" for p in found), found)
                self.assertEqual(ok, not any(p.path.endswith(".id") for p in found))
        doc = load("pdf-region.json")
        sel = by_id(doc["locations"], "passage-p6-ef94b64f@p010")["target"]["selector"][0]
        for value in ("page=1" + ARABIC_INDIC_ZERO, "page=10\n", "page=" + chr(0xFF11) + chr(0xFF10)):
            sel["value"] = value
            self.assertProblem(doc, "is not a positive integer (ASCII digits, at most 9)", "I7")

    def test_the_checkers_own_grammars_use_fullmatch_and_ascii_digits(self):
        for grammar, bad in ((V._RFC5147, "line=41,47\n"), (V._RFC5147, "line=" + ARABIC_INDIC_ZERO + ",47"),
                             (V._XYWH, "1,2,3,4\n"), (V._MEDIA_T, "10,20\n"), (V._PAGE, "1" + ARABIC_INDIC_ZERO),
                             (V._NAMED_ID, "Foo.bar\n"), (V._NAMED_ID, "Foo" + BOM), (V._VERSION, "1.0\n"),
                             (V._DATE, "2026-09-05\n"), (V._RESERVED_PASSAGE, "passage-0123abcd\n"),
                             (ids.HASH_ID, PDF_EXAMPLE + "\n")):
            with self.subTest(bad=ascii(bad)):
                self.assertIsNone(grammar.fullmatch(bad))
        self.assertTrue(re.match("^(?:" + vocab.HASH_ID_PATTERN + ")$", PDF_EXAMPLE + "\n"), "the trap avoided")
        code = (PACKAGE / "validate.py").read_text(encoding="utf-8")
        for construct in ("\\d", "\\s", "\\S", "\\w", "re.match("):
            self.assertNotIn(construct, code)
        self.assertNotIn(".match(", code.replace("fullmatch(", ""))


# --- the examples and the documents built here

class TestTheExamples(Case):

    def test_the_valid_examples_validate_in_canonical_form(self):
        for name in VALID:
            with self.subTest(example=name):
                data = (EXAMPLES / name).read_bytes()
                report = V.check(V.loads(data), text=data, canonical=True)
                self.assertEqual((report.problems, report.warnings), ([], []))
        self.assertEqual(sorted(p.name for p in EXAMPLES.glob("*.json")), sorted(VALID + INVALID))

    def test_each_invalid_example_fails_with_exactly_its_recorded_line(self):
        for name in INVALID:
            doc = load(name)
            self.assertEqual(lines(doc), [doc["x_expected_error"]])

    def test_the_documents_built_here_are_valid(self):
        for name, make in INLINE.items():
            with self.subTest(document=name):
                doc = make()
                self.assertValid(doc)
                expected = [("W-CONFORMS", "$.locations[1].target.selector[0].conformsTo")] if name == "media" else []
                self.assertEqual(warnings(doc), expected)

    def test_every_feature_is_exercised(self):
        """The examples and the documents built here use every record array, enum value, selector, IRI and medium."""
        docs = all_docs()
        values = lambda array, field: {r.get(field) for d in docs for r in d.get(array, [])}   # noqa: E731
        for array in V.RECORD_ARRAYS:
            self.assertTrue(any(d.get(array) for d in docs), array)
        self.assertEqual(values("items", "id_source"), set(vocab.ANNOTATION_ITEM_ID_SOURCES))
        self.assertEqual(values("items", "coverage") - {None}, set(vocab.ANNOTATION_COVERAGE))
        self.assertEqual(values("declarations", "id_source"), set(vocab.ANNOTATION_ID_SOURCES))
        self.assertLessEqual(set(vocab.ANNOTATION_MEMBER_PARENT_KINDS) | {"alias", "irreducible_def", "class"},
                             values("declarations", "kind"))
        self.assertEqual(values("artifacts", "kind"), {"module_doc", "check", "figure"})
        self.assertEqual(values("memberships", "role"), set(vocab.ANNOTATION_MEMBERSHIP_ROLES))
        self.assertEqual(values("changelog", "event"), set(vocab.ANNOTATION_CHANGELOG_EVENTS))
        self.assertEqual(values("links", "relation") - {None}, set(vocab.ANNOTATION_LINK_RELATIONS))
        self.assertEqual(values("links", "role"), set(vocab.ANNOTATION_LINK_ROLES))
        self.assertLessEqual({"verso_literate", "doc_gen4"}, values("destinations", "site"))
        self.assertEqual({k for d in docs for i in d["items"] for k in i.get("relations", {})},
                         set(vocab.ANNOTATION_ITEM_RELATIONS))
        self.assertEqual({s["kind"] for d in docs for s in d["sources"]}, set(vocab.ANNOTATION_SOURCE_KINDS))
        self.assertEqual({V.source_family(s) for d in docs for s in d["sources"]}, {"pdf", "html", "text", "generic"})
        seen, conforms, regions = set(), set(), set()
        for d in docs:
            for location in d.get("locations", []):
                for top in location["target"]["selector"]:
                    for sel in walk_selectors(top):
                        seen.add(sel["type"])
                        conforms.add(sel.get("conformsTo"))
                        if sel["type"] == "PdfRegionSelector":
                            regions |= {"rect" if "rect" in sel else "quads", sel["coordinate_space"]["units"]}
        self.assertEqual(seen, set(vocab.ANNOTATION_SELECTOR_TYPES))
        self.assertEqual(conforms - {None, EPUB_CFI}, set(vocab.ANNOTATION_CONFORMS_TO))
        self.assertEqual(regions, {"rect", "quads", "normalized", "pt"})
        inputs = {k for d in docs for p in d["provenance"] for i in p.get("inputs", []) for k in i}
        self.assertTrue({"path", "source"} <= inputs)

    def test_mixed_exercises_every_profile(self):
        """Every array and field of every profile appears in mixed.json, which declares all four."""
        doc = load("mixed.json")
        self.assertEqual(doc["profiles"], ALL_PROFILES)
        for name, owned in V.PROFILES.items():
            for array in owned["arrays"]:
                self.assertTrue(doc[array], array)
            for dotted in owned["fields"]:
                head, _, field = dotted.partition(".")
                records = [doc["companion"]] if head == "companion" else doc[head]
                with self.subTest(profile=name, field=dotted):
                    self.assertTrue(any(field in r for r in records))
        self.assertTrue({"toolchain", "packages", "graph"} <= set(doc["companion"]))
        self.assertTrue(any(c["event"] == "ordinal_assigned" for c in doc["changelog"]))

    def test_the_examples_quote_no_real_source(self):
        for doc in all_docs() + [load(n) for n in INVALID]:
            for source in doc["sources"]:
                if source["kind"] != "lean":
                    self.assertIn("synthetic", source["title"])
                for url in [source.get("url")] + source.get("alternate_urls", []):
                    if url:
                        self.assertRegex(url, r"^https://[a-z.]*example\.org/")

    def test_the_readme_shows_minimal_json(self):
        block = re.search(r"```json\n(.*?)```\n", (ROOT / "README.md").read_text(encoding="utf-8"), re.S)
        self.assertEqual(block.group(1), (EXAMPLES / "minimal.json").read_text(encoding="utf-8"))


# --- I-JSON: the loader and the same limits on in-memory values (IJSON)

class TestIJson(Case):

    def test_loads_takes_str_or_bytes_strictly(self):
        self.assertEqual(V.loads('{"a": [1, 2.5, "x", null, true]}'), {"a": [1, 2.5, "x", None, True]})
        self.assertEqual(V.loads(bytearray(b"[1]")), [1])
        with self.assertRaises(TypeError):
            V.loads(3)                                                  # type: ignore[arg-type]
        for text, message in ((b'{"a": "\xff"}', "not UTF-8"), ('{"a": 1}'.encode("utf-16"), "not UTF-8"),
                              ("{", "not JSON"), (b"\xef\xbb\xbf{}", "byte-order mark"), (BOM + "{}", "byte-order mark"),
                              ('{"a": {"b": 1, "b": 1}}', "duplicate key 'b'"), ('{"a": NaN}', "NaN is not JSON"),
                              ('{"a": -Infinity}', "is not JSON")):
            with self.subTest(text=text), self.assertRaisesRegex(V.LoadError, message):
                V.loads(text)
        self.assertTrue(issubclass(V.LoadError, ValueError))

    def test_numbers_are_finite_in_range_and_short(self):
        for text, message in (('{"x_a": 1e400}', "1e400 is not a finite number"), ("-1e999", "not a finite number"),
                              ("9007199254740992", r"outside \+-\(2\^53 - 1\)"), ("1e300", "outside"),
                              ("1" * 401, "401 characters is longer than 400"),
                              ("[" + "9" * 5000 + "]", "5000 characters is longer than 400"),
                              ("1" + "0" * 396 + "e-400", "longer than 400")):
            with self.subTest(text=text[:20]), self.assertRaisesRegex(V.LoadError, message):
                V.loads(text)
        self.assertEqual(V.loads("-9007199254740991"), -(2 ** 53 - 1))
        self.assertEqual(V.loads("1" + "0" * 390 + "e-400"), 1e-10)
        parsed = V.loads("[6.0, 1e3, -0.0, 0.5, 1.0e2]")
        self.assertEqual(parsed, [6, 1000, 0, 0.5, 100])
        self.assertEqual([type(v) for v in parsed], [int, int, int, float, int])

    def test_lone_surrogates_and_deep_nesting_are_refused(self):
        with self.assertRaisesRegex(V.LoadError, r"\$\.a\[1\]\.b: contains a lone surrogate"):
            V.loads('{"a": [0, {"b": "x' + JSON_LONE_SURROGATE + '"}]}')
        with self.assertRaisesRegex(V.LoadError, r"\$: key .* contains a lone surrogate"):
            V.loads('{"' + JSON_LONE_SURROGATE + '": 1}')
        self.assertEqual(V.loads('{"a": "\\ud83d\\ude00"}'), {"a": chr(0x1F600)})
        self.assertEqual(V.loads("[" * 64 + "]" * 64), json.loads("[" * 64 + "]" * 64))
        for text in ("[" * 65 + "]" * 65, "[" * 100000 + "]" * 100000):
            with self.assertRaisesRegex(V.LoadError, "nested deeper than 64 levels"):
                V.loads(text)
        with self.assertRaisesRegex(V.LoadError, r"\$\.x_a(\[0\]){63}: nested deeper than 64"):
            V.loads('{"x_a": ' + "[" * 500 + "]" * 500 + "}")

    def test_check_reports_the_limits_in_memory_with_code_ijson(self):
        doc = load("pdf-region.json")
        rect = by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][0]["refinedBy"]["rect"]
        rect["x1"] = float("inf")
        self.assertEqual(lines(doc), ["$.locations[0].target.selector[0].refinedBy.rect.x1: inf is not a finite "
                                      "number [IJSON]"])
        rect["x1"] = 10 ** 400
        self.assertIn("an integer of about 401 digits is outside +-(2^53 - 1)", lines(doc)[0])
        doc = load("pdf-region.json")
        doc["x_meta"] = {"a": (1, 2), "b": b"x", 1: 2}
        self.assertEqual(lines(doc), ["$.x_meta: key 1 is not a string [IJSON]",
                                      "$.x_meta.a: a tuple is not a JSON value [IJSON]",
                                      "$.x_meta.b: a bytes is not a JSON value [IJSON]"])
        for mutate in (lambda d: d["provenance"][1].__setitem__("note", "x" + LONE_SURROGATE),
                       lambda d: d.__setitem__("x_" + LONE_SURROGATE, 1),
                       lambda d: d["items"][0].__setitem__("id", "definition-" + LONE_SURROGATE)):
            doc = load("pdf-region.json")
            mutate(doc)
            (problem,) = V.check(doc).problems
            self.assertEqual(problem.code, "IJSON")
            self.assertTrue(problem.message.isascii() and "lone surrogate" in problem.message)
        doc = load("pdf-region.json")
        deep: list = []
        for _ in range(999):
            deep = [deep]
        doc["x_meta"] = deep
        self.assertEqual(codes(doc), ["IJSON"])
        chain: dict = {}
        for _ in range(70):
            chain = {"x_a": chain}
        self.assertEqual(lines({"x_d": chain}), ["$.x_d" + ".x_a" * 63 + ": nested deeper than 64 levels [IJSON]"])

    def test_the_pre_pass_stops_everything_else_and_reads_integral_floats_as_ints(self):
        doc = load("pdf-region.json")
        doc["x_meta"] = float("inf")
        del doc["sources"]
        self.assertEqual(codes(doc), ["IJSON"])
        self.assertEqual(codes(doc, lints=("external-urls",), text="{}", canonical=True), ["IJSON"])
        doc = load("pdf-region.json")
        doc["sources"][0]["physical_page_count"] = 40.0
        by_id(doc["items"], "passage-p6-ef94b64f")["pages"]["first"] = 6.0
        self.assertValid(doc)
        self.assertEqual(by_id(doc["items"], "passage-p6-ef94b64f")["pages"]["first"], 6.0, "the caller's object")
        doc["sources"][0]["physical_page_count"] = 40.5
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = load("pdf-region.json")                       # deep, but I-JSON: checked, not crashed
        chain: dict = quote("q")
        for _ in range(40):
            chain = quote("q", chain)
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"] = [chain]
        self.assertNotIn("IJSON", codes(doc))


# --- the canonical form (I11, I2 and the order)

class TestCanonicalForm(Case):

    def test_numbers_follow_ecmascript(self):
        cases = {1.0: "1", 0.00001: "0.00001", -0.0: "0", 1e21: "1e+21", 1e20: "100000000000000000000", 1e-7: "1e-7",
                 1e-6: "0.000001", 333333333.33333329: "333333333.3333333", 4.50: "4.5", 5e-324: "5e-324",
                 1.7976931348623157e308: "1.7976931348623157e+308", 2 ** 53: "9007199254740992",
                 2 ** 60: "1152921504606847000", 0.1 + 0.2: "0.30000000000000004", 123e-20: "1.23e-18"}
        for value, want in cases.items():
            self.assertEqual(V.jcs_number(value), want)
        self.assertEqual(V.canonical_dumps({"a": 1.0, "b": 0.00001}), '{\n  "a": 1,\n  "b": 0.00001\n}\n')

    def test_strings_and_layout_follow_json_stringify(self):
        self.assertEqual(V.canonical_dumps(["\u001f\n\t\"\\/é "]), '[\n  "\\u001f\\n\\t\\"\\\\/é "\n]\n')
        self.assertEqual(V.canonical_dumps({"a": [], "b": {}, "c": None, "d": True}),
                         '{\n  "a": [],\n  "b": {},\n  "c": null,\n  "d": true\n}\n')

    def test_keys_ids_and_sets_sort_by_utf16_code_units(self):
        astral, bmp = "\U0001d400", "Ａ"
        text = V.canonical_dumps({"": 1, "b": 3, "a": 4, bmp: 5, astral: 6})
        self.assertEqual([line.split('"')[1] for line in text.splitlines()[1:-1]], ["", "a", "b", astral, bmp])
        self.assertLess(bmp, astral)
        self.assertLess(V.order_key(astral), V.order_key(bmp))
        doc = load("pdf-region.json")
        base = {k: v for k, v in by_id(doc["items"], "definition-1.1").items() if k != "coverage"}
        doc["items"] += [dict(base, id=f"item-{c}", id_source="declared", number=f"9.{n}", legacy_ids=[bmp, astral])
                         for n, c in ((1, bmp), (2, astral))]
        doc = V.canonicalize(doc)
        order = [i["id"] for i in doc["items"]]
        self.assertLess(order.index(f"item-{astral}"), order.index(f"item-{bmp}"))
        self.assertEqual(doc["items"][order.index(f"item-{bmp}")]["legacy_ids"], [astral, bmp])
        self.assertValid(doc)
        i, j = order.index(f"item-{astral}"), order.index(f"item-{bmp}")
        doc["items"][i], doc["items"][j] = doc["items"][j], doc["items"][i]
        self.assertProblem(doc, "is not sorted by id (UTF-16 code units)", "I2")

    def test_a_shuffled_document_canonicalises_to_the_same_bytes(self):
        for name in VALID:
            original = (EXAMPLES / name).read_text(encoding="utf-8")
            for seed in range(4):
                rng = random.Random(seed)

                def mix(value):
                    if isinstance(value, dict):
                        keys = list(value)
                        rng.shuffle(keys)
                        return {k: mix(value[k]) for k in keys}
                    return [mix(v) for v in value] if isinstance(value, list) else value
                messy = mix(V.loads(original))
                rng.shuffle(messy["companion"].get("packages", []))
                for key in V.RECORD_ARRAYS:
                    rng.shuffle(messy.get(key, []))
                    for rec in messy.get(key, []):
                        for dotted in V.SET_FIELDS.get(key, ()):
                            rng.shuffle(V._get(rec, dotted) or [])
                        for field, _key in V.KEYED_LISTS.get(key, ()):
                            rng.shuffle(rec.get(field, []))
                with self.subTest(example=name, seed=seed):
                    self.assertEqual(V.canonical_dumps(V.canonicalize(messy)), original)

    def test_selector_alternatives_and_evidence_keep_their_order(self):
        doc = load("pdf-region.json")
        selectors = by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"]
        selectors.reverse()
        after = by_id(V.canonicalize(doc)["locations"], "definition-1.1@p007")["target"]["selector"]
        self.assertEqual(after, selectors)
        doc = load("mixed.json")
        doc["verdicts"][0]["evidence"].reverse()
        self.assertEqual(V.canonicalize(doc)["verdicts"][0]["evidence"], doc["verdicts"][0]["evidence"])
        self.assertValid(doc)

    def test_unsorted_arrays_sets_and_keyed_lists_are_i2(self):
        doc = load("pdf-region.json")
        doc["items"].reverse()
        self.assertProblem(doc, "$.items[1].id: items[] is not sorted by id", "I2")
        doc = load("mixed.json")
        doc["verdicts"][0]["resolution"]["commits"].reverse()
        self.assertProblem(doc, "resolution.commits: must be sorted", "I2")
        doc = load("mixed.json")
        by_id(doc["provenance"], "prov-graph")["inputs"].reverse()
        self.assertProblem(doc, "inputs: must be sorted by path, then source, one entry each", "I2")
        doc = load("mixed.json")
        doc["companion"]["packages"].reverse()
        self.assertEqual(lines(doc), ["$.companion.packages: must be sorted by name, one entry each [I2]"])
        doc = load("mixed.json")
        doc["items"][0]["xrefs"].reverse()
        self.assertEqual(lines(doc), ["$.items[0].xrefs: must be sorted by (database, tag), one entry each [I2]"])
        doc = load("minimal.json")
        doc["sources"][0]["identifiers"] = {"isbn": ["9781234567897", "9780000000002"]}
        self.assertEqual(lines(doc), ["$.sources[0].identifiers.isbn: must be sorted (UTF-16 code units) [I2]"])
        doc["sources"][0]["identifiers"] = {"isbn": ["9780000000002", "9780000000002"]}
        self.assertEqual(codes(doc), ["SCHEMA"])                    # a repeated entry: uniqueItems

    def test_the_writer_refuses_what_loads_would_not_return(self):
        for value, error, message in (({"a": 10 ** 400}, ValueError, "too large for a double"),
                                      ({1: 2}, TypeError, "an object key must be a string, not int: 1"),
                                      ({"a": object()}, TypeError, "object is not JSON"),
                                      ([float("nan")], ValueError, "NaN and Infinity are not JSON")):
            with self.assertRaisesRegex(error, message):
                V.canonical_dumps(value)
        doc = load("minimal.json")
        doc["items"][0]["legacy_ids"] = [{"a": 1}, "x", "x"]            # not a set of strings: left for the schema
        self.assertEqual(V.canonicalize(doc)["items"][0]["legacy_ids"], [{"a": 1}, "x", "x"])
        doc = malformed_records()
        self.assertEqual([p.get("name") for p in V.canonicalize(doc)["companion"]["packages"]], ["a", 5, None, None])
        self.assertTrue(V.canonical_dumps(V.canonicalize(doc)))
        self.assertIn("SCHEMA", codes(doc))

        def paths(x, p=()):
            yield p
            if isinstance(x, dict):
                for k, v in x.items():
                    yield from paths(v, p + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from paths(v, p + (i,))
        rng = random.Random(1)
        values = [10 ** 400, {1: 2}, [{"a": 1}], [[1], [1]], object(), float("nan"), "", None, 1, {"id": 3},
                  [None, "a"], {"name": []}]
        for _ in range(300):
            doc = load(rng.choice(VALID))
            *where, last = rng.choice(list(paths(doc))[1:])
            parent = doc
            for key in where:
                parent = parent[key]
            parent[last] = rng.choice(values)
            try:
                V.canonical_dumps(V.canonicalize(doc))
            except (TypeError, ValueError):
                pass


# --- the invariants, one class of rules at a time

class TestIdsReferencesAndProfiles(Case):
    """I1, I3, I13 and I14."""

    def test_i1_ids_are_unique_in_their_array(self):
        doc = load("site-pages.json")
        item = by_id(doc["items"], "passage-2caa5bb1")
        doc["items"].append(dict(item, title="The same passage again"))
        self.assertProblem(V.canonicalize(doc), "duplicate id 'passage-2caa5bb1' in items[]", "I1")

    def test_i3_references_resolve(self):
        self.assertEqual(lines(load("invalid-dangling-reference.json")),
                         ["$.links[2].declaration: 'Notes.Box.volume_pos' is not an id in declarations[] [I3]"])
        doc = load("mixed.json")
        by_id(doc["items"], "passage-boxes-motivation")["relations"]["near"] = ["passage-boxes-motivation"]
        self.assertProblem(doc, "an item is not related to itself", "I3")
        doc = load("mixed.json")
        member = next(m for m in doc["memberships"] if "declaration" in m)
        member["artifact"] = member.pop("declaration").replace("Notes.Box", "module_doc:Nowhere")
        self.assertProblem(doc, "'module_doc:Nowhere' is not an id in artifacts[]", "I3")
        doc = load("mixed.json")
        doc["verdicts"][0]["resolution"]["replaced_by"].append("Notes.Zz")
        self.assertProblem(doc, "'Notes.Zz' is not an id in declarations[]", "I3")
        doc = load("site-pages.json")
        by_id(doc["provenance"], "prov-text")["inputs"] = [{"source": "no-such-source"}]
        self.assertProblem(doc, "'no-such-source' is not an id in sources[]", "I3")
        doc = load("minimal.json")
        doc["items"][0]["clusters"] = ["c"]
        doc["profiles"] = {"graph": "1.0"}
        self.assertProblem(doc, "'c' names a record in clusters[], and the document has no clusters[]", "I3")

    def test_i3_link_membership_and_snippet_keys_are_unique(self):
        doc = load("pdf-region.json")
        doc["links"].append(dict(by_id(doc["links"], "definition-1.1/key/Notes.Box"), id="zz-again"))
        self.assertEqual(lines(doc), ["$.links[4]: repeats the link at $.links[0] (same item, target, role and "
                                      "sub) [I3]"])
        doc["links"][-1]["sub"] = "ii"
        self.assertValid(doc)
        doc = load("mixed.json")
        doc["memberships"].append(dict(doc["memberships"][0], id="zz-duplicate"))
        self.assertProblem(doc, "repeats the membership", "I3")
        doc = load("mixed.json")
        doc["snippets"].append(dict(doc["snippets"][0], id="zz-second"))
        self.assertProblem(doc, "already has a snippet at $.snippets[0]", "I3")
        doc = load("mixed.json")
        dest = next(d for d in doc["destinations"] if "artifact" in d)
        dest["declaration"] = "Notes.Box"
        self.assertProblem(doc, "must match exactly one alternative (oneOf)", "SCHEMA")

    def test_i3_verdicts_and_orphaned_links(self):
        doc = load("mixed.json")
        doc["verdicts"][0]["locations"] = ["definition-1.1@p007", "passage-remark-unions@p007"]
        self.assertProblem(doc, "does not show item 'definition-1.1'", "I3")
        doc = load("mixed.json")
        doc["verdicts"][0]["resolution"] = {"state": "open"}
        self.assertProblem(doc, "status is fixed, so the resolution must be fixed", "I3")
        doc = load("mixed.json")
        del doc["verdicts"][0]["resolution"]
        self.assertProblem(doc, "$.verdicts[0].status: status is fixed, so the resolution must be fixed (a verdict "
                                "without a resolution is open)", "I3")
        doc["verdicts"][0]["status"] = "unconfirmed"
        self.assertValid(doc)                                       # no resolution: open
        doc = load("mixed.json")
        retired = next(c for c in doc["changelog"] if c["subject"] == "example:f254071ef195")
        retired["subject_kind"] = "item"
        del retired["possible_successor"]
        self.assertProblem(doc, "is orphaned but no changelog entry retires it", "I3")
        doc = load("mixed.json")
        by_id(doc["links"], "definition-1.1/key/Notes.Box")["orphaned"] = True
        self.assertProblem(doc, "'Notes.Box' is live; an orphaned link names a retired id", "I3")
        doc = load("mixed.json")
        by_id(doc["links"], "definition-1.1/support/section-1")["orphaned"] = True
        self.assertProblem(doc, "only a link to a declaration can be orphaned", "I3")

    def test_i13_an_unattributed_declaration_has_no_link(self):
        doc = load("mixed.json")
        doc["links"].append(link("definition-1.1", "Notes.simp_volume", "support") | {"provenance": "prov-curation"})
        self.assertProblem(V.canonicalize(doc), "'Notes.simp_volume' is linked at", "I13")

    def test_i14_a_profiles_arrays_and_fields_need_it_declared(self):
        self.assertEqual(V.PROFILES, {
            "audit": {"arrays": ("verdicts",), "fields": ()},
            "graph": {"arrays": ("artifacts", "clusters", "memberships"),
                      "fields": ("companion.graph", "declarations.unlocated", "destinations.artifact",
                                 "items.clusters", "links.cluster")},
            "history": {"arrays": ("changelog",), "fields": ("declarations.replaced_by", "links.orphaned")},
            "site": {"arrays": ("destinations", "snippets"), "fields": ()}})
        for name, owned in V.PROFILES.items():
            doc = load("mixed.json")
            want = {f"$.{a}" for a in owned["arrays"]}
            for dotted in owned["fields"]:
                head, _, field = dotted.partition(".")
                if head == "companion":
                    want.add(f"$.companion.{field}")
                else:
                    want |= {f"$.{head}[{i}].{field}" for i, r in enumerate(doc[head]) if field in r}
            del doc["profiles"][name]
            found = V.check(doc).problems
            with self.subTest(profile=name):
                self.assertEqual({(p.code, p.path) for p in found}, {("I14", p) for p in want})
                self.assertTrue(all(f"belongs to the {name} profile, which the document does not declare "
                                    f"(profiles.{name})" in p.message for p in found))
        doc = web_doc()
        del doc["profiles"]
        self.assertEqual(lines(doc), ["$.destinations: destinations[] belongs to the site profile, which the "
                                      "document does not declare (profiles.site) [I14]"])

    def test_i14_a_declared_profile_may_be_unused_and_role_is_core(self):
        doc = load("minimal.json")
        for profiles in ({}, ALL_PROFILES):
            doc["profiles"] = profiles
            self.assertValid(doc)
        for bad in ({"audit": "1"}, ["site"]):
            doc["profiles"] = bad
            self.assertEqual(codes(doc), ["SCHEMA"])
        doc["profiles"] = {"other": "1.0"}
        self.assertEqual(lines(doc), ["$.profiles.other: is not an allowed key here [SCHEMA]"])
        doc = load("mixed.json")
        del doc["profiles"]["audit"], doc["verdicts"]
        self.assertTrue(any("role" in s for s in doc["sources"]))
        self.assertValid(doc)


class TestItems(Case):
    """I4, I6 for items, I12, and the item shapes the schema states."""

    def test_i4_a_passage_is_anchored_and_a_numbered_item_need_not_be(self):
        doc = load("minimal.json")
        del doc["items"][0]["pages"]
        self.assertValid(doc)
        item = doc["items"][0]
        item.update(form="passage", title="The lemma, as a passage", id_source="declared")
        del item["number"]
        self.assertEqual(lines(doc), ["$.items[0]: passage 'lemma-1.2' is anchored nowhere: it needs a location, "
                                      "a quote or pages [I4]"])
        item["quote"] = {"exact": "Lemma 1.2."}
        self.assertValid(doc)

    def test_the_forms_and_coverage_values(self):
        doc = web_doc()
        del doc["items"][1]["title"]
        self.assertProblem(doc, "missing required key 'title'", "SCHEMA")
        for key, value in (("number", "1.2"), ("sub", "ii")):
            doc = web_doc()
            doc["items"][1][key] = value
            self.assertProblem(doc, "(not)", "SCHEMA")
        doc = load("pdf-region.json")
        del by_id(doc["items"], "definition-1.1")["form"]
        self.assertProblem(doc, "missing required key 'form'", "SCHEMA")
        doc = load("mixed.json")
        for value in ("cluster_only", "partial"):
            by_id(doc["items"], "passage-remark-unions")["coverage"] = value
            self.assertProblem(doc, "is not one of", "SCHEMA")

    def test_i6_numbered_identity_is_unique(self):
        doc = load("pdf-region.json")
        doc["items"].append(dict(by_id(doc["items"], "definition-1.1"), id="definition-1.1-again", id_source="declared"))
        self.assertProblem(V.canonicalize(doc), "the same numbered item as", "I6")

    def test_i12_a_label_id_is_kind_number_and_sub(self):
        doc = load("pdf-region.json")
        by_id(doc["items"], "definition-1.1")["number"] = "1.9"
        self.assertProblem(doc, "a label id is <kind>-<number>[-<sub>], here 'definition-1.9'", "I12")
        doc = load("minimal.json")
        item, link_ = doc["items"][0], doc["links"][0]
        for sub in ("ii", "3", "ix,x", "b'", "f''", "a'-c'", "1.2'", "b',c'"):
            item["sub"] = link_["sub"] = sub
            item["id"] = link_["item"] = f"lemma-1.2-{sub}"
            link_["id"] = f"lemma-1.2-{sub}/key/Notes.Box.volume_nonneg"
            with self.subTest(sub=sub):
                self.assertValid(doc)
        for bad in ("(b')", "'b", "b'c", "b' ", "b\u2032", "b'.", "''"):
            item["sub"] = link_["sub"] = bad
            with self.subTest(sub=bad):
                self.assertEqual([(p.code, p.path) for p in V.check(doc).problems],
                                 [("SCHEMA", "$.items[0].sub"), ("SCHEMA", "$.links[0].sub")])
        item["sub"] = link_["sub"] = "b'"
        item["id"] = link_["item"] = "lemma-1.2-b"
        link_["id"] = "lemma-1.2-b/key/Notes.Box.volume_nonneg"
        self.assertEqual(lines(doc), ["$.items[0].id: a label id is <kind>-<number>[-<sub>], here \"lemma-1.2-b'\" "
                                      "[I12]"])
        doc = load("minimal.json")
        doc["items"][0]["kind"] = "---"
        self.assertEqual(lines(doc), ["$.items[0].id_source: kind '---' gives no label slug; declare the id [I12]"])

    def test_i12_a_quote_hash_id_hashes_the_items_quote_or_its_first_locations(self):
        doc = web_doc()
        item = next(i for i in doc["items"] if i["id_source"] == "quote_hash")
        item["quote"]["exact"] += " again"
        self.assertProblem(doc, "a quote_hash id is passage-<8 hex of the normalised quote> (item.quote)", "I12")
        item["quote"]["exact"] = "  "
        self.assertProblem(doc, "a quote_hash id hashes a quote with text in it; item.quote is only whitespace", "I12")
        doc = load("site-pages.json")
        quote_ = by_id(doc["locations"], "passage-2caa5bb1@p022")["target"]["selector"][0]["refinedBy"]
        quote_["exact"] = "every  null set is contained in a Borel null set"     # the normaliser collapses it
        self.assertValid(doc)
        quote_["exact"] += " again"
        self.assertProblem(doc, "(the quote of location 'passage-2caa5bb1@p022')", "I12")
        by_id(doc["locations"], "passage-2caa5bb1@p022")["target"]["selector"][0] = frag(vocab.CONFORMS_TO_PDF,
                                                                                         "page=22")
        self.assertProblem(doc, "a quote_hash id needs item.quote, or a TextQuoteSelector on the item's first "
                                "location", "I12")
        doc = load("site-pages.json")
        by_id(doc["items"], "passage-2caa5bb1")["id_source"] = "page_title_hash"
        self.assertProblem(doc, "a passage with a quote (the quote of location", "I12")

    def test_i12_a_page_title_hash_id_needs_a_printed_page_of_at_least_1(self):
        doc = load("pdf-region.json")
        item = by_id(doc["items"], "passage-p6-ef94b64f")
        self.assertEqual(item["id"], ids.passage_page_id(6, item["title"]))
        item["title"] += "!"
        self.assertProblem(doc, "a page_title_hash id is passage-p<printed page>-<8 hex", "I12")
        item["title"] = " \t "
        self.assertProblem(doc, "a page_title_hash id hashes a title with text in it", "I12")
        doc = load("pdf-region.json")
        item = by_id(doc["items"], "passage-p6-ef94b64f")
        item["pages"] = {"first": 10, "basis": "physical"}           # printed 6 = physical 10 - offset 4
        self.assertValid(doc)
        doc["sources"][0]["printed_page_offset"] = 12
        self.assertProblem(doc, "page_title_hash needs a printed page of at least 1; physical page 10 less the "
                                "source's printed_page_offset is -2", "I12")
        del doc["sources"][0]["printed_page_offset"]
        self.assertProblem(doc, "page_title_hash needs a printed page: pages on the printed basis", "I12")

    def test_i12_a_declared_item_id_may_not_take_a_mechanical_shape(self):
        doc = json.loads((EXAMPLES / "mixed.json").read_text(encoding="utf-8")
                         .replace("passage-remark-unions", "passage-0123abcd"))
        self.assertProblem(V.canonicalize(doc), "has the shape of a mechanical passage id", "I12")


class TestCoverage(Case):
    """I5: the coverage class and the item's non-orphaned links agree."""

    def item(self, doc: dict, rid: str) -> dict:
        return by_id(doc["items"], rid)

    def test_rule_2_links_without_a_key_need_coverage(self):
        doc = load("mixed.json")
        del self.item(doc, "passage-remark-unions")["coverage"], self.item(doc, "passage-remark-unions")["coverage_note"]
        self.assertProblem(doc, "has links but no key link, so it must carry coverage", "I5")
        doc = load("minimal.json")
        doc["links"] = []
        self.assertValid(doc)

    def test_rule_3_attributed_needs_a_key_unless_partial_only(self):
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["id"] != "definition-1.1/key/Notes.Box"]
        self.item(doc, "definition-1.1")["coverage"] = "support_only"
        self.assertProblem(doc, "has attributed links and no key link", "I5")
        self.item(doc, "definition-1.1")["coverage"] = "partial_only"
        self.assertValid(doc)

    def test_rule_4_formalized_needs_a_key_and_five_classes_exclude_one(self):
        doc = load("mixed.json")
        self.item(doc, "passage-remark-unions")["coverage"] = "formalized"
        self.assertProblem(doc, "item 'passage-remark-unions' is formalized but has no key link", "I5")
        for value in ("partial_only", "support_only", "example_only", "not_formalized", "out_of_scope"):
            doc = load("mixed.json")
            self.item(doc, "definition-1.1")["coverage"] = value
            with self.subTest(coverage=value):
                self.assertProblem(doc, f"item 'definition-1.1' is {value} but has a key link", "I5")

    def test_rule_4_private_only(self):
        doc = load("mixed.json")
        doc["links"].append(link("theorem-1.5", "Notes.Box") | {"provenance": "prov-curation"})
        self.assertProblem(V.canonicalize(doc), "item 'theorem-1.5' is private_only, so a key link names a private "
                                                "declaration; 'Notes.Box' is not private", "I5")
        doc = load("mixed.json")
        doc["links"].append({"cluster": "section-1", "id": "theorem-1.5/key/section-1", "item": "theorem-1.5",
                             "provenance": "prov-curation", "role": "key"})
        self.assertProblem(V.canonicalize(doc), "'theorem-1.5/key/section-1' names a cluster", "I5")
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["item"] != "theorem-1.5"]
        self.assertProblem(doc, "item 'theorem-1.5' is private_only but has no link", "I5")
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["id"] != "theorem-1.5/key/private:Notes.Basic:Notes.Box.volume_aux"]
        self.assertValid(doc)                                           # a helper link is a link

    def test_rule_5_not_formalized_and_out_of_scope_exclude_key_and_attributed(self):
        for value in ("not_formalized", "out_of_scope"):
            doc = load("mixed.json")
            self.item(doc, "lemma-1.4")["coverage"] = value
            self.assertProblem(doc, f"item 'lemma-1.4' is {value} but has an attributed link", "I5")
            doc = load("mixed.json")
            self.item(doc, "passage-remark-unions")["coverage"] = value       # example and support links
            self.assertValid(doc)

    def test_rule_6_coverage_note_needs_coverage(self):
        doc = load("minimal.json")
        doc["items"][0]["coverage_note"] = "A note without a class."
        self.assertEqual(lines(doc), ["$.items[0].coverage_note: coverage_note needs coverage [I5]"])
        doc["items"][0]["coverage"] = "formalized"
        self.assertValid(doc)

    def test_orphaned_links_do_not_count_and_an_example_may_be_key(self):
        doc = load("mixed.json")
        self.item(doc, "definition-1.1")["coverage"] = "formalized"
        self.assertValid(doc)
        doc = load("pdf-region.json")
        link_ = by_id(doc["links"], f"exercise-1.4/example/{PDF_EXAMPLE}")
        link_["role"], link_["id"] = "key", f"exercise-1.4/key/{PDF_EXAMPLE}"
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "item 'exercise-1.4' is example_only but has a key link", "I5")
        self.item(doc, "exercise-1.4")["coverage"] = "formalized"
        self.assertValid(doc)


class TestSourcesAndPages(Case):
    """I6 for sources and pages, and the identity rules the schema states."""

    def test_identity_by_bytes_revision_or_identifiers(self):
        doc = web_doc()
        del doc["sources"][0]["revision"]
        self.assertProblem(doc, "matches none of the allowed alternatives (anyOf)", "SCHEMA")
        doc["sources"][0]["identifiers"] = {"arxiv": "2601.00001v2"}       # identifiers pin pdf and other only
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = load("minimal.json")
        del doc["sources"][0]["sha256"]
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc["sources"][0]["identifiers"] = {"arxiv": "2601.00001v2"}
        self.assertValid(doc)
        doc = media_doc()
        del doc["sources"][1]["sha256"]
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc["sources"][1]["identifiers"] = {"isbn": ["9781234567897"]}        # an e-book by its ISBN
        self.assertValid(doc)
        del doc["sources"][0]["media_type"]
        self.assertProblem(doc, "missing required key 'media_type'", "SCHEMA")

    def test_a_text_layers_extractor_and_version_come_together(self):
        doc = load("pdf-region.json")
        del doc["sources"][0]["text_layer"]["version"]
        self.assertEqual(lines(doc), ["$.sources[0].text_layer: is missing required key 'version' [SCHEMA]"])
        del doc["sources"][0]["text_layer"]["extractor"]
        self.assertValid(doc)

    def test_a_region_needs_the_bytes_a_page_does_not(self):
        doc = load("pdf-region.json")
        source = doc["sources"][0]
        del source["sha256"]
        source["identifiers"] = {"doi": "10.5555/elementary-sets.2026", "isbn": ["9781234567897"]}
        found = V.check(doc).problems
        self.assertEqual({(p.code, p.path) for p in found}, {("I7", "$.locations[0].target.selector[0].refinedBy"),
                                                             ("I7", "$.locations[1].target.selector[0]")})
        self.assertIn("a PdfRegionSelector needs the source's bytes; 'notes-pdf' names none (no sha256 or git_blob)",
                      found[0].message)
        del doc["locations"][0]["target"]["selector"][0]["refinedBy"]
        del doc["locations"][1]["target"]["selector"][0]
        self.assertValid(doc)

    def test_identifiers_xrefs_and_packages_are_shaped(self):
        doc = load("minimal.json")
        for good in ({"doi": "10.123456789/a.b/c(d)"}, {"arxiv": "math.AG/0601001v1"}, {"arxiv": "2601.12345v10"}):
            doc["sources"][0]["identifiers"] = good
            self.assertValid(doc)
        for bad in ({}, {"doi": "10.100/x"}, {"isbn": []}, {"isbn": ["9771234567897"]}, {"arxiv": "2601.00001"},
                    {"arxiv": "Math.AG/0601001v1"}, {"issn": "1234-5678"}, {"doi": "10.1000/x\n"}):
            doc["sources"][0]["identifiers"] = bad
            with self.subTest(identifiers=bad):
                self.assertEqual({(p.code, "identifiers" in p.path) for p in V.check(doc).problems}, {("SCHEMA", True)})
        doc = load("mixed.json")
        for bad in ([{"database": "Stacks", "tag": "0A1B"}], [{"database": "stacks", "tag": "0A 1B"}], [],
                    [{"database": "stacks", "tag": "x"}] * 2):
            doc["items"][0]["xrefs"] = bad
            self.assertEqual(set(codes(doc)), {"SCHEMA"})
        doc = load("mixed.json")
        for bad in ([{"name": "mathlib", "rev": "abc1234"}], [{"name": "", "rev": "0" * 40}], [{"name": "mathlib"}]):
            doc["companion"]["packages"] = bad
            self.assertEqual(codes(doc), ["SCHEMA"])
        doc["companion"]["commit"] = doc["companion"]["commit"][:7]
        self.assertProblem(doc, "$.companion.commit", "SCHEMA")

    def test_i6_page_fields_describe_a_pdf(self):
        doc = media_doc()
        doc["sources"][0]["page_size"] = {"width_pt": 612, "height_pt": 792}
        self.assertProblem(doc, "page_size describe PDF pages; 'lecture' is not a PDF", "I6")
        doc = web_doc()
        doc["sources"][0]["page_size"] = {"width_pt": 612, "height_pt": 792}
        self.assertProblem(doc, "(not)", "SCHEMA")
        doc = load("pdf-region.json")
        doc["sources"][0]["page_sizes"] = [{"first": 3, "last": 5, "width_pt": 500, "height_pt": 700},
                                           {"first": 5, "last": 41, "width_pt": 500, "height_pt": 700}]
        self.assertProblem(doc, "page_sizes ranges overlap", "I6")
        self.assertProblem(doc, "page 41 is past the source's 40 physical pages", "I6")
        doc["sources"][0]["page_sizes"] = [{"first": 5, "last": 3, "width_pt": 500, "height_pt": 700}]
        self.assertProblem(doc, "last (3) is before first (5)", "I6")
        doc = web_doc()
        doc["locations"][0]["pages"] = {"first": 1, "basis": "physical"}
        self.assertProblem(doc, "pages are for a pdf source; 'wiki' is web", "I6")
        doc = load("pdf-region.json")
        doc["sources"][0]["scope"] = "site"
        self.assertProblem(doc, 'must be "web"', "SCHEMA")

    def test_i6_every_physical_page_is_at_least_1_and_within_the_count(self):
        doc = load("pdf-region.json")
        doc["sources"][0]["printed_page_offset"] = -3
        for rec in doc["items"] + doc["links"] + doc["locations"]:
            pages = rec.get("pages")
            if pages and pages["basis"] == "printed":
                pages["basis"] = "physical"
                pages["first"] += 4
                if "last" in pages:
                    pages["last"] += 4
        passage = by_id(doc["items"], "passage-p6-ef94b64f")
        old, passage["id"] = passage["id"], ids.passage_page_id(13, passage["title"])
        for location in doc["locations"]:
            location["items"] = [passage["id"] if i == old else i for i in location["items"]]
        doc = V.canonicalize(doc)
        self.assertValid(doc)
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 1}
        self.assertProblem(doc, "page 1 (printed) is physical page -2; with the source's printed_page_offset every "
                                "physical page is at least 1", "I6")
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 44}
        self.assertProblem(doc, "page 44 (printed) is past the source's 40 physical pages", "I6")
        by_id(doc["items"], "definition-1.1")["pages"] = {"basis": "printed", "first": 5, "last": 4}
        self.assertProblem(doc, "last (4) is before first (5)", "I6")

    def test_i6_a_sites_sha256_is_the_sha256_of_its_page_manifest(self):
        pages = [{"path": "b/index.html", "sha256": "b" * 64}, {"path": "a.html", "sha256": "a" * 64}]
        manifest = f"{'a' * 64}  a.html\n{'b' * 64}  b/index.html\n"
        self.assertEqual(V.site_sha256(pages), hashlib.sha256(manifest.encode("utf-8")).hexdigest())
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        site["page_hashes"][0]["sha256"] = "0" * 64
        self.assertProblem(doc, "a site's sha256 is the sha256 of its page manifest", "I6")
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        site["page_hashes"] = [p for p in site["page_hashes"] if p["path"] != "Notes/Section_2/index.html"]
        site["sha256"] = V.site_sha256(site["page_hashes"])
        self.assertProblem(doc, "'Notes/Section_2/index.html' is not a page in 'literate-site''s page_hashes", "I7")
        del site["page_hashes"]
        self.assertEqual(lines(doc), ["$.sources[1]: is missing required key 'page_hashes' [SCHEMA]"])
        del site["sha256"]
        self.assertValid(doc)                                       # pinned by revision alone

    def test_i6_page_hashes_name_files_in_the_site_path_grammar(self):
        def with_page(path: str) -> dict:
            doc = load("site-pages.json")
            site = by_id(doc["sources"], "literate-site")
            site["page_hashes"] = sorted(site["page_hashes"] + [{"path": path, "sha256": "0" * 64}],
                                         key=lambda p: V.order_key(p["path"]))
            site["sha256"] = V.site_sha256(site["page_hashes"])
            return doc
        for path in ("style.css", "a/b.html", "x.y.z"):
            self.assertValid(with_page(path))
        for path in ("/abs.html", "../up.html", "a/../b.html", "a#frag.html", "a:b.html", "a b.html", "x.html\n"):
            with self.subTest(path=ascii(path)):
                found = V.check(with_page(path)).problems
                self.assertTrue(found and all(p.code == "SCHEMA" and p.path.endswith(".path") for p in found), found)
        found = lines(with_page("Notes/"))
        self.assertRegex(found[0], r"^\$\.sources\[1\]\.page_hashes\[[0-9]\]\.path: 'Notes/' names a directory; a "
                                   r"page_hashes entry names a file \(write its index.html\) \[I6\]$")


class TestSelectors(Case):
    """I7: selector types, grammars, placement, regions and where locations sit."""

    def with_selector(self, sel: dict, name: str = "pdf-region.json", rid: str = "definition-1.1@p007") -> dict:
        doc = load(name)
        location = by_id(doc["locations"], rid)
        location["target"]["selector"] = [sel]
        location.pop("pages", None)
        return doc

    def region(self, page: int = 7, **coords) -> dict:
        return {"type": "PdfRegionSelector", "page": page, "coordinate_space": dict(CS),
                "rect": coords or {"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2}}

    def page(self, n: int, child: dict | None = None) -> dict:
        return frag(vocab.CONFORMS_TO_PDF, f"page={n}", child)

    def test_a_type_and_a_conforms_to_the_sources_family_allows(self):
        self.assertEqual(V.ALLOWED_SELECTORS, {
            "pdf": {"FragmentSelector", "TextQuoteSelector", "PdfRegionSelector"},
            "html": {"FragmentSelector", "TextQuoteSelector", "CssSelector", "SitePageSelector"},
            "text": {"FragmentSelector", "TextQuoteSelector"},
            "generic": {"FragmentSelector", "TextQuoteSelector", "CssSelector"}})
        self.assertProblem(self.with_selector({"type": "CssSelector", "value": "p"}),
                           "CssSelector does not apply to a pdf source", "I7")
        doc = tex_doc()
        doc["locations"][1]["target"]["selector"].append(self.region(1))
        self.assertProblem(doc, "PdfRegionSelector does not apply to a tex source", "I7")
        doc = tex_doc()
        doc["locations"][1]["target"]["selector"][0]["conformsTo"] = vocab.CONFORMS_TO_PDF
        self.assertProblem(doc, "a tex source takes http://tools.ietf.org/rfc/rfc5147", "I7")
        self.assertProblem(self.with_selector(frag(HTML_ID, "x")), "a pdf source takes http://tools.ietf.org/rfc/"
                                                                   "rfc3778 or http://tools.ietf.org/rfc/rfc8118", "I7")
        doc = media_doc()
        doc["locations"][0]["target"]["selector"].append({"type": "CssSelector", "value": "video"})
        self.assertValid(doc)                                       # generic takes CSS
        doc["locations"][2]["target"]["selector"].append({"type": "CssSelector", "value": "p"})
        self.assertEqual(codes(doc), ["I7"])                        # text does not
        for gone in ({"type": "TextPositionSelector", "start": 1, "end": 2}, {"type": "XPathSelector", "value": "//p"},
                     {"type": "RangeSelector", "startSelector": quote("a"), "endSelector": quote("b")}):
            self.assertEqual(codes(self.with_selector(gone)), ["SCHEMA"])
        doc = web_doc()
        doc["locations"][0]["target"]["state"] = {"type": "TimeState", "sourceDate": "2026-09-01T08:00:00Z"}
        self.assertEqual(lines(doc), ["$.locations[0].target.state: is not an allowed key here [SCHEMA]"])

    def test_pdf_fragments(self):
        for value in ("page=7&zoom=100", "page=7&zoom=100,0,0", "page=7&highlight=90,522,140,260",
                      "page=7&highlight=90,90,140,140", "page=7&view=FitH", "nameddest=x"):
            self.assertValid(self.with_selector(self.page(7) | {"value": value}))
        for value, message in (("page=7&zoom=100,0", "zoom= takes 1 or 3 numbers"),
                               ("page=7&highlight=522,90,140,260", "highlight= is left,right,top,bottom with left <= "
                                                                   "right and top <= bottom"),
                               ("page=999&page=7", "page= is given twice; a PDF fragment names each parameter once"),
                               ("page=7#page=9", "page= is given twice"), ("page=41", "page=41 is past the source's 40 "
                                                                                       "physical pages"),
                               ("page=0", "page=0 is not a positive integer"),
                               ("frame=3", "'frame=3' is not an RFC 8118 parameter"),
                               ("#page=7", "write the fragment without its leading #")):
            with self.subTest(value=value):
                self.assertProblem(self.with_selector(self.page(7) | {"value": value}), message, "I7")
        doc = self.with_selector(self.page(7) | {"conformsTo": vocab.CONFORMS_TO_PDF_RFC3778})
        self.assertValid(doc)
        doc = self.with_selector(self.page(41))
        del doc["sources"][0]["physical_page_count"]
        self.assertValid(doc)                                       # bounded only by a given count

    def test_rfc5147_text_fragments(self):
        doc = tex_doc()
        sel = doc["locations"][1]["target"]["selector"][0]
        for value in ("line=41,47", "line=41", "char=0,10", "line=,47", "line=41,", "line=41,47;length=10,UTF-8",
                      "line=41,47;md5=0123456789ABCDEF0123456789abcdef"):
            sel["value"] = value
            self.assertValid(doc)
        sel["value"] = "line=47,41"
        self.assertEqual(lines(doc), ["$.locations[1].target.selector[0].value: RFC 5147 range 47,41 is empty or out of "
                                      "order; lines L1..L2 are written line=(L1-1),L2 [I7]"])
        for value, message in (("line=,", "an RFC 5147 range needs at least one end"),
                               ("line=41,47;md5=0123", "is not an RFC 5147 fragment"),
                               ("lines=1,2", "is not an RFC 5147 fragment")):
            sel["value"] = value
            self.assertProblem(doc, message, "I7")

    def test_html_ids_and_media_fragments(self):
        doc = load("site-pages.json")
        by_id(doc["locations"], "Notes.sum_le@site")["target"]["selector"][0]["refinedBy"]["value"] = "two words"
        self.assertProblem(doc, "is not an HTML element id", "I7")
        doc = media_doc()
        sel = doc["locations"][0]["target"]["selector"][0]
        for value in ("t=30,60", "t=npt:10,20", "t=,20", "t=0:02:00,121.5", "xywh=0,0,10,10", "track=audio&t=5"):
            sel["value"] = value
            self.assertValid(doc)
        for value, message in (("t=60,30", "the start must be before the end"),
                               ("t=npt:1:30", "is not a Media Fragments t= value"),
                               ("t=00:61", "minutes and seconds run from 00 to 59"),
                               ("xywh=0,0,0,10", "width and height must be positive"),
                               ("xywh=percent:50,0,60,10", "a percent: region must stay within 100"),
                               ("xywh=1.5,0,10,10", "is not a Media Fragments xywh= value"),
                               ("id=a b", "id= takes a percent-encoded name")):
            sel["value"] = value
            self.assertProblem(doc, message, "I7")
        for value in ("t=1&t=2", "frame=3&t=1"):
            sel["value"] = value
            self.assertValid(doc)
            self.assertEqual(warnings(doc)[0], ("W-MEDIA", "$.locations[0].target.selector[0].value"))

    def test_placement(self):
        self.assertValid(self.with_selector(self.region()))
        self.assertValid(self.with_selector(self.page(7, self.region())))
        self.assertValid(self.with_selector(self.page(7, self.page(7, quote("q")))))
        for sel, path, message in (
                (self.page(7, quote("q", self.region())), ".refinedBy.refinedBy",
                 "a PdfRegionSelector is a top-level alternative or the direct refinement of a PDF page= fragment"),
                (self.page(7, self.region(8)), ".refinedBy.page", "page 8 disagrees with the refined page=7"),
                (self.page(7, self.page(8)), ".refinedBy.value", "page=8 inside page=7"),
                (self.page(7, quote("q", self.page(8))), ".refinedBy.refinedBy.value", "page=8 inside page=7"),
                (frag(vocab.CONFORMS_TO_PDF, "nameddest=d", quote("q")), ".value",
                 "a PDF fragment that is refined must name its page=")):
            with self.subTest(message=message):
                self.assertEqual(lines(self.with_selector(sel)),
                                 [f"$.locations[0].target.selector[0]{path}: {message} [I7]"])
        chain = quote("q")
        for _ in range(6):
            chain = quote("q", chain)
        self.assertValid(self.with_selector(self.page(7, chain)))           # 8 selectors
        self.assertEqual(lines(self.with_selector(self.page(7, quote("q", chain)))),
                         ["$.locations[0].target.selector[0]" + ".refinedBy" * 8 + ": a refinedBy chain is at most 8 "
                          "selectors deep [I7]"])

    def test_site_pages(self):
        doc = load("site-pages.json")
        location = by_id(doc["locations"], "Notes.sum_le@site")
        location["target"]["selector"] = [location["target"]["selector"][0]["refinedBy"]]
        self.assertProblem(doc, "is a site: each alternative names its page with a SitePageSelector", "I7")
        doc = load("site-pages.json")
        by_id(doc["locations"], "Notes.sum_le@site")["target"]["selector"][0]["refinedBy"] = {
            "type": "SitePageSelector", "path": "a/"}
        self.assertProblem(doc, "a SitePageSelector is a top-level alternative, never a refinement", "I7")
        doc = web_doc()
        doc["locations"][0]["target"]["selector"].append({"type": "SitePageSelector", "path": "index.html"})
        self.assertProblem(doc, "a SitePageSelector names a page of a site; 'wiki' is one page", "I7")

    def test_regions(self):
        self.assertProblem(self.with_selector(self.region(x0=0.1, y0=0.1, x1=1.5, y1=0.2)),
                           "coordinates must lie in [0, 1] for units normalized", "I7")
        self.assertProblem(self.with_selector(self.region(x0=0.2, y0=0.1, x1=0.1, y1=0.2)),
                           "a rect needs x0 < x1 and y0 < y1", "I7")
        self.assertProblem(self.with_selector(self.region(41)), "page 41 is past the source's 40 physical pages", "I7")
        sel = self.region()
        sel["coordinate_space"]["origin"] = "bottom_left"
        self.assertProblem(self.with_selector(sel), "top_left goes with y_axis down, bottom_left with up", "I7")
        sel = self.region(x0=90, y0=262, x1=522, y1=300)
        sel["coordinate_space"]["units"] = "pt"
        self.assertValid(self.with_selector(sel))
        sel["rect"]["x1"] = 1000
        doc = self.with_selector(sel)
        self.assertProblem(doc, "the rect leaves the 612 x 792 pt page", "I7")
        doc["sources"][0]["page_sizes"] = [{"first": 7, "last": 7, "width_pt": 1224, "height_pt": 792}]
        self.assertValid(doc)
        sel["rect"]["x0"] = -1
        self.assertProblem(self.with_selector(sel), "coordinates must be >= 0 for units pt", "I7")

    def test_quads(self):
        def quad(*points) -> dict:
            corners = {}
            for i, (x, y) in enumerate(points):
                corners[f"x{i}"], corners[f"y{i}"] = x, y
            return {"type": "PdfRegionSelector", "page": 7, "coordinate_space": dict(CS), "quads": [corners]}
        self.assertValid(self.with_selector(quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2))))
        self.assertValid(self.with_selector(quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.1))))   # a triangle
        path = "$.locations[0].target.selector[0].quads[0]"
        self.assertEqual(lines(self.with_selector(quad((0.1, 0.1), (0.2, 0.1), (0.2, 0.1), (0.1, 0.1)))),
                         [f"{path}: a quad needs at least three distinct corners [I7]"])
        self.assertEqual(lines(self.with_selector(quad((0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.4, 0.4)))),
                         [f"{path}: a quad's corners must not all lie on one line (it would enclose no area) [I7]"])
        sel = quad((10, 10), (700, 10), (700, 700), (10, 700))
        sel["coordinate_space"]["units"] = "pt"
        self.assertEqual(lines(self.with_selector(sel)), [f"{path}: the quad leaves the 612 x 792 pt page [I7]"])

    def test_where_locations_sit(self):
        doc = load("mixed.json")
        by_id(doc["locations"], "definition-1.1@p007")["items"] = ["definition-1.1", "passage-bcffcbba"]
        self.assertProblem(doc, "a location shows items of its own source 'notes-pdf'", "I7")
        doc = load("pdf-region.json")
        del by_id(doc["links"], "lemma-1.2/helper/private:Notes.Basic:Notes.Box.volume_aux")["locations"]
        self.assertProblem(doc, "a location shows at least one item, anchors a declaration, or is named by a link",
                           "I7")
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["pages"] = {"first": 8, "basis": "physical"}
        self.assertProblem(doc, "the selectors name physical page(s) [7], outside 8..8", "I7")
        doc = load("mixed.json")
        doc["links"].append(link("passage-bcffcbba", "Notes.Box", "support", locations=["definition-1.1@p007"])
                            | {"provenance": "prov-curation"})
        self.assertProblem(V.canonicalize(doc), "not on the item's source 'notes-errata'", "I7")

    def test_an_anchor_shows_the_declarations_own_text(self):
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box")["anchors"] = ["definition-1.1@p007"]
        self.assertProblem(doc, "an anchor shows the declaration's own text, on a lean, web, or other text/html "
                                "source; 'notes-pdf' is pdf", "I7")
        doc = media_doc()
        doc["declarations"][0]["anchors"] = ["theorem-3@md"]
        self.assertValid(doc)                                       # Markdown is text
        doc["declarations"][0]["anchors"] = ["passage-sketch@t"]
        self.assertProblem(doc, "is other (video/mp4)", "I7")
        doc = tex_doc()
        doc["declarations"][0]["anchors"] = ["theorem-1.3@tex"]
        self.assertProblem(doc, "'blueprint' is tex", "I7")


class TestDeclarations(Case):
    """I8: ids by id_source, flags, signatures and their hashes, members, ordinals."""

    def test_the_hash_id_its_signature_and_statement_sha256_agree(self):
        doc = load("pdf-region.json")
        decl_ = by_id(doc["declarations"], PDF_EXAMPLE)
        self.assertEqual(decl_["id"], ids.anonymous_id("example", decl_["statement_sha256"]))
        self.assertEqual(decl_["statement_sha256"], ids.statement_sha256(decl_["signature"]))
        signature = decl_["signature"]
        decl_["signature"] += " "
        self.assertProblem(doc, "must be normalised: comments removed, each run of whitespace one space", "I8")
        decl_["signature"] = signature + " -- a comment"
        self.assertProblem(doc, "must be normalised", "I8")
        decl_["signature"] = signature + " extra"
        self.assertProblem(doc, "its sha256 is not statement_sha256 (the hash of the signature's hash form)", "I8")
        decl_["signature"] = signature.replace(" : ", ":")              # another spacing: the same hash form
        self.assertValid(doc)
        decl_["statement_sha256"] = "0" * 64
        del decl_["signature"]
        self.assertProblem(doc, "the id's hash is not the first 12 digits of statement_sha256", "I8")
        doc = load("minimal.json")                                       # a named declaration may carry both
        named = doc["declarations"][0]
        named["signature"] = "theorem Notes.Box.volume_nonneg (b : Box) : 0 <= b.volume"
        named["statement_sha256"] = ids.statement_sha256(named["signature"])
        self.assertValid(doc)

    def test_the_id_grammar_by_id_source(self):
        doc = load("pdf-region.json")
        by_id(doc["declarations"], PDF_EXAMPLE)["kind"] = "instance"
        self.assertProblem(doc, "the id says example but kind is instance", "I8")
        doc = json.loads((EXAMPLES / "mixed.json").read_text(encoding="utf-8")
                         .replace("example:Unions-of-boxes-are-elementary", "example:0123456789ab"))
        self.assertProblem(V.canonicalize(doc), "a slug of 12 hex digits is reserved for statement hashes", "I8")
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "private:Notes.Basic:Notes.Box.volume_aux")["name"] = "Notes.Box.other"
        self.assertProblem(doc, "a private declaration's id is private:<module>:<name>, here", "I8")
        doc = load("pdf-region.json")
        decl_ = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
        for name, ok in (("Notes.Box:volume_nonneg", True), ("private:Notes.Box", False)):
            decl_["id"] = decl_["name"] = name
            by_id(doc["links"], "lemma-1.2/key/Notes.Box.volume_nonneg")["declaration"] = name
            self.assertEqual(not codes(V.canonicalize(doc)), ok)
        self.assertProblem(V.canonicalize(doc), "is not a fully qualified Lean name", "I8")
        doc = load("minimal.json")
        doc["declarations"][0]["name"] = "Notes.Other"
        self.assertProblem(doc, "a name-identified declaration's id is its name", "I8")

    def test_the_flags_agree_with_id_source(self):
        for rid, field, value, message in (
                ("Notes.Box", "private", True, "a private or anonymous declaration is not identified by name"),
                (PDF_EXAMPLE, "name", "Notes.ex", "an anonymous declaration has no name"),
                (PDF_EXAMPLE, "anonymous", False, "id_source statement_hash is for anonymous declarations"),
                ("private:Notes.Basic:Notes.Box.volume_aux", "private", False,
                 "id_source private needs private true and anonymous false"),
                ("Notes.Box", "id_source", "declared", "id_source declared is for anonymous declarations"),
                ("Notes.Box.lower", "parent", "Notes.Box.lower", "a declaration is not its own parent")):
            doc = load("pdf-region.json")
            by_id(doc["declarations"], rid)[field] = value
            with self.subTest(message=message):
                self.assertProblem(doc, message, "I8")
        doc = load("minimal.json")
        doc["declarations"][0]["kind"] = "example"
        self.assertEqual(lines(doc), ["$.declarations[0].anonymous: an example is always anonymous (a named example is "
                                      "refused) [I8]"])
        doc = load("mixed.json")
        unlocated = by_id(doc["declarations"], "example:Unions-of-boxes-are-elementary")
        unlocated["line"] = 3
        self.assertProblem(doc, "(not)", "SCHEMA")

    def with_member(self, kind: str, parent_kind: str, **more) -> tuple[dict, str]:
        """minimal.json and a member ``Notes.Color.red`` of ``Notes.Color``, the last declaration."""
        doc = load("minimal.json")
        doc["declarations"] += [decl("Notes.Color", parent_kind),
                                decl("Notes.Color.red", kind, **({"namespace": "Notes.Color", "parent": "Notes.Color"}
                                                                  | more))]
        return V.canonicalize(doc), "$.declarations[2]"

    def test_members_and_their_parents(self):
        for kind, parents in vocab.ANNOTATION_MEMBER_PARENT_KINDS.items():
            for parent_kind in ("inductive", "structure", "class"):
                doc, path = self.with_member(kind, parent_kind)
                with self.subTest(kind=kind, parent=parent_kind):
                    if parent_kind in parents:
                        self.assertValid(doc)
                    else:
                        self.assertEqual(lines(doc), [f"{path}.parent: a {kind}'s parent is a structure or class, not "
                                                      f"an inductive [I3]"])
            doc, path = self.with_member(kind, "theorem")
            self.assertEqual(codes(doc), ["I3"])
            del doc["declarations"][2]["parent"]
            self.assertEqual(lines(doc), [f"{path}: is missing required key 'parent' [SCHEMA]"])
        doc, path = self.with_member("theorem", "structure")
        self.assertProblem(doc, "(not)", "SCHEMA")                      # only a member has a parent

    def test_a_members_full_name_is_its_parents_and_its_own(self):
        doc, path = self.with_member("field", "structure", namespace="Notes")
        self.assertEqual(lines(doc), [f"{path}.namespace: a field's namespace is its parent's full name (its name), "
                                      f"'Notes.Color' [I8]"])
        doc, path = self.with_member("field", "structure")
        doc["declarations"][2]["id"] = doc["declarations"][2]["name"] = "Notes.Color.red.dark"
        self.assertEqual(lines(doc), [f"{path}.name: a field's full name is its namespace, a dot and its own name [I8]"])
        del doc["declarations"][2]["namespace"]
        self.assertEqual(lines(doc), [f"{path}.name: a field's full name is its parent's full name ('Notes.Color'), "
                                      f"a dot and its own name [I8]"])
        doc, path = self.with_member("field", "structure")
        del doc["declarations"][2]["name"], doc["declarations"][2]["namespace"]
        self.assertValid(doc)                                           # the full name is read from the id
        doc["declarations"][2]["id"] = "Notes.Color.red.dark"
        self.assertEqual(lines(doc), [f"{path}.id: a field's full name is its parent's full name ('Notes.Color'), a "
                                      f"dot and its own name [I8]"])
        doc = web_doc()
        by_id(doc["declarations"], "Ideal.IsPrime.ne_top'")["namespace"] = "Ideal"
        self.assertProblem(doc, "a projection's namespace is its parent's full name (its name), 'Ideal.IsPrime'", "I8")

    def test_an_ordinal_needs_its_latest_record_to_name_the_declarations_file(self):
        doc = load("mixed.json")
        doc["changelog"] = [c for c in doc["changelog"] if c["event"] != "ordinal_assigned"]
        self.assertProblem(doc, "carries an ordinal, which is positional", "I8")
        rid = ORDINAL + "~2"

        def moved(first_at: str, second_at: str) -> dict:
            """~2 now sits in Notes/Unions.lean; a record at ``second_at`` says so, one at ``first_at`` does not."""
            doc = load("mixed.json")
            by_id(doc["declarations"], rid).update(file="Notes/Unions.lean", module="Notes.Unions")
            record = next(c for c in doc["changelog"] if c["subject"] == rid)
            record["at"] = first_at
            doc["changelog"].append(dict(record, at=second_at, file="Notes/Unions.lean", id="zz-ordinal"))
            return V.canonicalize(doc)
        self.assertProblem(moved("2026-09-01", "2026-08-01"), f"the latest ordinal_assigned record gives {rid!r} to a "
                                                              f"declaration in 'Notes/Basic.lean', and it is in "
                                                              f"'Notes/Unions.lean'", "I8")
        base = "2026-09-05T00:00:00."
        for first, second in (("2026-09-01", "2026-09-05"), (base + "0000001Z", base + "0000009Z"),
                              (base + "1234567890123Z", base + "1234567890124Z")):
            self.assertValid(moved(first, second))                      # later, at full precision
        for first, second in (("2026-09-05", "2026-09-05T00:00:00Z"), (base + "5Z", base + "50Z")):
            self.assertProblem(moved(first, second), "name different files", "I8")     # the same instant


class TestDatesAndTheChangelog(Case):
    """I9: dates and timestamps, and the changelog's rules."""

    def test_every_date_and_timestamp_is_real(self):
        chains = set(V._date_chains(schema()))
        self.assertTrue({("companion", "generated_at"), ("sources", "*", "retrieved_at"), ("provenance", "*", "at"),
                         ("locations", "*", "signoff", "at"), ("changelog", "*", "at")} <= chains)
        for path, mutate in (
                ("$.provenance[0].at", lambda d: d["provenance"][0].__setitem__("at", "2026-02-30")),
                ("$.locations[0].signoff.at", lambda d: d["locations"][0]["signoff"].__setitem__("at", "2026-13-45")),
                ("$.companion.generated_at", lambda d: d["companion"].__setitem__("generated_at", "2026-02-30T09:00:00Z")),
                ("$.sources[0].retrieved_at", lambda d: d["sources"][0].__setitem__("retrieved_at",
                                                                                    "2026-09-31T00:00:00Z"))):
            doc = load("pdf-region.json")
            mutate(doc)
            (line,) = lines(doc)
            self.assertRegex(line, rf"^{re.escape(path)}: '.*' is not a calendar date or UTC instant \[I9\]$")
        doc = load("mixed.json")
        for at, ok in (("2016-12-31T23:59:60Z", True), ("2016-12-31T23:59:60.5Z", True), ("2024-02-29", True),
                       ("2016-12-31T23:58:60Z", False), ("2016-12-31T24:00:00Z", False), ("2026-09-05T25:00:00Z", False),
                       ("0000-01-01", False), ("2016-12-31T23:59:60", False)):
            doc["changelog"][3]["at"] = at
            with self.subTest(at=at):
                self.assertEqual(V.check(doc).ok, ok, lines(doc))
        self.assertLess(V._parse_at("2026-09-05T00:00:00.09Z"), V._parse_at("2026-09-05T00:00:00.1Z"))
        self.assertEqual(V._parse_at("2026-09-05T00:00:00.10Z"), V._parse_at("2026-09-05T00:00:00.1Z"))
        self.assertLess(V._parse_at("2016-12-31T23:59:60Z"), V._parse_at("2017-01-01"))

    def test_a_retired_or_renamed_id_is_never_live_again(self):
        doc = load("mixed.json")
        doc["declarations"].append({"anonymous": True, "file": "Notes/Exercises.lean", "id": "example:f254071ef195",
                                    "id_source": "statement_hash", "kind": "example", "module": "Notes.Exercises",
                                    "private": False, "statement_sha256": "f254071ef195" + "0" * 52})
        self.assertProblem(V.canonicalize(doc), "is retired, so it may not be used again", "I9")
        doc = load("mixed.json")
        change = next(c for c in doc["changelog"] if c["event"] == "renamed")
        change["subject"] = "Notes.Box"
        self.assertProblem(doc, "'Notes.Box' is renamed, so it may not be used again", "I9")
        change["subject"] = change["successor"]
        self.assertProblem(doc, "the successor differs from the subject", "I9")
        change["successor"] = "Notes.Gone"
        self.assertProblem(doc, "'Notes.Gone' is not a live declaration id", "I9")

    def test_restated_names_a_live_or_later_retired_non_hash_declaration(self):
        restated = {"at": "2026-09-25", "event": "restated", "id": "zz-restated", "new_statement_sha256": "1" * 64,
                    "old_statement_sha256": "0" * 64, "subject_kind": "declaration"}
        retired = {"event": "retired", "id": "zz-retired", "reason": "removed", "subject": "Notes.Gone",
                   "subject_kind": "declaration"}
        for subject, extra, message in (
                (ORDINAL, (), f"{ORDINAL!r} is a statement-hash id, which changes with its statement"),
                ("Notes.Gone", (), "'Notes.Gone' is not a live declaration id, and no later changelog entry"),
                ("Notes.Gone", (dict(retired, at="2026-09-25"),), "no later changelog entry retires or renames it"),
                ("Notes.Gone", (dict(retired, at="2026-09-25T00:00:00Z"),), "no later changelog entry"),
                ("private:Notes.Basic:Notes.Box.volume_aux", (), None),
                ("Notes.Gone", (dict(retired, at="2026-09-25T00:00:00.000000001Z"),), None)):
            doc = load("mixed.json")
            doc["changelog"] += [dict(restated, subject=subject), *extra]
            with self.subTest(subject=subject, extra=extra):
                if message is None:
                    self.assertValid(V.canonicalize(doc))
                else:
                    self.assertProblem(V.canonicalize(doc), message, "I9")
        doc = load("mixed.json")
        doc["changelog"].append(dict(restated, subject="Notes.Box", subject_kind="item"))
        self.assertProblem(V.canonicalize(doc), "restated records a declaration whose statement changed", "I9")

    def test_ordinal_assigned_names_a_tilde_id_live_or_retired_no_earlier(self):
        doc = load("mixed.json")
        doc["changelog"] = [c for c in doc["changelog"] if c["id"] != "2026-09-04/retired/example:7c01be3bbde5~3"]
        self.assertProblem(doc, "is not a live declaration id, and no later changelog entry retires or renames it",
                           "I9")
        doc = load("mixed.json")
        by_id(doc["changelog"], "2026-09-04/retired/example:7c01be3bbde5~3")["at"] = "2026-08-01"
        self.assertProblem(doc, "no later changelog entry retires or renames it", "I9")
        doc = load("mixed.json")
        by_id(doc["changelog"], "2026-09-01/ordinal/example:7c01be3bbde5~2")["subject"] = ORDINAL
        self.assertProblem(V.canonicalize(doc), "ordinal_assigned records a declaration's <keyword>:<12 hex>~k id", "I9")


# --- warnings, versions and the external-urls lint

class TestWarningsAndVersions(Case):

    def test_unknown_conforms_to_relation_and_xref_database_warn(self):
        doc = tex_doc()
        sel = doc["locations"][1]["target"]["selector"][0]
        sel["conformsTo"], sel["value"] = "https://example.org/some-grammar", "anything at all"
        self.assertValid(doc)
        self.assertIn("is not an IRI this checker knows", V.check(doc).warnings[0].message)
        del sel["conformsTo"]
        self.assertEqual(warnings(doc), [("W-CONFORMS", "$.locations[1].target.selector[0].conformsTo")])
        self.assertIn("absent (W3C: SHOULD have one)", V.check(doc).warnings[0].message)
        doc = web_doc()
        doc["links"][0]["relation"] = "analogy"
        self.assertValid(doc)
        self.assertEqual(warnings(doc), [("W-RELATION", "$.links[0].relation")])
        doc = load("mixed.json")
        doc["items"][0]["xrefs"].append({"database": "zbmath", "tag": "123.45678"})
        self.assertValid(doc)
        self.assertEqual(warnings(doc), [("W-XREF", "$.items[0].xrefs[2].database")])
        self.assertIn("'zbmath' is outside the documented core (kerodon, lmfdb, stacks, wikidata)",
                      V.check(doc).warnings[0].message)

    def test_the_schema_of_the_declared_minor_is_used(self):
        doc = load("minimal.json")
        self.assertEqual(V.select_schema(doc).path, V.schema_path(1, 0))
        self.assertFalse(V.select_schema(doc).forward)
        for bad in ("1.0\n", 1):
            doc["schema_version"] = bad
            self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("SCHEMA", "$.schema_version")])
        doc["schema_version"] = "2.0"
        self.assertEqual(lines(doc), ["$.schema_version: no schema for major version 2 (this checker has 1) [SCHEMA]"])
        doc = web_doc()
        doc["profiles"]["site"] = "2.0"
        self.assertEqual(lines(doc), ["$.profiles.site: no schema for site profile major version 2 (this checker has "
                                      "1.0) [SCHEMA]"])
        doc = load("minimal.json")
        doc["schema"] = "other/annotations"
        self.assertEqual(lines(doc), ['$.schema: must be "formal-companion/annotations" [SCHEMA]'])

    def test_a_newer_minor_is_checked_in_forward_mode(self):
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.9"
        doc["items"][0]["future_field"] = {"anything": [1, 2]}
        doc["future_array"] = []
        report = V.check(doc)
        self.assertTrue(report.ok, report.problems)
        self.assertEqual([(w.code, w.path) for w in report.warnings],
                         [("W-NEWER", "$.schema_version"), ("W-NEWER", "$.items[0].future_field"),
                          ("W-NEWER", "$.future_array")])
        self.assertIn("checked against 1.0, keys added since are ignored", report.warnings[0].message)
        doc["links"][0]["declaration"] = "Notes.Nowhere"                    # the invariants still run
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("I3", "$.links[0].declaration")])
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.9"
        doc["items"][0]["coverage"] = "future_class"                        # an unknown value still fails
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = web_doc()
        doc["profiles"]["site"] = "1.4"
        doc["destinations"][0]["future_field"] = True
        doc["profiles"]["future"] = "1.0"
        self.assertTrue(V.check(doc).ok)
        self.assertEqual(set(warnings(doc)), {("W-NEWER", "$.profiles.site"), ("W-NEWER", "$.destinations[0].future_field"),
                                              ("W-NEWER", "$.profiles.future")})
        del doc["profiles"]["future"]
        doc["profiles"]["site"] = "1.0"
        self.assertEqual(lines(doc), ["$.destinations[0].future_field: is not an allowed key here [SCHEMA]"])

    def test_dollar_schema_should_be_the_declared_minors_id(self):
        doc = load("minimal.json")
        doc["$schema"] = SCHEMA_ID
        self.assertEqual(warnings(doc), [])
        doc["$schema"] = "https://example.org/other-schema.json"
        self.assertTrue(V.check(doc).ok)
        self.assertEqual(warnings(doc), [("W-SCHEMA-ID", "$.$schema")])
        self.assertIn(f"is not the $id of the declared schema 1.0, {SCHEMA_ID}", V.check(doc).warnings[0].message)
        doc["schema_version"], doc["$schema"] = "1.3", V.schema_id(1, 3)
        self.assertEqual([w for w, _p in warnings(doc)], ["W-NEWER"])
        doc["$schema"] = 3
        self.assertEqual(codes(doc), ["SCHEMA"])


class TestCodes(unittest.TestCase):

    def test_the_checker_emits_exactly_the_codes_of_the_specification(self):
        """IJSON, SCHEMA, I1 to I14 but the retired I10, L1 and six warnings; each has its tests above."""
        code = (PACKAGE / "validate.py").read_text(encoding="utf-8")
        emitted = set(re.findall(r'(?:self\.(?:fail|warn)|Problem)\("([A-Z0-9-]+)"', code))
        self.assertEqual(emitted, {"IJSON", "SCHEMA", "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9", "I11",
                                   "I12", "I13", "I14", "L1", "W-CONFORMS", "W-MEDIA", "W-RELATION", "W-XREF",
                                   "W-NEWER", "W-SCHEMA-ID"})

    def test_the_specification_states_every_code_and_the_profile_table(self):
        text = (ROOT / "docs" / "annotations.md").read_text(encoding="utf-8")
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14):
            self.assertIn(f"| I{n} |", text)
        self.assertNotIn("| I10 |", text)
        for code in ("IJSON", "SCHEMA", "L1", "W-CONFORMS", "W-MEDIA", "W-RELATION", "W-XREF", "W-NEWER", "W-SCHEMA-ID"):
            self.assertIn(f"`{code}`", text)
        for name, owned in V.PROFILES.items():
            (row,) = [line for line in text.splitlines() if line.startswith(f"| `{name}` |")]
            for key in owned["arrays"] + owned["fields"]:
                head, _, field = key.partition(".")
                self.assertIn(f"`{head}[].{field}`" if field and head != "companion" else f"`{key}`", row)
        for block in re.findall(r"```json\n(.*?)```", text, re.S):
            json.loads(block)


class TestTheExternalUrlsLint(Case):
    """L1: opt-in; no URL outside the exempt paths, in values, keys and x_ values at any depth."""

    def lint(self, doc: dict) -> list[str]:
        return lines(doc, lints=("external-urls",))

    def test_it_runs_only_when_asked(self):
        doc = load("mixed.json")
        self.assertEqual(self.lint(doc), [])
        doc["provenance"][0]["note"] = "see https://example.org/run"
        by_id(doc["items"], "passage-boxes-motivation")["title"] = "see HTTP://EXAMPLE.ORG"
        self.assertValid(doc)
        found = self.lint(doc)
        self.assertEqual(len(found), 2)
        self.assertIn("$.items[3].title: contains 'HTTP://EXAMPLE.ORG'", found[0])
        self.assertEqual(found[1], "$.provenance[0].note: contains 'https://example.org/run', a URL-like reference; "
                                   + V._L1_RULE + " [L1]")
        with self.assertRaises(ValueError):
            V.check(doc, lints=("no-such-lint",))
        self.assertEqual(V.LINTS, frozenset({"external-urls"}))

    def test_what_is_url_like(self):
        doc = load("pdf-region.json")
        for value, flagged in (("ftp://files.example.org/x", True), ("//evil.example/x", True),
                               ("see //evil.example/x", False), ("javascript:alert(1)", True), ("data:text/html,hi", True),
                               ("mailto:a@example.org", True), ("file:///etc/passwd", True), ("see git+ssh://h/r", True),
                               ("https:evil.example", False), ("2 // 3", False), ("JavaScript:void(0)", True),
                               ("data-set: 3", False), ("see mailto:a@b", False)):
            doc["x_meta"] = value
            with self.subTest(value=value):
                self.assertEqual(bool(self.lint(doc)), flagged)

    def test_keys_and_x_values_at_any_depth(self):
        doc = load("mixed.json")
        doc["x_elsewhere"] = [{"deep": [["https://example.org/"]]}]
        self.assertIn("$.x_elsewhere[0].deep[0][0]: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["companion"]["x_build"]["log"] = "http://example.org/build"
        self.assertIn("$.companion.x_build.log: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["x_meta"] = {"https://evil.example/": 1}
        self.assertTrue(self.lint(doc)[0].startswith('$.x_meta["https://evil.example/"]: the key '
                                                     "'https://evil.example/' contains "))

    def test_the_exemptions_are_by_path_not_by_key_name(self):
        doc = load("mixed.json")
        by_id(doc["items"], "passage-bcffcbba")["quote"]["prefix"] = "from http://notes.example.org: "
        by_id(doc["locations"], "passage-remark-unions@p007")["target"]["selector"][1]["refinedBy"]["suffix"] = \
            " at https://example.org/x"
        doc["$schema"] = SCHEMA_ID
        self.assertValid(doc)
        self.assertEqual(self.lint(doc), [])
        for x_meta in ({"$schema": "https://example.org/x"}, {"conformsTo": "https://evil.example/t"},
                       {"type": "TextQuoteSelector", "exact": "https://evil.example/a"},
                       {"quote": {"exact": "https://evil.example"}}, {"url": "https://evil.example"},
                       {"href": "https://evil.example"}):
            doc["x_meta"] = x_meta
            with self.subTest(x_meta=x_meta):
                self.assertEqual(len(self.lint(doc)), 1)
        doc = load("mixed.json")
        doc["companion"]["repo"] = "https://git.example.org/x/y"
        self.assertProblem(doc, "$.companion.repo", "SCHEMA")                # host/org/name, no scheme


# --- the command line

class Temp(Case):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, content: str | bytes | dict) -> Path:
        if isinstance(content, dict):
            content = V.canonical_dumps(V.canonicalize(content))
        path = self.tmp / name
        path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
        return path


class TestTheCli(Temp):

    def test_every_document_is_checked_and_2_wins_over_1(self):
        good, bad = EXAMPLES / "pdf-region.json", EXAMPLES / "invalid-dangling-reference.json"
        unreadable, missing = self.write("dup.json", '{"a": 1, "a": 2}'), self.tmp / "missing.json"
        status, out, err = run_cli(str(unreadable), str(bad), str(missing), str(good))
        self.assertEqual(status, 2)
        self.assertIn(f"{unreadable}: cannot read: duplicate key 'a' in one object", err)
        self.assertIn(f"{missing}: cannot read: ", err)
        self.assertIn(f"{bad}: {load(bad.name)['x_expected_error']}\n", out)
        self.assertIn(f"{good}: ok (1 sources, 2 provenance, 4 items, 5 declarations, 6 locations, 4 links)\n", out)
        self.assertEqual(run_cli(str(bad), str(good))[0], 1)
        self.assertEqual(run_cli(str(good), str(good))[0], 0)
        status, out, err = run_cli(str(self.write("list.json", "[1, 2]")))
        self.assertEqual(status, 1)
        self.assertIn(": $: must be of type object [SCHEMA]", out)

    def test_unreadable_documents_exit_2_with_a_message(self):
        for label, body in (("1e400", '{"x_a": 1e400}'), ("deep", "[" * 100000 + "]" * 100000),
                            ("digits", '{"x_a": ' + "1" * 5000 + "}"), ("nan", '{"x_a": NaN}'),
                            ("surrogate", '{"x_a": "' + JSON_LONE_SURROGATE + '"}'), ("bom", b"\xef\xbb\xbf{}"),
                            ("utf-16", '{"a": 1}'.encode("utf-16")), ("big int", '{"x_a": 9007199254740992}')):
            path = self.write(f"{label}.json", body)
            with self.subTest(label=label):
                status, out, err = run_cli(str(path))
                self.assertEqual((status, out), (2, ""))
                self.assertTrue(err.startswith(f"{path}: cannot read: "), err)
                self.assertEqual(run_cli(str(path), "--canonical")[0], 2)
                self.assertEqual(run_cli(str(path), "--print-canonical")[0], 2)

    def test_warnings_and_format_json(self):
        doc = media_doc()
        good, bad = self.write("media.json", doc), EXAMPLES / "invalid-dangling-reference.json"
        status, out, err = run_cli(str(good))
        self.assertEqual((status, err), (0, ""))
        self.assertRegex(out, r"^.*: warning: \$\.locations\[1\]\.target\.selector\[0\]\.conformsTo: .* \[W-CONFORMS\]\n"
                              r".*: ok \(3 sources, 1 provenance, 3 items, 1 declarations, 3 locations, 2 links\)\n$")
        unreadable = self.write("nan.json", '{"x": NaN}')
        status, out, err = run_cli(str(good), str(bad), str(unreadable), "--format", "json")
        self.assertEqual((status, err), (2, ""))
        records = [json.loads(line) for line in out.splitlines()]
        self.assertEqual([(r["file"], r["ok"]) for r in records], [(str(good), True), (str(bad), False),
                                                                     (str(unreadable), False)])
        self.assertEqual(records[0]["warnings"][0]["code"], "W-CONFORMS")
        self.assertEqual(set(records[0]), {"file", "ok", "problems", "warnings"})
        self.assertEqual(records[1]["problems"], [{"code": "I3", "path": "$.links[2].declaration",
                                                   "message": "'Notes.Box.volume_pos' is not an id in declarations[]"}])
        self.assertEqual(records[2]["problems"][0]["code"], "IJSON")

    def test_canonical_compares_the_exact_bytes(self):
        text = (EXAMPLES / "pdf-region.json").read_text(encoding="utf-8")
        for label, body in (("crlf", text.replace("\n", "\r\n")), ("cr", text.replace("\n", "\r")),
                            ("no final newline", text.rstrip("\n")), ("two final newlines", text + "\n"),
                            ("indented", json.dumps(json.loads(text), indent=4, ensure_ascii=False))):
            path = self.write(f"{label}.json", body)
            with self.subTest(label=label):
                status, out, _err = run_cli(str(path), "--canonical")
                self.assertEqual(status, 1)
                self.assertTrue(out.endswith(": $: the file is not in canonical form (RFC 8785 key order and numbers, "
                                             "2-space indent, LF line ends, a final newline, arrays sorted by id); "
                                             "--print-canonical writes it [I11]\n"), out)
                self.assertEqual(run_cli(str(path))[0], 0)
        self.assertEqual(run_cli(str(self.write("lf.json", text)), "--canonical")[0], 0)
        status, out, err = run_cli(str(self.write("bom.json", b"\xef\xbb\xbf" + text.encode())), "--canonical")
        self.assertEqual((status, out), (2, ""))
        self.assertIn("byte-order mark", err)
        data = text.encode("utf-8")
        doc = V.loads(data)
        self.assertTrue(V.check(doc, text=data, canonical=True).ok and V.check(doc, text=text, canonical=True).ok)
        self.assertEqual(codes(doc, text=data.replace(b"\n", b"\r\n"), canonical=True), ["I11"])

    def test_print_canonical_sorts_validates_then_writes(self):
        doc = load("mixed.json")
        doc["declarations"].reverse()
        doc["items"][0]["legacy_ids"] = ["zz", "aa"]
        unsorted = self.write("unsorted.json", json.dumps(doc, indent=1))
        self.assertIn("[I2]", run_cli(str(unsorted))[1])
        status, out, err = run_cli(str(unsorted), "--print-canonical")
        self.assertEqual((status, err), (0, ""))
        fixed = V.loads(out)
        self.assertEqual(fixed["items"][0]["legacy_ids"], ["aa", "zz"])
        self.assertEqual(run_cli(str(self.write("fixed.json", out)), "--canonical")[0], 0)
        messy = self.write("messy.json", json.dumps(media_doc(), indent=4))
        status, out, err = run_cli(str(messy), "--print-canonical")
        self.assertEqual((status, out), (0, V.canonical_dumps(media_doc())))
        self.assertIn("[W-CONFORMS]", err)                          # warnings go to stderr
        for name, body, code in (("dangling.json", load("invalid-dangling-reference.json"), "I3"),
                                 ("types.json", json.dumps(dict(load("mixed.json"), clusters=[{"id": "c", "items": [[1]]}])),
                                  "SCHEMA"),
                                 ("records.json", json.dumps(malformed_records()), "SCHEMA")):
            path = self.write(name, body)
            status, out, err = run_cli(str(path), "--print-canonical")
            self.assertEqual((status, out), (1, ""))
            self.assertIn(f"[{code}]", err)
            status, out, err = run_cli(str(path), "--print-canonical", "--format", "json")
            self.assertEqual((status, out, json.loads(err)["problems"][0]["code"]), (1, "", code))
        path = self.write("surrogate.json", '{"schema_version": "' + JSON_LONE_SURROGATE + '"}')
        status, out, err = run_cli(str(path), "--print-canonical", "--format", "json")
        self.assertEqual((status, out, json.loads(err)["problems"][0]["code"]), (2, "", "IJSON"))
        self.assertIn("--print-canonical takes exactly one document", run_cli(str(path), str(path),
                                                                              "--print-canonical")[2])

    def test_output_is_utf8_or_escaped_whatever_the_locale(self):
        source = EXAMPLES / "pdf-region.json"
        for encoding in ("latin-1", "ascii"):
            child = run_child(str(source), "--print-canonical", PYTHONIOENCODING=encoding, LC_ALL="C")
            self.assertEqual((child.returncode, child.stdout, child.stderr), (0, source.read_bytes(), b""))
        doc = load("pdf-region.json")
        doc["items"].insert(1, dict(doc["items"][0]))
        doc["items"][0]["id"] = doc["items"][1]["id"] = "d" + chr(0xE9) + "finition-1.1"
        path = self.write("accent.json", json.dumps(doc, ensure_ascii=False))
        child = run_child(str(path), PYTHONIOENCODING="ascii", LC_ALL="C")
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertIn(b"duplicate id 'd\\xe9finition-1.1'", child.stdout)
        child = run_child(str(path), "--format", "json", PYTHONIOENCODING="ascii", LC_ALL="C")
        self.assertIn("duplicate id", json.loads(child.stdout.decode("ascii"))["problems"][0]["message"])

    def test_an_internal_error_is_reported_never_a_traceback_never_invalid(self):
        good = EXAMPLES / "pdf-region.json"
        with mock.patch.object(V.Checker, "run", side_effect=KeyError("boom")):
            status, out, err = run_cli(str(good), str(good))
        self.assertEqual((status, out, err), (2, "", f"{good}: internal error: KeyError: 'boom'\n" * 2))
        schema_file = self.write("odd.schema.json", json.dumps({"type": "object", "format": "email"}))
        child = run_child(str(good), "--schema", str(schema_file))
        self.assertEqual((child.returncode, child.stdout), (2, b""))
        self.assertIn(b"internal error: SchemaError: #: keyword 'format' is not implemented", child.stderr)
        self.assertNotIn(b"Traceback", child.stderr)

    def test_lint_flag_and_validate(self):
        doc = load("mixed.json")
        doc["provenance"][0]["note"] = "see https://example.org/run"
        path = self.write("doc.json", doc)
        self.assertEqual(run_cli(str(path))[0], 0)
        status, out, _err = run_cli(str(path), "--lint", "external-urls")
        self.assertEqual(status, 1)
        self.assertTrue(out.rstrip().endswith(" [L1]"))
        status, _out, err = run_cli(str(path), "--lint", "no-such-lint")
        self.assertEqual(status, 2)
        self.assertIn("invalid choice", err)
        bad = load("invalid-dangling-reference.json")
        self.assertEqual(V.validate(bad), ["$.links[2].declaration: 'Notes.Box.volume_pos' is not an id in declarations[]"])


class TestScaling(unittest.TestCase):

    def test_unique_items_is_linear(self):
        checker = S.Validator({"type": "array", "uniqueItems": True})
        big = [{"id": f"x{i}", "n": [i, i + 0.5, {"k": True}]} for i in range(20000)]
        start = time.perf_counter()
        self.assertEqual(checker.errors(big), [])
        self.assertLess(time.perf_counter() - start, 5.0)
        big.append(dict(big[7]))
        self.assertEqual(checker.errors(big), [("$[20000]", "duplicates an earlier entry")])
        self.assertEqual(checker.errors([1, 1.0]), [("$[1]", "duplicates an earlier entry")])
        self.assertEqual(checker.errors([1, True, 0, False, None, "", [], [2, 1], [1, 2]]), [])
        self.assertEqual(checker.errors([{"a": 1, "b": 2}, {"b": 2, "a": 1}]), [("$[1]", "duplicates an earlier entry")])

    def test_quote_hash_items_are_checked_in_linear_time(self):
        doc = load("pdf-region.json")
        doc["sources"][0]["physical_page_count"] = 100000
        doc["items"], doc["locations"], doc["links"] = [], [], []
        doc["declarations"] = [d for d in doc["declarations"] if d["id"] == "Notes.Box"]
        for i in range(3000):
            text = f"quote number {i}"
            rid = ids.passage_quote_id(text)
            doc["items"].append({"coverage": "formalized", "form": "passage", "id": rid, "id_source": "quote_hash",
                                 "kind": "passage", "source": "notes-pdf", "title": f"t{i}"})
            doc["locations"].append(loc(f"{rid}@loc", "notes-pdf",
                                        [frag(vocab.CONFORMS_TO_PDF, f"page={i + 1}", quote(text))], (rid,)))
            doc["links"].append(link(rid, "Notes.Box") | {"provenance": "prov-docstrings"})
        doc = V.canonicalize(doc)
        start = time.perf_counter()
        self.assertTrue(V.check(doc).ok)
        self.assertLess(time.perf_counter() - start, 4.0)


class TestAgreementWithJsonschema(unittest.TestCase):
    """Only when jsonschema is installed: it and the package's evaluator agree, except on Python's ``$``."""

    def setUp(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        self.real = jsonschema.Draft202012Validator(schema())
        jsonschema.Draft202012Validator.check_schema(schema())
        self.ours = S.Validator(schema())

    def test_python_jsonschema_lets_a_dollar_match_before_a_final_newline(self):
        doc = load("pdf-region.json")
        doc["companion"]["commit"] += "\n"
        self.assertTrue(self.real.is_valid(doc))
        self.assertTrue(self.ours.errors(doc))

    def test_both_evaluators_agree_on_the_documents_and_on_mutations(self):
        docs = all_docs() + [load(n) for n in INVALID]
        rng = random.Random(0)
        values = [None, True, 0, -1, 1.5, "", "x", "1.0", [], {}, {"type": "TextQuoteSelector"}, "page=0", "passage",
                  "numbered", "site", "partial_only", {"doi": "10.1/x"}, [{"database": "stacks", "tag": "1"}]]

        def paths(x, p=()):
            yield p
            items = x.items() if isinstance(x, dict) else enumerate(x) if isinstance(x, list) else ()
            for k, v in items:
                yield from paths(v, p + (k,))
        for doc in docs:
            self.assertEqual(self.real.is_valid(doc), not self.ours.errors(doc))
        for _ in range(600):
            doc = copy.deepcopy(rng.choice(docs))
            where = rng.choice(list(paths(doc))[1:])
            parent = doc
            for key in where[:-1]:
                parent = parent[key]
            parent[where[-1]] = rng.choice(values)
            with self.subTest(path=where):
                self.assertEqual(self.real.is_valid(doc), not self.ours.errors(doc))


if __name__ == "__main__":
    unittest.main()
