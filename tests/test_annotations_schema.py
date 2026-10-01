"""The formal-companion annotation format: schema, invariants, ids, canonical form.

Tests docs/annotations.md against the package.  The shipped examples must
validate, the deliberately broken ones must fail with exactly the line each
records in its own ``x_expected_error`` key, and a shuffled document must
canonicalise back to the same bytes.  When the ``jsonschema`` package is
importable the package's own evaluator is also checked against it; the suite
never needs it.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import random
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
# The copy under test is the one Python imports: an installed package when
# there is one (a wheel, an sdist install, an editable install of src/).
# Only when none is importable does the suite fall back to the source tree, so
# a checkout still runs with nothing installed.
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(SRC))

import formal_companion_annotations                                                 # noqa: E402
from formal_companion_annotations import ids                                        # noqa: E402
from formal_companion_annotations import validate as V                              # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402
from formal_companion_annotations.schemacheck import SchemaError, Validator         # noqa: E402

#: The imported package's directory, wherever it was installed.
PACKAGE = Path(formal_companion_annotations.__file__).resolve().parent
EXAMPLES = ROOT / "examples" / "annotations"
SCHEMA_FILE = "annotations-v1.0.schema.json"
#: The repository's copy, for readers and non-Python consumers ...
SCHEMA = ROOT / "schema" / SCHEMA_FILE
#: ... the package-data copy in the source tree, which a build packages ...
SOURCE_TREE_SCHEMA = SRC / "formal_companion_annotations" / "schema" / SCHEMA_FILE
#: ... and the copy the imported checker loads (the same file as the one above
#: when the source tree is what is imported); all three are byte-identical.
PACKAGED_SCHEMA = PACKAGE / "schema" / SCHEMA_FILE
#: The schema's ``$id``: one per format minor, never changed after release,
#: never fetched (docs/annotations.md section 12.5).
SCHEMA_ID = "https://w3id.org/formal-companion/annotations/v1.0/schema.json"
SCHEMA_ID_RULE = re.compile(r"https://w3id\.org/formal-companion/annotations/v(?P<major>[0-9]+)\.(?P<minor>[0-9]+)"
                            r"/schema\.json")
VALID = ("graph-profile.json", "minimal.json", "mixed.json", "other-media.json", "pdf-region.json",
         "site-pages.json", "tex-lines.json", "web-passage.json")
INVALID = ("invalid-dangling-reference.json", "invalid-reversed-line-range.json", "invalid-undeclared-profile.json")
EPUB_CFI = "http://www.idpf.org/epub/linking/cfi/epub-cfi.html"
#: The statement-hash ids the examples use (the first 12 hex digits of the hash of the signature's hash form).
PDF_EXAMPLE = ids.anonymous_id("example", ids.statement_sha256("example : volume (Box.unit 2) = 1"))
GRAPH_EXAMPLE = ids.anonymous_id("example", ids.statement_sha256("example : Box.unit 0 = Box.unit 0"))
SITE_INSTANCE = ids.anonymous_id("instance", ids.statement_sha256("instance : IsProbabilityMeasure coinMeasure"))
ALL_PROFILES = {"audit": "1.0", "graph": "1.0", "history": "1.0", "site": "1.0"}


def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def problems(doc: dict) -> list[str]:
    return V.validate(doc)


def warnings(doc: dict) -> list[str]:
    return [str(w) for w in V.check(doc).warnings]


def lines(doc: dict, **kwargs) -> list[str]:
    """Each problem as the CLI prints it after the file name: ``<path>: <message> [<code>]``."""
    return [f"{p} [{p.code}]" for p in V.check(doc, **kwargs).problems]


def codes(doc: dict, **kwargs) -> list[str]:
    return [p.code for p in V.check(doc, **kwargs).problems]


def by_id(records: list[dict], rid: str) -> dict:
    return next(r for r in records if r["id"] == rid)


def walk_selectors(sel: dict):
    yield sel
    if "refinedBy" in sel:
        yield from walk_selectors(sel["refinedBy"])


class TestTheSchemaFile(unittest.TestCase):

    def schema(self) -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_it_is_draft_2020_12_with_an_id_that_is_never_fetched(self):
        schema = self.schema()
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], SCHEMA_ID)
        self.assertEqual(schema["title"], "formal-companion annotations, schema 1.0")
        self.assertIn("validators never fetch it", schema["description"])
        self.assertIn("documents need not carry $schema", schema["description"])

    def test_the_id_is_one_per_format_minor(self):
        """Section 12.5: ``<base>/v<major>.<minor>/schema.json``, the file named after the minor."""
        m = SCHEMA_ID_RULE.fullmatch(self.schema()["$id"])
        self.assertIsNotNone(m, self.schema()["$id"])
        major, minor = int(m["major"]), int(m["minor"])
        self.assertEqual(major, vocab.ANNOTATION_SCHEMA_MAJOR)
        self.assertEqual(f"{major}.{minor}", vocab.ANNOTATION_SCHEMA_VERSION)
        self.assertEqual(SCHEMA.name, f"annotations-v{major}.{minor}.schema.json")
        self.assertEqual(self.schema()["$id"], V.schema_id(major, minor))
        self.assertTrue(self.schema()["$id"].startswith(vocab.ANNOTATION_SCHEMA_ID_BASE + "/"))
        self.assertEqual(int(formal_companion_annotations.__version__.split(".")[0]), major,
                         "package MAJOR is the format's major")

    def test_the_checker_never_fetches_anything(self):
        """No module of the package imports a network library, so no ``$id`` or ``$schema`` is fetched."""
        for module in sorted(PACKAGE.glob("*.py")):
            text = module.read_text(encoding="utf-8")
            with self.subTest(module=module.name):
                self.assertIsNone(re.search(r"^\s*(import|from)\s+(urllib|http|socket|ssl)\b", text, re.M))

    def test_a_document_need_not_carry_dollar_schema(self):
        self.assertNotIn("$schema", self.schema()["required"])
        doc = load("mixed.json")
        doc.pop("$schema", None)
        self.assertEqual(problems(doc), [])

    def test_the_description_names_this_projects_checker(self):
        description = self.schema()["description"]
        self.assertIn("the formal-companion-annotations-validate command", description)
        self.assertIn("src/formal_companion_annotations/validate.py", description)
        self.assertTrue((ROOT / "src" / "formal_companion_annotations" / "validate.py").is_file())
        self.assertIn("docs/annotations.md", description)
        self.assertTrue((ROOT / "docs" / "annotations.md").is_file())

    def test_the_packaged_schema_is_the_repositorys_byte_for_byte(self):
        self.assertEqual(PACKAGED_SCHEMA.read_bytes(), SCHEMA.read_bytes())
        self.assertEqual(SOURCE_TREE_SCHEMA.read_bytes(), SCHEMA.read_bytes())
        self.assertEqual(sorted(p.name for p in SCHEMA.parent.glob("*.json")), [SCHEMA_FILE])
        self.assertEqual(sorted(p.name for p in PACKAGED_SCHEMA.parent.glob("*.json")), [SCHEMA_FILE])

    def test_the_format_identifier_is_formal_companion(self):
        self.assertEqual(vocab.ANNOTATION_SCHEMA, "formal-companion/annotations")
        self.assertEqual(self.schema()["properties"]["schema"]["const"], "formal-companion/annotations")
        doc = load("minimal.json")
        doc["schema"] = "other/annotations"
        self.assertEqual(lines(doc), ['$.schema: must be "formal-companion/annotations" [SCHEMA]'])

    def test_it_is_itself_in_canonical_form(self):
        text = SCHEMA.read_text(encoding="utf-8")
        self.assertEqual(text, V.canonical_dumps(json.loads(text)))

    def test_schema_version_is_a_major_minor_string(self):
        root = self.schema()["properties"]
        self.assertEqual(root["schema_version"]["type"], "string")
        self.assertTrue(re.fullmatch(root["schema_version"]["pattern"], vocab.ANNOTATION_SCHEMA_VERSION))
        self.assertEqual(V.schema_path(1, 0), PACKAGED_SCHEMA)
        self.assertEqual(V.SCHEMA_PATH, PACKAGED_SCHEMA)
        self.assertEqual(V.SCHEMA_DIR, PACKAGED_SCHEMA.parent)

    def test_the_profiles_object_is_closed_and_versioned(self):
        profiles = self.schema()["properties"]["profiles"]
        self.assertIs(profiles["additionalProperties"], False)
        self.assertEqual(set(profiles["properties"]), set(vocab.ANNOTATION_PROFILES))
        self.assertNotIn("required", profiles)
        for name, sub in profiles["properties"].items():
            with self.subTest(profile=name):
                self.assertEqual(sub, {"pattern": "^1\\.(0|[1-9][0-9]*)$", "type": "string"})
                self.assertTrue(re.fullmatch(sub["pattern"], vocab.ANNOTATION_PROFILE_VERSIONS[name]))

    def test_the_evaluator_refuses_a_keyword_it_does_not_implement(self):
        with self.assertRaises(SchemaError):
            Validator({"type": "string", "format": "date-time"})
        with self.assertRaises(SchemaError):
            Validator({"$ref": "https://example.org/other.json"})

    def test_every_record_is_closed_and_takes_x_keys(self):
        d = self.schema()["$defs"]
        for name in ("source", "item", "declaration", "artifact", "membership", "link", "provenance",
                     "location", "destination", "snippet", "verdict", "unattributed", "cluster", "change"):
            with self.subTest(record=name):
                self.assertIs(d[name]["additionalProperties"], False)
                self.assertEqual(list(d[name]["patternProperties"]), ["^x_[a-z0-9_]+$"])
                self.assertIn("id", d[name]["required"])
        for name in ("pages", "quote", "signoff", "target", "relations", "resolution", "graph_lock",
                     "input_lock", "page_size", "page_hash", "identifiers", "xref", "package",
                     *vocab.ANNOTATION_SELECTOR_TYPES):
            with self.subTest(sub_object=name):
                self.assertIs(d[name]["additionalProperties"], False)
                self.assertNotIn("patternProperties", d[name])
        self.assertIs(self.schema()["additionalProperties"], False)

    def test_a_site_page_path_and_a_relative_href_share_one_grammar(self):
        d = self.schema()["$defs"]
        self.assertEqual(d["SitePageSelector"]["properties"]["path"], {"$ref": "#/$defs/site_path"})
        self.assertIn({"$ref": "#/$defs/site_path"}, d["destination"]["properties"]["href"]["anyOf"])
        ours = Validator(self.schema())
        for path in ("Notes/Section_2/", "a/b.html", "a:b.html", "/abs", "../up", "a#frag", "a b"):
            doc = load("site-pages.json")
            loc = next(l for l in doc["locations"] if l["target"]["selector"][0]["type"] == "SitePageSelector")
            loc["target"]["selector"][0]["path"] = path
            dest = doc["destinations"][0]
            dest["href"] = path
            errors = [p for p, _m in ours.errors(doc)]
            as_path = any(".path" in p for p in errors)
            as_href = any(".href" in p for p in errors)
            with self.subTest(path=path):
                self.assertEqual(as_path, as_href, errors)
                self.assertEqual(as_path, path not in ("Notes/Section_2/", "a/b.html"))

    def test_the_root_arrays_are_the_checkers(self):
        root = self.schema()["properties"]
        arrays = {k for k, v in root.items() if v.get("type") == "array"}
        self.assertEqual(arrays, set(V.RECORD_ARRAYS))
        owned = {a for p in V.PROFILES.values() for a in p["arrays"]}
        core = {"sources", "items", "declarations", "links", "provenance", "locations", "unattributed"}
        self.assertEqual(owned | core, arrays)
        self.assertEqual(owned & core, set())


class TestOneVocabulary(unittest.TestCase):
    """The schema's enums are vocab's, and documented (docs/vocabulary.md)."""

    def schema(self) -> dict:
        return json.loads(SCHEMA.read_text(encoding="utf-8"))["$defs"]

    #: Every enum in the schema, by ($defs name, property path), and its vocab set.
    #: A property path is the chain of property names below the definition
    #: (``declarations.verdict``: through an array's ``items``).
    ENUMS = {
            ("source", "kind"): vocab.ANNOTATION_SOURCE_KINDS,
            ("source", "scope"): vocab.ANNOTATION_SOURCE_SCOPES,
            ("source", "role"): vocab.ANNOTATION_SOURCE_ROLES,
            ("item", "form"): vocab.ANNOTATION_ITEM_FORMS,
            ("item", "id_source"): vocab.ANNOTATION_ITEM_ID_SOURCES,
            ("item", "kind_source"): vocab.ANNOTATION_TEXT_ORIGINS,
            ("item", "title_source"): vocab.ANNOTATION_TEXT_ORIGINS,
            ("item", "coverage"): vocab.ANNOTATION_COVERAGE,
            ("pages", "basis"): vocab.ANNOTATION_PAGE_BASES,
            ("pages", "anchor"): vocab.ANNOTATION_PAGE_ANCHORS,
            ("declaration", "kind"): vocab.ANNOTATION_LEAN_KINDS,
            ("declaration", "id_source"): vocab.ANNOTATION_ID_SOURCES,
            ("declaration", "sorry"): vocab.ANNOTATION_SORRY_CLASSES,
            ("artifact", "kind"): vocab.ANNOTATION_ARTIFACT_KINDS,
            ("membership", "role"): vocab.ANNOTATION_MEMBERSHIP_ROLES,
            ("link", "role"): vocab.ANNOTATION_LINK_ROLES,
            ("provenance", "actor"): vocab.ANNOTATION_PROVENANCE_ACTORS,
            ("provenance", "method"): vocab.ANNOTATION_PROVENANCE_METHODS,
            ("destination", "site"): vocab.ANNOTATION_DESTINATION_SITES,
            ("destination", "resolution"): vocab.ANNOTATION_DESTINATION_RESOLUTIONS,
            ("coordinate_space", "origin"): vocab.ANNOTATION_COORDINATE_ORIGINS,
            ("coordinate_space", "units"): vocab.ANNOTATION_COORDINATE_UNITS,
            ("coordinate_space", "x_axis"): vocab.ANNOTATION_COORDINATE_X_AXES,
            ("coordinate_space", "y_axis"): vocab.ANNOTATION_COORDINATE_Y_AXES,
            ("coordinate_space", "page_box"): vocab.ANNOTATION_PAGE_BOXES,
            ("text_layer", "unicode"): vocab.ANNOTATION_TEXT_UNICODE,
            ("text_layer", "whitespace"): vocab.ANNOTATION_TEXT_WHITESPACE,
            ("text_layer", "case"): vocab.ANNOTATION_TEXT_CASE,
            ("verdict", "verdict"): vocab.ANNOTATION_VERDICTS,
            ("verdict", "declarations.verdict"): vocab.ANNOTATION_VERDICTS,
            ("verdict", "severity"): vocab.ANNOTATION_SEVERITIES,
            ("verdict", "status"): vocab.ANNOTATION_VERDICT_STATUSES,
            ("resolution", "state"): vocab.ANNOTATION_RESOLUTION_STATES,
            ("unattributed", "claim"): vocab.ANNOTATION_UNATTRIBUTED_CLAIMS,
            ("change", "event"): vocab.ANNOTATION_CHANGELOG_EVENTS,
            ("change", "subject_kind"): vocab.ANNOTATION_CHANGELOG_SUBJECTS,
            ("change", "reason"): vocab.ANNOTATION_CHANGELOG_REASONS,
            ("selector", "type"): vocab.ANNOTATION_SELECTOR_TYPES,
    }
    _CONDITIONAL = frozenset({"allOf", "anyOf", "oneOf", "if", "then", "else", "not"})
    #: The six sets docs/vocabulary.md section 2 defines value by value.
    DEFINED = ("ANNOTATION_VERDICTS", "ANNOTATION_SEVERITIES", "ANNOTATION_VERDICT_STATUSES",
               "ANNOTATION_RESOLUTION_STATES", "ANNOTATION_SOURCE_ROLES", "ANNOTATION_SORRY_CLASSES")

    def schema_enums(self):
        """Every ``enum`` in the schema: (key, values, conditional).

        ``conditional`` is true for an enum inside allOf/anyOf/oneOf/if/then/
        else/not, which narrows a property the definition declares.
        """
        whole = json.loads(SCHEMA.read_text(encoding="utf-8"))

        def walk(node, owner, props, conditional):
            if isinstance(node, dict):
                if "enum" in node:
                    yield (owner, ".".join(props)), node["enum"], conditional
                for key, child in node.items():
                    if key == "properties" and isinstance(child, dict):
                        for name, sub in child.items():
                            yield from walk(sub, owner, props + [name], conditional)
                    elif key == "$defs":
                        for name, sub in child.items():
                            yield from walk(sub, name, [], False)
                    elif key != "enum":
                        yield from walk(child, owner, props, conditional or key in self._CONDITIONAL)
            elif isinstance(node, list):
                for child in node:
                    yield from walk(child, owner, props, conditional)
        yield from walk(whole, "$root", [], False)

    def test_every_enum_in_the_schema_is_a_vocab_set(self):
        found = list(self.schema_enums())
        self.assertGreater(len(found), 40)
        declared = set()
        for key, values, conditional in found:
            with self.subTest(enum=key, conditional=conditional):
                self.assertIn(key, self.ENUMS, f"schema enum {key} has no vocab set in ENUMS")
                if conditional:
                    self.assertLessEqual(set(values), set(self.ENUMS[key]))
                else:
                    declared.add(key)
                    self.assertEqual(set(values), set(self.ENUMS[key]))
                    self.assertEqual(values, sorted(values), "an enum is written in sorted order")
        self.assertEqual(declared, set(self.ENUMS), "an ENUMS row names no enum in the schema")

    def test_the_other_closed_sets_are_the_vocab_sets(self):
        d = self.schema()
        self.assertEqual(set(d["relations"]["properties"]), set(vocab.ANNOTATION_ITEM_RELATIONS))
        root = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]
        self.assertEqual(root["schema"]["const"], vocab.ANNOTATION_SCHEMA)
        self.assertEqual(set(root["profiles"]["properties"]), set(vocab.ANNOTATION_PROFILES))
        self.assertEqual(set(vocab.ANNOTATION_PROFILE_VERSIONS), set(vocab.ANNOTATION_PROFILES))
        self.assertEqual(set(V.PROFILES), set(vocab.ANNOTATION_PROFILES))
        self.assertEqual(set(vocab.ANNOTATION_ORIGIN_Y_AXIS), set(vocab.ANNOTATION_COORDINATE_ORIGINS))
        self.assertEqual(set(vocab.ANNOTATION_ORIGIN_Y_AXIS.values()), set(vocab.ANNOTATION_COORDINATE_Y_AXES))
        self.assertLessEqual(set(vocab.ANNOTATION_MEMBER_PARENT_KINDS), vocab.ANNOTATION_LEAN_KINDS)
        for kinds in vocab.ANNOTATION_MEMBER_PARENT_KINDS.values():
            self.assertLessEqual(kinds, vocab.ANNOTATION_LEAN_KINDS)
        # the schema's "members need a parent" rule names exactly the member kinds
        members = [rule for rule in d["declaration"]["allOf"]
                   if "kind" in rule["if"].get("properties", {}) and rule["then"].get("required") == ["parent"]]
        self.assertEqual(len(members), 1)
        self.assertEqual(set(members[0]["if"]["properties"]["kind"]["enum"]),
                         set(vocab.ANNOTATION_MEMBER_PARENT_KINDS))
        self.assertEqual(set(d["identifiers"]["properties"]), {"doi", "isbn", "arxiv"})
        self.assertEqual(vocab.ANNOTATION_RESOLUTION_STATES,
                         {"open", "fixed", "in_progress", "refuted", "argued_correct", "out_of_scope"})

    def test_a_walker_that_misses_an_enum_would_fail(self):
        """The walk sees a nested enum (inside ``items``) and a conditional one."""
        keys = {(key, conditional) for key, _v, conditional in self.schema_enums()}
        self.assertIn((("verdict", "declarations.verdict"), False), keys)
        self.assertIn((("declaration", "kind"), True), keys)

    def test_conforms_to_relation_and_xref_database_are_open_strings(self):
        d = self.schema()
        self.assertNotIn("enum", d["FragmentSelector"]["properties"]["conformsTo"])
        self.assertNotIn("conformsTo", d["FragmentSelector"]["required"])
        self.assertNotIn("enum", d["link"]["properties"]["relation"])
        self.assertNotIn("enum", d["xref"]["properties"]["database"])
        self.assertEqual(set(V.CONFORMS), set(vocab.ANNOTATION_CONFORMS_TO))
        for token in vocab.ANNOTATION_LINK_RELATIONS | vocab.ANNOTATION_XREF_DATABASES:
            self.assertTrue(re.fullmatch(d["link"]["properties"]["relation"]["pattern"], token), token)

    def test_every_selector_type_has_a_definition(self):
        d = self.schema()
        for name in vocab.ANNOTATION_SELECTOR_TYPES:
            with self.subTest(selector=name):
                self.assertEqual(d[name]["properties"]["type"]["const"], name)
        self.assertEqual(vocab.ANNOTATION_SELECTOR_TYPES,
                         {"FragmentSelector", "TextQuoteSelector", "CssSelector", "PdfRegionSelector",
                          "SitePageSelector"})
        for gone in ("TextPositionSelector", "DataPositionSelector", "XPathSelector", "SvgSelector",
                     "RangeSelector", "state"):
            self.assertNotIn(gone, d)
        self.assertNotIn("state", d["target"]["properties"])

    def test_every_set_is_named_for_the_format(self):
        """vocab holds the format's own vocabulary: every set or table is ``ANNOTATION_<...>`` (or the
        scanner's ``ANONYMOUS_KEYWORDS``) and public, so no set named after a tool's verdicts, statuses or
        classes can sit here under another name."""
        names = [name for name in dir(vocab)
                 if isinstance(getattr(vocab, name), (frozenset, dict)) and name != "__builtins__"]
        self.assertGreater(len(names), 30)
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(name.startswith("ANNOTATION_") or name == "ANONYMOUS_KEYWORDS", name)
                self.assertIn(name, vocab.__all__)

    def test_every_value_is_documented(self):
        text = (ROOT / "docs" / "vocabulary.md").read_text(encoding="utf-8")
        section = text.split("\n## 1. ", 1)[1].split("\n---", 1)[0]
        for name in dir(vocab):
            value = getattr(vocab, name)
            if not name.startswith("ANNOTATION_") or not isinstance(value, frozenset):
                continue
            for entry in value:
                with self.subTest(enum=name, value=entry):
                    self.assertIn(f"`{entry}`", section)
        for kind, parents in vocab.ANNOTATION_MEMBER_PARENT_KINDS.items():
            self.assertIn(f"`{kind}`", section)
        for name in self.DEFINED:
            with self.subTest(defined=name):
                self.assertIn(f"`{name}`", text.split("\n## 2. ", 1)[1])

    def test_every_defined_value_has_a_meaning_in_the_formats_own_words(self):
        """Each of the six sets has its own subsection of section 2 with one
        ``| `value` | meaning |`` row per value, and no tool is named."""
        text = (ROOT / "docs" / "vocabulary.md").read_text(encoding="utf-8")
        section = text.split("\n## 2. ", 1)[1].split("\n---", 1)[0]
        subsections = {}
        for block in section.split("\n### ")[1:]:
            heading, _, body = block.partition("\n")
            subsections[heading] = body
        for name in self.DEFINED:
            values = getattr(vocab, name)
            with self.subTest(set=name):
                title = "Resolution states" if name == "ANNOTATION_RESOLUTION_STATES" else f"`{name}`"
                matches = [h for h in subsections if re.match(rf"2\.\d+ {re.escape(title)}(:|$)", h)]
                self.assertEqual(len(matches), 1, f"no subsection of section 2 defines {name}")
                rows = {}
                for line in subsections[matches[0]].splitlines():
                    m = re.match(r"^\| `([^`]+)` \| (.+) \|$", line)
                    if m:
                        rows[m.group(1)] = m.group(2).strip()
                self.assertEqual(set(rows), set(values), f"{name}: the rows are not the set's values")
                for value, meaning in rows.items():
                    self.assertGreaterEqual(len(meaning.split()), 3, f"{name}.{value} has no meaning")
        self.assertIn("**The format owns every value it uses.**", text)
        for token in set(re.findall(r"\b[A-Z][A-Z0-9]*_[A-Z0-9_]*\b", text)):   # every set it names is vocab's
            self.assertTrue(token == "ANNOTATION_" or hasattr(vocab, token), f"{token} is not a name of vocab")


class TestOneIdGrammar(unittest.TestCase):
    """ids.py (the writer) and validate.py (the checker) share vocab's grammar."""

    def test_both_sides_compile_the_vocab_pattern(self):
        self.assertIn(vocab.DECLARED_ID_PATTERN, ids.DECLARED_ID.pattern)
        self.assertIn(vocab.HASH_ID_PATTERN, ids.HASH_ID.pattern)
        self.assertIs(V._DECLARED_ID, ids.DECLARED_ID)
        self.assertIs(V._HASH_ID, ids.HASH_ID)

    def test_capitals_are_allowed_and_hash_shaped_slugs_are_reserved(self):
        for good in ("example:L1-seminorm-ae-laws", "instance:Foo.bar_baz", "example:0123456789abc"):
            with self.subTest(id=good):
                self.assertTrue(ids.DECLARED_ID.fullmatch(good))
        for bad in ("example:0123456789ab", "example:-x", "theorem:foo", "example:a b", "Foo.bar",
                    "example:foo\n"):
            with self.subTest(id=bad):
                self.assertFalse(ids.DECLARED_ID.fullmatch(bad))


class TestTheExamples(unittest.TestCase):

    def test_the_valid_examples_validate_in_canonical_form(self):
        for name in VALID:
            with self.subTest(example=name):
                text = (EXAMPLES / name).read_text(encoding="utf-8")
                self.assertEqual(V.validate(V.loads(text), text=text, canonical=True), [])
        self.assertEqual(sorted(p.name for p in EXAMPLES.glob("*.json")), sorted(VALID + INVALID))

    def test_the_only_warning_is_the_unknown_conforms_to(self):
        for name in VALID:
            with self.subTest(example=name):
                found = warnings(load(name))
                if name == "other-media.json":
                    self.assertEqual(len(found), 1)
                    self.assertIn("is not an IRI this checker knows", found[0])
                else:
                    self.assertEqual(found, [])

    def test_each_invalid_example_fails_with_exactly_its_recorded_error(self):
        """``x_expected_error`` is the CLI's line after the file name: path, message and code."""
        for name in INVALID:
            with self.subTest(example=name):
                doc = load(name)
                self.assertEqual(lines(doc), [doc["x_expected_error"]])
                self.assertRegex(doc["x_expected_error"], r" \[I[0-9]+\]$")
        seen = {load(name)["x_expected_error"].rsplit("[", 1)[1] for name in INVALID}
        self.assertEqual(seen, {"I3]", "I7]", "I14]"})

    def test_every_record_type_appears(self):
        docs = [load(n) for n in VALID]
        for key in V.RECORD_ARRAYS:
            with self.subTest(array=key):
                self.assertTrue(any(d.get(key) for d in docs), key)
        graph = load("graph-profile.json")
        self.assertIn("graph", graph["companion"])
        self.assertTrue(any("inputs" in p for p in graph["provenance"]))
        values = lambda array, field: {r.get(field) for d in docs for r in d.get(array, [])}
        self.assertEqual(values("items", "id_source"), set(vocab.ANNOTATION_ITEM_ID_SOURCES))
        self.assertEqual(values("items", "form"), set(vocab.ANNOTATION_ITEM_FORMS))
        self.assertEqual(values("items", "coverage") - {None}, set(vocab.ANNOTATION_COVERAGE))
        self.assertEqual(values("declarations", "id_source"), set(vocab.ANNOTATION_ID_SOURCES))
        self.assertLessEqual({"field", "projection", "structure", "class", "example", "instance", "constructor",
                              "alias"}, values("declarations", "kind"))
        self.assertIn(True, values("declarations", "unlocated"))
        self.assertEqual(values("artifacts", "kind") - {None}, {"module_doc", "check", "figure"})
        self.assertEqual(values("memberships", "role"), set(vocab.ANNOTATION_MEMBERSHIP_ROLES))
        self.assertEqual(values("changelog", "event"), set(vocab.ANNOTATION_CHANGELOG_EVENTS))
        self.assertEqual(values("links", "relation") - {None}, set(vocab.ANNOTATION_LINK_RELATIONS))
        self.assertTrue(any("page_hashes" in s for d in docs for s in d["sources"]))
        self.assertTrue(any("source" in entry for d in docs for p in d["provenance"]
                            for entry in p.get("inputs", [])))
        self.assertTrue(any(i["id_source"] == "quote_hash" and "quote" not in i for d in docs for i in d["items"]),
                        "a quote_hash passage whose quote is its location's")
        ordinal = [c for c in graph["changelog"] if c["event"] == "ordinal_assigned"]
        self.assertTrue(ordinal and all("file" in c for c in ordinal))
        retired = {c["subject"] for c in graph["changelog"] if c["event"] == "retired"}
        self.assertTrue(any(c["subject"] in retired for c in ordinal), "a record outlives its retired id")
        self.assertTrue(any("resolution" not in v for d in docs for v in d.get("verdicts", [])),
                        "an open verdict carries no resolution")
        self.assertTrue(any("artifact" in r for d in docs for r in d.get("destinations", [])))
        rels = {k for d in docs for i in d["items"] for k in i.get("relations", {})}
        self.assertEqual(rels, set(vocab.ANNOTATION_ITEM_RELATIONS))
        verdict = graph["verdicts"][0]
        self.assertTrue({"evidence", "locations"} <= set(verdict))
        self.assertTrue({"issue", "commits", "replaced_by"} <= set(verdict["resolution"]))
        declared = {name for d in docs for name in d.get("profiles", {})}
        self.assertEqual(declared, set(vocab.ANNOTATION_PROFILES))

    def test_mixed_exercises_every_profile_and_every_new_field(self):
        doc = load("mixed.json")
        self.assertEqual(doc["profiles"], ALL_PROFILES)
        self.assertTrue({"toolchain", "packages"} <= set(doc["companion"]))
        self.assertEqual([p["name"] for p in doc["companion"]["packages"]], ["batteries", "mathlib"])
        identifiers = next(s["identifiers"] for s in doc["sources"] if "identifiers" in s)
        self.assertEqual(set(identifiers), {"doi", "isbn", "arxiv"})
        self.assertTrue(any("xrefs" in i for i in doc["items"]))
        self.assertTrue(any("coverage_note" in i for i in doc["items"]))
        partial = next(i for i in doc["items"] if i.get("coverage") == "partial_only")
        roles = {l["role"] for l in doc["links"] if l["item"] == partial["id"]}
        self.assertEqual(roles, {"attributed"})
        self.assertEqual({l["relation"] for l in doc["links"] if l["item"] == partial["id"]},
                         {"part", "special_case"})
        private = next(i for i in doc["items"] if i.get("coverage") == "private_only")
        key = next(l for l in doc["links"] if l["item"] == private["id"] and l["role"] == "key")
        self.assertTrue(by_id(doc["declarations"], key["declaration"])["private"])
        constructor = next(d for d in doc["declarations"] if d["kind"] == "constructor")
        self.assertEqual(by_id(doc["declarations"], constructor["parent"])["kind"], "structure")
        self.assertTrue(any(d["kind"] == "alias" for d in doc["declarations"]))
        self.assertTrue(any(k.startswith("x_") for k in doc["verdicts"][0]), "finding data went to x_ keys")

    def test_every_location_kind_appears(self):
        docs = [load(n) for n in VALID]
        families = {V.source_family(s) for d in docs for s in d["sources"]}
        self.assertEqual(families, {"pdf", "html", "text", "generic"})
        kinds = {s["kind"] for d in docs for s in d["sources"]}
        self.assertEqual(kinds, set(vocab.ANNOTATION_SOURCE_KINDS))
        seen, conforms, regions = set(), set(), set()
        for d in docs:
            for loc in d.get("locations", []):
                for top in loc["target"]["selector"]:
                    for sel in walk_selectors(top):
                        seen.add(sel["type"])
                        if "conformsTo" in sel:
                            conforms.add(sel["conformsTo"])
                        if sel["type"] == "PdfRegionSelector":
                            regions.add("rect" if "rect" in sel else "quads")
                            regions.add(sel["coordinate_space"]["units"])
        self.assertEqual(seen, set(vocab.ANNOTATION_SELECTOR_TYPES))
        self.assertEqual(conforms - {EPUB_CFI}, set(vocab.ANNOTATION_CONFORMS_TO))
        self.assertEqual(regions, {"rect", "quads", "normalized", "pt"})
        site = load("site-pages.json")
        unhosted = [s for s in site["sources"] if s["kind"] == "web"]
        self.assertTrue(unhosted and all("url" not in s and s["scope"] == "site" for s in unhosted))
        page_only = [loc for d in docs for loc in d.get("locations", [])
                     if "pages" in loc and all(s["type"] == "FragmentSelector" and "refinedBy" not in s
                                               for s in loc["target"]["selector"])]
        self.assertTrue(page_only)
        mixed = load("mixed.json")
        passages = [i for i in mixed["items"] if i["form"] == "passage"]
        self.assertGreaterEqual(len(passages), 2)
        pages = [loc["target"]["selector"][0].get("page") for loc in mixed["locations"]]
        self.assertGreater(len(pages), len(set(pages)), "no page carries two items")

    def test_the_examples_quote_no_real_source(self):
        """Examples are synthetic: every source title says so, and every URL is an example.org one."""
        for name in VALID + INVALID:
            doc = load(name)
            for source in doc["sources"]:
                if source["kind"] != "lean":
                    with self.subTest(example=name, source=source["id"]):
                        self.assertIn("synthetic", source["title"])
                for url in [source.get("url")] + source.get("alternate_urls", []):
                    if url:
                        self.assertRegex(url, r"^https://[a-z.]*example\.org/")
            for dest in doc.get("destinations", []):
                if dest["href"].startswith("https://"):
                    self.assertRegex(dest["href"], r"^https://[a-z.]*example\.org/")

    def readme_block(self) -> str | None:
        readme = ROOT / "README.md"
        if not readme.is_file():
            return None
        m = re.search(r"```json\n(.*?)```\n", readme.read_text(encoding="utf-8"), re.S)
        return m.group(1) if m else None

    def test_the_readme_minimal_document_is_the_example(self):
        """README.md's first json block is examples/annotations/minimal.json, byte for byte."""
        block = self.readme_block()
        if block is None:
            self.skipTest("README.md has no json block yet")
        minimal = (EXAMPLES / "minimal.json").read_text(encoding="utf-8")
        self.assertEqual(json.loads(block), json.loads(minimal))
        self.assertEqual(block, minimal)

    def test_the_specifications_minimal_document_is_the_example(self):
        """docs/annotations.md section 3.2 shows the same document (compacted)."""
        text = (ROOT / "docs" / "annotations.md").read_text(encoding="utf-8")
        heading = "A minimal complete document"
        if heading not in text:
            self.skipTest("the specification has no minimal document section yet")
        after = text.split(heading, 1)[1]
        block = re.search(r"```json\n(.*?)```", after, re.S).group(1)
        self.assertEqual(json.loads(block), load("minimal.json"))
        self.assertEqual(V.canonical_dumps(json.loads(block)), (EXAMPLES / "minimal.json").read_text(encoding="utf-8"))

    def test_minimal_is_the_core_only(self):
        doc = load("minimal.json")
        self.assertEqual(set(doc), {"companion", "declarations", "items", "links", "provenance", "schema",
                                    "schema_version", "sources"})
        self.assertEqual([len(doc[k]) for k in ("sources", "items", "declarations", "links", "provenance")],
                         [1, 1, 1, 1, 1])


class TestTheCli(unittest.TestCase):

    def run_cli(self, *argv: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = V.main(list(argv))
        return status, out.getvalue(), err.getvalue()

    def test_valid_invalid_and_unreadable(self):
        status, out, _ = self.run_cli(*(str(EXAMPLES / n) for n in VALID), "--canonical")
        self.assertEqual(status, 0, out)
        self.assertEqual(out.count(": ok ("), len(VALID))
        self.assertEqual(out.count(": warning: "), 1)
        bad = EXAMPLES / INVALID[0]
        status, out, _ = self.run_cli(str(bad))
        self.assertEqual(status, 1)
        self.assertIn(load(INVALID[0])["x_expected_error"], out)
        with tempfile.TemporaryDirectory() as tmp:
            dup = Path(tmp) / "dup.json"
            dup.write_text('{"schema": 1, "schema": 2}', encoding="utf-8")
            status, _, err = self.run_cli(str(dup))
            self.assertEqual(status, 2)
            self.assertIn("duplicate key", err)
            nan = Path(tmp) / "nan.json"
            nan.write_text('{"x": NaN}', encoding="utf-8")
            self.assertEqual(self.run_cli(str(nan))[0], 2)

    def test_print_canonical_writes_the_canonical_bytes(self):
        name = "mixed.json"
        doc = load(name)
        with tempfile.TemporaryDirectory() as tmp:
            messy = Path(tmp) / name
            messy.write_text(json.dumps(doc, indent=4), encoding="utf-8")
            status, out, _ = self.run_cli(str(messy), "--canonical")
            self.assertEqual(status, 1)
            self.assertIn("not in canonical form", out)
            status, out, _ = self.run_cli(str(messy), "--print-canonical")
            self.assertEqual(status, 0)
            self.assertEqual(out, (EXAMPLES / name).read_text(encoding="utf-8"))


class TestCanonicalForm(unittest.TestCase):
    """Section 10: RFC 8785 key order and numbers, independent of Python's float spelling."""

    def test_numbers_follow_ecmascript(self):
        cases = {
            1.0: "1", 0.00001: "0.00001", 0.247647: "0.247647", -0.0: "0", 0: "0",
            1e21: "1e+21", 1e20: "100000000000000000000", 1e-7: "1e-7", 1e-6: "0.000001",
            333333333.33333329: "333333333.3333333", 1e30: "1e+30", 4.50: "4.5", 2e-3: "0.002",
            1e-27: "1e-27", 5e-324: "5e-324", 1.7976931348623157e308: "1.7976931348623157e+308",
            -1.5: "-1.5", 612: "612", 2 ** 53: "9007199254740992", 2 ** 60: "1152921504606847000",
            0.1 + 0.2: "0.30000000000000004", 123e-20: "1.23e-18",
        }
        for value, want in cases.items():
            with self.subTest(value=value):
                self.assertEqual(V.jcs_number(value), want)
        with self.assertRaises(ValueError):
            V.jcs_number(float("nan"))
        with self.assertRaises(TypeError):
            V.jcs_number(True)

    def test_python_and_canonical_spellings_differ(self):
        self.assertEqual(json.dumps(1.0), "1.0")
        self.assertEqual(json.dumps(0.00001), "1e-05")
        self.assertEqual(V.canonical_dumps({"a": 1.0, "b": 0.00001, "c": 0.247647}),
                         '{\n  "a": 1,\n  "b": 0.00001,\n  "c": 0.247647\n}\n')

    def test_keys_sort_by_utf16_code_units(self):
        astral, bmp = "\U0001d400", "Ａ"            # MATHEMATICAL BOLD CAPITAL A, FULLWIDTH A
        text = V.canonical_dumps({"": 1, "\U0001f600": 2, "b": 3, "a": 4, bmp: 5, astral: 6})
        order = [line.split('"')[1] for line in text.splitlines()[1:-1]]
        self.assertEqual(order, ["", "a", "b", astral, "\U0001f600", bmp])
        self.assertEqual(sorted(order), ["", "a", "b", bmp, astral, "\U0001f600"], "code point order differs")

    def test_records_and_id_lists_sort_by_utf16_code_units_too(self):
        astral, bmp = "\U0001d400", "Ａ"            # MATHEMATICAL BOLD CAPITAL A, FULLWIDTH A
        self.assertLess(bmp, astral)                       # code point order
        self.assertLess(V.order_key(astral), V.order_key(bmp))   # UTF-16 order, as JavaScript sorts
        doc = load("pdf-region.json")
        base = {k: v for k, v in by_id(doc["items"], "definition-1.1").items() if k != "coverage"}
        doc["items"] += [dict(base, id=f"item-{c}", id_source="declared", number=f"9.{n}", legacy_ids=[bmp, astral])
                         for n, c in ((1, bmp), (2, astral))]
        doc = V.canonicalize(doc)
        order = [i["id"] for i in doc["items"]]
        self.assertLess(order.index(f"item-{astral}"), order.index(f"item-{bmp}"))
        self.assertEqual(doc["items"][order.index(f"item-{bmp}")]["legacy_ids"], [astral, bmp])
        self.assertEqual(problems(doc), [])
        i, j = order.index(f"item-{astral}"), order.index(f"item-{bmp}")
        doc["items"][i], doc["items"][j] = doc["items"][j], doc["items"][i]
        self.assertProblem(doc, "is not sorted by id (UTF-16 code units)")

    def assertProblem(self, doc: dict, fragment: str) -> None:
        found = problems(doc)
        self.assertTrue(any(fragment in p for p in found), f"{fragment!r} not in {found}")

    def test_strings_are_escaped_as_json_stringify_does(self):
        self.assertEqual(V.canonical_dumps(["\u001f\n\t\"\\/é "]),
                         '[\n  "\\u001f\\n\\t\\"\\\\/é "\n]\n')
        self.assertEqual(V.canonical_dumps({"a": [], "b": {}, "c": None, "d": True}),
                         '{\n  "a": [],\n  "b": {},\n  "c": null,\n  "d": true\n}\n')

    def shuffled(self, doc: dict, seed: int) -> dict:
        rng = random.Random(seed)

        def mix(value):
            if isinstance(value, dict):
                keys = list(value)
                rng.shuffle(keys)
                return {k: mix(value[k]) for k in keys}
            if isinstance(value, list):
                return [mix(v) for v in value]
            return value
        out = mix(copy.deepcopy(doc))
        if isinstance(out["companion"].get("packages"), list):
            rng.shuffle(out["companion"]["packages"])
        for key in V.RECORD_ARRAYS:
            if key in out:
                rng.shuffle(out[key])
                for rec in out[key]:
                    for dotted in V.SET_FIELDS.get(key, ()):
                        values = V._get(rec, dotted)
                        if isinstance(values, list):
                            rng.shuffle(values)
                    for field_name, _key in V.KEYED_LISTS.get(key, ()):
                        if isinstance(rec.get(field_name), list):
                            rng.shuffle(rec[field_name])
        return out

    def test_a_shuffled_document_canonicalises_to_the_same_bytes(self):
        for name in VALID:
            original = (EXAMPLES / name).read_text(encoding="utf-8")
            for seed in range(5):
                with self.subTest(example=name, seed=seed):
                    messy = self.shuffled(V.loads(original), seed)
                    again = V.canonical_dumps(V.canonicalize(messy))
                    self.assertEqual(again, original)
                    self.assertEqual(V.canonical_dumps(V.canonicalize(V.loads(again))), again)

    def test_a_float_that_is_an_integer_is_written_without_a_point(self):
        doc = load("graph-profile.json")
        loc = by_id(doc["locations"], "definition-1.1@p007-2")
        loc["target"]["selector"][0]["rect"]["x0"] = 90.0
        self.assertEqual(V.canonical_dumps(doc), (EXAMPLES / "graph-profile.json").read_text(encoding="utf-8"))

    def test_selector_alternatives_keep_their_order(self):
        doc = load("pdf-region.json")
        loc = by_id(doc["locations"], "definition-1.1@p007")
        loc["target"]["selector"].reverse()
        before = [s["value"] for s in loc["target"]["selector"]]
        after = by_id(V.canonicalize(doc)["locations"], "definition-1.1@p007")["target"]["selector"]
        self.assertEqual([s["value"] for s in after], before)

    def test_unsorted_arrays_and_nested_sets_are_reported(self):
        doc = load("pdf-region.json")
        doc["items"].reverse()
        self.assertTrue(any("is not sorted by id" in p for p in problems(doc)))
        doc = load("graph-profile.json")
        doc["verdicts"][0]["resolution"]["commits"].reverse()
        self.assertTrue(any("resolution.commits: must be sorted" in p for p in problems(doc)))
        doc = load("graph-profile.json")
        doc["provenance"][1]["inputs"].reverse()
        self.assertTrue(any("inputs: must be sorted by path" in p for p in problems(doc)))


class TestTheInvariants(unittest.TestCase):
    """One broken copy of a valid example per rule, each failing for its reason."""

    def assertProblem(self, doc: dict, fragment: str, code: str | None = None) -> None:
        found = V.check(doc).problems
        hits = [p for p in found if fragment in str(p)]
        self.assertTrue(hits, f"{fragment!r} not in {[str(p) for p in found]}")
        if code is not None:
            self.assertEqual({p.code for p in hits}, {code}, hits)

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def item(self, doc: dict, rid: str) -> dict:
        return by_id(doc["items"], rid)

    # -- items -----------------------------------------------------------------
    def test_a_passage_needs_an_anchor_and_a_numbered_item_does_not(self):
        doc = load("web-passage.json")
        doc["locations"] = []
        self.assertProblem(doc, "passage 'passage-lead-definition' is anchored nowhere", "I4")
        doc = load("minimal.json")              # I4 is for passages: a number locates a numbered item
        del doc["items"][0]["pages"]
        self.assertValid(doc)
        doc["items"][0]["form"] = "passage"
        doc["items"][0]["title"] = "The lemma, as a passage"
        del doc["items"][0]["number"]
        doc["items"][0]["id_source"] = "declared"
        self.assertEqual(lines(doc), ["$.items[0]: passage 'lemma-1.2' is anchored nowhere: it needs a location, "
                                      "a quote or pages [I4]"])
        doc["items"][0]["quote"] = {"exact": "Lemma 1.2."}
        self.assertValid(doc)

    def test_a_passage_needs_a_title_and_takes_no_number_or_sub(self):
        doc = load("web-passage.json")
        del self.item(doc, "passage-lead-definition")["title"]
        self.assertProblem(doc, "missing required key 'title'")
        doc = load("web-passage.json")
        self.item(doc, "passage-lead-definition")["number"] = "1.2"
        self.assertProblem(doc, "(not)")
        doc = load("web-passage.json")
        self.item(doc, "passage-lead-definition")["sub"] = "ii"
        self.assertProblem(doc, "(not)")

    def test_form_is_a_required_discriminator(self):
        doc = load("pdf-region.json")
        del self.item(doc, "definition-1.1")["form"]
        self.assertProblem(doc, "missing required key 'form'")
        doc = load("pdf-region.json")
        self.item(doc, "definition-1.1")["form"] = "passage"
        self.assertTrue(problems(doc))

    def test_many_items_may_share_a_page(self):
        self.assertValid(load("mixed.json"))

    def test_old_coverage_values_and_cluster_fallback_are_refused(self):
        for value in ("cluster_only", "partial"):
            doc = load("graph-profile.json")
            self.item(doc, "remark-1.3")["coverage"] = value
            with self.subTest(value=value):
                self.assertProblem(doc, "is not one of", "SCHEMA")
        doc = load("graph-profile.json")
        self.item(doc, "remark-1.3")["cluster_fallback"] = True
        self.assertEqual(lines(doc), ["$.items[1].cluster_fallback: is not an allowed key here [SCHEMA]"])

    def test_numbered_identity_is_unique(self):
        doc = load("pdf-region.json")
        doc["items"].append(dict(self.item(doc, "definition-1.1"), id="definition-1.1-again",
                                 id_source="declared"))
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "the same numbered item as", "I6")

    def test_item_relations_resolve_and_are_not_reflexive(self):
        doc = load("mixed.json")
        self.item(doc, "passage-boxes-motivation")["relations"]["near"] = ["passage-boxes-motivation"]
        self.assertProblem(doc, "an item is not related to itself", "I3")
        doc = load("mixed.json")
        self.item(doc, "passage-boxes-motivation")["relations"]["near"] = ["definition-9.9"]
        self.assertProblem(doc, "'definition-9.9' is not an id in items[]", "I3")

    def test_sub_admits_primes_and_the_label_id_carries_them(self):
        """5.2: a part the source numbers (b'), (b''), (f') is sub b', b'', f'; the id copies it verbatim."""
        doc = load("minimal.json")
        item, link = doc["items"][0], doc["links"][0]
        for sub in ("ii", "3", "ix,x", "b'", "f''", "a'-c'", "1.2'", "b',c'"):
            item["sub"] = sub
            item["id"] = link["item"] = item_id = f"lemma-1.2-{sub}"
            link["sub"], link["id"] = sub, f"{item_id}/key/Notes.Box.volume_nonneg"
            with self.subTest(sub=sub):
                self.assertValid(doc)
                self.assertEqual(ids.item_label_id("Lemma", "1.2", sub), item_id)
        for bad in ("(b')", "'b", "b'c", "b' ", "b\u2032", "b'.", "''"):   # ASCII U+0027, after a part
            item["sub"] = link["sub"] = bad
            item["id"] = link["item"] = "lemma-1.2"
            link["id"] = "lemma-1.2/key/Notes.Box.volume_nonneg"
            with self.subTest(sub=bad):
                self.assertEqual([(p.code, p.path) for p in V.check(doc).problems],
                                 [("SCHEMA", "$.items[0].sub"), ("SCHEMA", "$.links[0].sub")])
        item["sub"] = link["sub"] = "b'"
        item["id"] = link["item"] = "lemma-1.2-b"
        link["id"] = "lemma-1.2-b/key/Notes.Box.volume_nonneg"
        self.assertEqual(lines(doc), ["$.items[0].id: a label id is <kind>-<number>[-<sub>], here \"lemma-1.2-b'\" "
                                      "[I12]"])

    # -- item ids (I12) --------------------------------------------------------
    def test_a_label_id_is_kind_and_number(self):
        doc = load("pdf-region.json")
        doc["items"][0]["id_source"] = "label"
        item = by_id(doc["items"], "definition-1.1")
        item["number"] = "1.9"
        self.assertProblem(doc, "a label id is <kind>-<number>[-<sub>], here 'definition-1.9'", "I12")

    def test_a_quote_hash_id_is_the_quote_hash(self):
        doc = load("web-passage.json")
        item = next(i for i in doc["items"] if i["id_source"] == "quote_hash")
        self.assertEqual(item["id"], ids.passage_quote_id(item["quote"]["exact"]))
        item["quote"]["exact"] += " again"
        self.assertProblem(doc, "a quote_hash id is passage-<8 hex of the normalised quote> (item.quote)", "I12")

    def test_a_quote_hash_id_may_come_from_the_first_locations_quote(self):
        doc = load("site-pages.json")
        item = next(i for i in doc["items"] if i["id_source"] == "quote_hash")
        self.assertNotIn("quote", item)
        loc = by_id(doc["locations"], f"{item['id']}@p022")
        quote = loc["target"]["selector"][0]["refinedBy"]
        self.assertEqual(item["id"], ids.passage_quote_id(quote["exact"]))
        quote["exact"] = "every  null set is contained in a Borel null set"   # the normaliser collapses it
        self.assertValid(doc)
        quote["exact"] += " again"
        self.assertProblem(doc, f"(the quote of location '{item['id']}@p022')")
        loc["target"]["selector"][0] = {"type": "FragmentSelector", "conformsTo": vocab.CONFORMS_TO_PDF,
                                        "value": "page=22"}
        self.assertProblem(doc, "a quote_hash id needs item.quote, or a TextQuoteSelector on the item's "
                                "first location")

    def test_the_same_quote_twice_is_one_passage_or_a_duplicate_id(self):
        doc = load("site-pages.json")
        item = next(i for i in doc["items"] if i["id_source"] == "quote_hash")
        doc["items"].append(dict(item, title="Another title for the same passage"))
        self.assertProblem(doc, f"duplicate id {item['id']!r} in items[]", "I1")

    def test_a_page_title_hash_id_needs_a_printed_page_and_no_quote(self):
        doc = load("pdf-region.json")
        item = next(i for i in doc["items"] if i["id_source"] == "page_title_hash")
        self.assertEqual(item["id"], ids.passage_page_id(item["pages"]["first"], item["title"]))
        item["title"] += "!"
        self.assertProblem(doc, "a page_title_hash id is passage-p<printed page>-<8 hex")
        doc = load("pdf-region.json")
        item = next(i for i in doc["items"] if i["id_source"] == "page_title_hash")
        item["quote"] = {"exact": "a quote"}
        self.assertProblem(doc, "takes the quote_hash id")
        doc = load("pdf-region.json")
        item = next(i for i in doc["items"] if i["id_source"] == "page_title_hash")
        item["pages"] = {"first": 10, "basis": "physical"}
        self.assertValid(doc)
        del doc["sources"][0]["printed_page_offset"]
        self.assertProblem(doc, "page_title_hash needs a printed page")

    def test_a_declared_item_id_may_not_take_a_mechanical_shape(self):
        doc = load("mixed.json")
        doc = json.loads(json.dumps(doc).replace("passage-remark-unions", "passage-0123abcd"))
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "has the shape of a mechanical passage id", "I12")

    # -- locations and selectors (I7) -------------------------------------------
    def test_a_region_must_agree_with_the_page_it_refines(self):
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][0]["refinedBy"]["page"] = 8
        self.assertProblem(doc, "disagrees with the refined page=7", "I7")

    def test_a_region_stays_on_its_page(self):
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = 1.5
        self.assertProblem(doc, "coordinates must lie in [0, 1] for units normalized", "I7")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][0]["refinedBy"]["rect"]["x1"] = 1.0
        self.assertValid(doc)
        doc = load("graph-profile.json")
        by_id(doc["locations"], "definition-1.1@p007-2")["target"]["selector"][0]["rect"]["x1"] = 700
        self.assertProblem(doc, "the rect leaves the 612 x 792 pt page", "I7")

    def test_page_beyond_the_source(self):
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][1]["value"] = "page=41"
        self.assertProblem(doc, "page=41 is past the source's 40 physical pages", "I7")
        del doc["sources"][0]["physical_page_count"]   # bounded only when the source gives a count
        self.assertFalse(any("is past the source" in p for p in lines(doc)), lines(doc))

    def test_location_pages_agree_with_the_selectors(self):
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["pages"] = {"first": 8, "basis": "physical"}
        self.assertProblem(doc, "the selectors name physical page(s) [7], outside 8..8", "I7")
        doc = load("web-passage.json")
        doc["locations"][0]["pages"] = {"first": 1, "basis": "physical"}
        self.assertProblem(doc, "pages are for a pdf source", "I6")

    def test_text_layer_extractor_and_version_come_together(self):
        doc = load("pdf-region.json")
        del doc["sources"][0]["text_layer"]["version"]
        self.assertProblem(doc, "$.sources[0].text_layer: is missing required key 'version'")
        doc = load("tex-lines.json")
        doc["sources"][0]["text_layer"]["version"] = "1.0"
        self.assertProblem(doc, "$.sources[0].text_layer: is missing required key 'extractor'")
        doc = load("pdf-region.json")
        del doc["sources"][0]["text_layer"]["extractor"]
        del doc["sources"][0]["text_layer"]["version"]
        self.assertValid(doc)                          # both absent is fine: no offsets to tie to

    def test_a_selector_the_source_kind_cannot_use(self):
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"].append(
            {"type": "CssSelector", "value": "p"})
        self.assertProblem(doc, "CssSelector does not apply to a pdf source", "I7")
        doc = load("tex-lines.json")
        doc["locations"][0]["target"]["selector"][0]["conformsTo"] = vocab.CONFORMS_TO_PDF
        self.assertProblem(doc, "a tex source takes http://tools.ietf.org/rfc/rfc5147", "I7")
        doc = load("pdf-region.json")
        by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][1]["conformsTo"] = \
            vocab.CONFORMS_TO_HTML
        self.assertProblem(doc, "a pdf source takes http://tools.ietf.org/rfc/rfc3778 or "
                                "http://tools.ietf.org/rfc/rfc8118", "I7")
        doc = load("tex-lines.json")
        doc["locations"][0]["target"]["selector"].append(
            {"type": "PdfRegionSelector", "page": 1, "rect": {"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2},
             "coordinate_space": {"origin": "top_left", "units": "normalized", "x_axis": "right",
                                  "y_axis": "down", "page_box": "CropBox"}})
        self.assertProblem(doc, "PdfRegionSelector does not apply to a tex source", "I7")

    def test_conforms_to_is_open_with_a_warning(self):
        doc = load("tex-lines.json")
        sel = doc["locations"][0]["target"]["selector"][0]
        sel["conformsTo"] = "https://example.org/some-grammar"
        sel["value"] = "anything at all"
        self.assertValid(doc)
        self.assertTrue(any("is not an IRI this checker knows" in w for w in warnings(doc)))
        del sel["conformsTo"]
        self.assertValid(doc)
        self.assertTrue(any("absent (W3C: SHOULD have one)" in w for w in warnings(doc)))

    def test_rfc3778_is_a_synonym_and_rfc3236_names_html_ids(self):
        doc = load("pdf-region.json")
        for loc in doc["locations"]:
            for sel in loc["target"]["selector"]:
                if sel.get("conformsTo") == vocab.CONFORMS_TO_PDF:
                    sel["conformsTo"] = vocab.CONFORMS_TO_PDF_RFC3778
        self.assertValid(doc)
        doc = load("site-pages.json")
        inner = by_id(doc["locations"], "Notes.sum_le@site")["target"]["selector"][0]["refinedBy"]
        self.assertEqual(inner["conformsTo"], vocab.CONFORMS_TO_HTML)
        inner["value"] = "two words"
        self.assertProblem(doc, "is not an HTML element id", "I7")

    def test_zoom_takes_one_or_three_numbers(self):
        doc = load("pdf-region.json")
        sel = by_id(doc["locations"], "definition-1.1@p007")["target"]["selector"][1]
        for value in ("page=7&zoom=100", "page=7&zoom=100,0,0"):
            sel["value"] = value
            self.assertValid(doc)
        sel["value"] = "page=7&zoom=100,0"
        self.assertProblem(doc, "zoom= takes 1 or 3 numbers", "I7")

    def test_media_fragments_take_time_as_well_as_xywh(self):
        doc = load("other-media.json")
        sel = by_id(doc["locations"], "passage-video-proof-sketch@t")["target"]["selector"][0]
        for value in ("t=30,60", "t=npt:10,20", "t=,20", "t=10", "t=0:02:00,121.5", "t=npt:120,0:02:01.5",
                      "xywh=0,0,10,10", "track=audio&t=5"):
            sel["value"] = value
            with self.subTest(value=value):
                self.assertValid(doc)
        for value, fragment in (("t=60,30", "the start must be before the end"),
                                ("t=npt:1:30", "is not a Media Fragments t= value"),
                                ("xywh=0,0,0,10", "width and height must be positive"),
                                ("xywh=1.5,0,10,10", "is not a Media Fragments xywh= value")):
            sel["value"] = value
            with self.subTest(value=value):
                self.assertProblem(doc, fragment, "I7")
        for value, fragment in (("t=1&t=2", "appears more than once; the last one is used"),
                                ("frame=3&t=1", "is not a Media Fragments dimension")):
            sel["value"] = value
            with self.subTest(value=value):
                self.assertValid(doc)
                self.assertTrue(any(fragment in w for w in warnings(doc)), warnings(doc))

    def test_a_site_names_its_pages(self):
        doc = load("site-pages.json")
        loc = by_id(doc["locations"], "Notes.sum_le@site")
        loc["target"]["selector"] = [loc["target"]["selector"][0]["refinedBy"]]
        self.assertProblem(doc, "is a site: each alternative names its page with a SitePageSelector", "I7")
        doc = load("web-passage.json")
        doc["locations"][0]["target"]["selector"].append({"type": "SitePageSelector", "path": "index.html"})
        self.assertProblem(doc, "a SitePageSelector names a page of a site", "I7")
        doc = load("site-pages.json")
        loc = by_id(doc["locations"], "Notes.sum_le@site")
        loc["target"]["selector"][0]["refinedBy"] = {"type": "SitePageSelector", "path": "a/"}
        self.assertProblem(doc, "a SitePageSelector is a top-level alternative, never a refinement", "I7")

    def test_a_location_shows_items_of_its_own_source(self):
        doc = load("mixed.json")
        loc = by_id(doc["locations"], "definition-1.1@p007")
        errata = next(i["id"] for i in doc["items"] if i["source"] == "notes-errata")
        loc["items"] = sorted(loc["items"] + [errata])
        self.assertProblem(doc, "a location shows items of its own source 'notes-pdf'", "I7")

    def test_a_location_with_no_items_is_named_by_something(self):
        doc = load("pdf-region.json")
        link = next(l for l in doc["links"] if "locations" in l)
        del link["locations"]
        self.assertProblem(doc, "a location shows at least one item, anchors a declaration, or is named by a link",
                           "I7")

    def test_an_anchor_shows_lean_text(self):
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box")["anchors"] = ["definition-1.1@p007"]
        self.assertProblem(doc, "an anchor shows the declaration's own text, on a lean, web, or other "
                                "text/html source; 'notes-pdf' is pdf", "I7")

    def test_an_anchor_may_sit_on_an_other_text_source_but_not_on_video(self):
        doc = load("other-media.json")
        md = next(s for s in doc["sources"] if s.get("media_type") == "text/markdown")
        loc = next(l for l in doc["locations"] if l["target"]["source"] == md["id"])
        doc["declarations"][0]["anchors"] = [loc["id"]]
        self.assertValid(doc)
        video = next(s for s in doc["sources"] if s.get("media_type") == "video/mp4")
        loc = next(l for l in doc["locations"] if l["target"]["source"] == video["id"])
        doc["declarations"][0]["anchors"] = [loc["id"]]
        self.assertProblem(doc, "is other (video/mp4)", "I7")

    def test_a_link_location_is_on_the_items_source(self):
        doc = load("mixed.json")
        errata = next(i for i in doc["items"] if i["source"] == "notes-errata")
        doc["links"].append({"id": f"{errata['id']}/support/Notes.Box", "item": errata["id"], "declaration": "Notes.Box",
                             "role": "support", "provenance": "prov-curation",
                             "locations": ["definition-1.1@p007"]})
        errata["coverage"] = "support_only"
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "not on the item's source 'notes-errata'", "I7")

    # -- sources -------------------------------------------------------------------
    def test_a_web_source_is_pinned_by_sha256_or_revision(self):
        doc = load("web-passage.json")
        del doc["sources"][0]["revision"]
        self.assertProblem(doc, "matches none of the allowed alternatives (anyOf)")
        doc = load("site-pages.json")
        web = next(s for s in doc["sources"] if s["kind"] == "web")
        self.assertNotIn("url", web)
        self.assertValid(doc)

    def test_page_fields_and_site_scope_belong_to_their_kinds(self):
        doc = load("web-passage.json")
        doc["sources"][0]["page_size"] = {"width_pt": 612, "height_pt": 792}
        self.assertProblem(doc, "(not)")
        doc = load("pdf-region.json")
        doc["sources"][0]["scope"] = "site"
        self.assertProblem(doc, "must be \"web\"")
        doc = load("other-media.json")
        del doc["sources"][0]["media_type"]
        self.assertProblem(doc, "missing required key 'media_type'")
        doc = load("other-media.json")
        video = next(s for s in doc["sources"] if s.get("media_type") == "video/mp4")
        video["page_size"] = {"width_pt": 612, "height_pt": 792}
        self.assertProblem(doc, "page_size describe PDF pages", "I6")
        doc = load("pdf-region.json")
        doc["sources"][0]["page_sizes"] = [{"first": 3, "last": 5, "width_pt": 500, "height_pt": 700},
                                           {"first": 5, "last": 41, "width_pt": 500, "height_pt": 700}]
        found = problems(doc)
        self.assertTrue(any("page_sizes ranges overlap" in p for p in found), found)
        self.assertTrue(any("page 41 is past the source's 40 physical pages" in p for p in found), found)

    def test_a_site_sha256_is_the_sha256_of_its_page_manifest(self):
        pages = [{"path": "b/index.html", "sha256": "b" * 64}, {"path": "a.html", "sha256": "a" * 64}]
        manifest = f"{'a' * 64}  a.html\n{'b' * 64}  b/index.html\n"
        self.assertEqual(V.site_sha256(pages), hashlib.sha256(manifest.encode("utf-8")).hexdigest())
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        self.assertEqual(site["sha256"], V.site_sha256(site["page_hashes"]))
        site["page_hashes"][0]["sha256"] = "0" * 64
        self.assertProblem(doc, "a site's sha256 is the sha256 of its page manifest", "I6")
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        site["page_hashes"] = [p for p in site["page_hashes"] if p["path"] != "Notes/Section_2/index.html"]
        site["sha256"] = V.site_sha256(site["page_hashes"])
        self.assertProblem(doc, "'Notes/Section_2/index.html' is not a page in 'literate-site''s page_hashes", "I7")
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        site["page_hashes"].reverse()
        self.assertProblem(doc, "page_hashes: must be sorted by path, one entry each", "I2")
        doc = load("pdf-region.json")
        doc["sources"][0]["page_hashes"] = [{"path": "a.html", "sha256": "a" * 64}]
        self.assertProblem(doc, "(not)")

    def test_a_site_with_a_sha256_carries_page_hashes(self):
        """The site's sha256 is defined over the listed pages, so the list is required with it;
        a site pinned by revision alone needs no list."""
        doc = load("site-pages.json")
        site = by_id(doc["sources"], "literate-site")
        del site["page_hashes"]
        self.assertEqual(lines(doc), ["$.sources[1]: is missing required key 'page_hashes' [SCHEMA]"])
        del site["sha256"]
        self.assertValid(doc)

    def test_companion_commit_is_a_full_sha(self):
        doc = load("mixed.json")
        doc["companion"]["commit"] = doc["companion"]["commit"][:7]
        self.assertProblem(doc, "$.companion.commit", "SCHEMA")

    # -- URLs: no core invariant (I10 is retired); the external-urls lint (L1) ---
    def lint(self, doc: dict) -> list[str]:
        return lines(doc, lints=("external-urls",))

    def test_a_url_outside_sources_and_destinations_is_not_a_problem_by_default(self):
        doc = load("mixed.json")
        doc["provenance"][0]["note"] = "see https://example.org/run"
        self.item(doc, "passage-boxes-motivation")["title"] = "see http://example.org"
        self.assertValid(doc)
        doc = load("mixed.json")
        doc["companion"]["repo"] = "https://git.example.org/x/y"
        self.assertProblem(doc, "$.companion.repo", "SCHEMA")     # the schema: host/org/name, no scheme

    def test_the_external_urls_lint_flags_urls_outside_the_exempt_paths(self):
        doc = load("mixed.json")
        self.assertEqual(self.lint(doc), [])
        doc["provenance"][0]["note"] = "see https://example.org/run"
        self.item(doc, "passage-boxes-motivation")["title"] = "see HTTP://EXAMPLE.ORG"
        found = self.lint(doc)
        self.assertEqual(len(found), 2, found)
        self.assertIn("$.items[", found[0])                   # document order: items before provenance
        self.assertIn("'HTTP://EXAMPLE.ORG'", found[0])
        self.assertTrue(found[1].startswith("$.provenance[0].note: contains 'https://example.org/run', a URL-like "
                                            "reference; the external-urls lint allows a URL only in"), found[1])
        self.assertTrue(all(f.endswith(" [L1]") for f in found))
        self.assertEqual(problems(doc), [], "a lint finding is not a problem unless the lint is asked for")
        with self.assertRaises(ValueError):
            V.check(doc, lints=("no-such-lint",))
        self.assertEqual(V.LINTS, frozenset({"external-urls"}))

    def test_the_lint_sees_every_scheme_and_the_prefixes_at_the_start(self):
        """``<scheme>://`` anywhere; ``//host`` and the four prefixes only at the start of the string."""
        doc = load("pdf-region.json")
        for value, flagged in (("ftp://files.example.org/x", True), ("//evil.example/x", True),
                               ("see //evil.example/x", False), ("javascript:alert(1)", True),
                               ("data:text/html,hi", True), ("mailto:a@example.org", True),
                               ("file:///etc/passwd", True), ("git+ssh://host/repo", True),
                               ("see git+ssh://host/repo", True), ("https:evil.example", False),
                               ("a/b", False), ("2 // 3", False), ("x=1&y=2", False),
                               ("JavaScript:void(0)", True), ("data-set: 3", False), ("see mailto:a@b", False)):
            doc["x_meta"] = value
            with self.subTest(value=value):
                self.assertEqual(bool(self.lint(doc)), flagged, self.lint(doc))

    def test_the_lint_scans_x_values_at_any_depth_and_keys(self):
        doc = load("mixed.json")
        index, prov = next((i, p) for i, p in enumerate(doc["provenance"]) if any(k.startswith("x_") for k in p))
        prov["x_curation_pass"] = {"log": "https://example.org/run/2"}
        self.assertEqual(self.lint(doc), [f"$.provenance[{index}].x_curation_pass.log: contains "
                                          "'https://example.org/run/2', a URL-like reference; " + V._L1_RULE
                                          + " [L1]"])
        doc = load("mixed.json")
        doc["companion"]["x_build"]["log"] = "http://example.org/build"
        self.assertIn("$.companion.x_build.log: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["x_elsewhere"] = [{"deep": [["https://example.org/"]]}]
        self.assertIn("$.x_elsewhere[0].deep[0][0]: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["x_meta"] = {"https://evil.example/": 1}
        (found,) = self.lint(doc)
        self.assertTrue(found.startswith('$.x_meta["https://evil.example/"]: the key \'https://evil.example/\' '
                                         'contains '), found)

    def test_the_lints_exemptions_are_by_path_not_by_key_name(self):
        doc = load("mixed.json")
        errata = next(i for i in doc["items"] if i["source"] == "notes-errata")
        errata["quote"]["prefix"] = "from http://notes.example.org: "
        sel = by_id(doc["locations"], "passage-remark-unions@p007")["target"]["selector"][1]["refinedBy"]
        self.assertEqual(sel["type"], "TextQuoteSelector")
        sel["suffix"] = " at https://example.org/x"
        doc["$schema"] = SCHEMA_ID
        doc["sources"][1]["alternate_urls"] = ["https://mirror.example.org/notes.pdf"]
        self.assertValid(doc)
        self.assertEqual(self.lint(doc), [])
        # the same key names elsewhere are not exempt
        doc["x_meta"] = {"$schema": "https://example.org/x"}
        self.assertIn("$.x_meta.$schema: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["items"][0]["x_meta"] = {"type": "TextQuoteSelector", "exact": "https://evil.example/a"}
        self.assertIn(".x_meta.exact: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["x_meta"] = {"conformsTo": "https://evil.example/track"}
        self.assertIn("$.x_meta.conformsTo: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["items"][0]["x_meta"] = {"quote": {"exact": "https://evil.example"}}
        self.assertIn(".x_meta.quote.exact: contains", self.lint(doc)[0])
        doc = load("mixed.json")
        doc["x_meta"] = {"url": "https://evil.example", "href": "https://evil.example"}
        self.assertEqual(len(self.lint(doc)), 2)

    def test_the_cli_runs_a_lint_only_when_asked(self):
        doc = load("mixed.json")
        doc["provenance"][0]["note"] = "see https://example.org/run"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                self.assertEqual(V.main([str(path)]), 0)
                self.assertEqual(V.main([str(path), "--lint", "external-urls"]), 1)
            self.assertIn(f"{path}: $.provenance[0].note: contains 'https://example.org/run', a URL-like",
                          out.getvalue())
            self.assertTrue(out.getvalue().rstrip().endswith(" [L1]"))
            with redirect_stdout(out), redirect_stderr(err), self.assertRaises(SystemExit):
                V.main([str(path), "--lint", "no-such-lint"])
            self.assertIn("invalid choice", err.getvalue())

    # -- declarations (I8) -----------------------------------------------------------
    def test_a_hash_id_must_match_its_statement(self):
        doc = load("pdf-region.json")
        decl = next(d for d in doc["declarations"] if d["id_source"] == "statement_hash")
        decl["statement_sha256"] = "0" * 64
        del decl["signature"]
        self.assertProblem(doc, "is not the first 12 digits of statement_sha256", "I8")

    def test_a_signature_is_the_display_form_and_hashes_through_the_hash_form(self):
        doc = load("pdf-region.json")
        decl = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
        signature = decl["signature"]
        self.assertEqual(ids.normalize_statement(signature), signature)
        self.assertEqual(decl["statement_sha256"], ids.statement_sha256(signature))
        self.assertEqual(decl["statement_sha256"],
                         hashlib.sha256(ids.hash_form(signature).encode("utf-8")).hexdigest())
        decl["signature"] += " "
        self.assertProblem(doc, "must be normalised", "I8")
        decl["signature"] = signature + " extra"
        self.assertProblem(doc, "its sha256 is not statement_sha256", "I8")
        decl["signature"] = signature.replace(" : ", ":")          # another spacing: the same hash form
        self.assertEqual(ids.statement_sha256(decl["signature"]), decl["statement_sha256"])
        self.assertEqual(lines(doc), [])

    def test_a_signature_carries_no_comment(self):
        doc = load("pdf-region.json")
        decl = by_id(doc["declarations"], "Notes.Box.volume_nonneg")
        decl["signature"] += " -- a comment"
        decl["statement_sha256"] = ids.statement_sha256(decl["signature"])
        self.assertProblem(doc, "must be normalised: comments removed", "I8")
        decl["signature"] = decl["signature"].replace(" -- a comment", " /- a block -/ ")
        self.assertProblem(doc, "must be normalised: comments removed", "I8")

    def test_the_example_ids_are_the_hash_rule(self):
        for name, rid in (("pdf-region.json", PDF_EXAMPLE), ("graph-profile.json", GRAPH_EXAMPLE),
                          ("site-pages.json", SITE_INSTANCE)):
            with self.subTest(example=name):
                decl = by_id(load(name)["declarations"], rid)
                self.assertEqual(decl["id"], ids.anonymous_id(decl["kind"], decl["statement_sha256"]))
                self.assertEqual(decl["statement_sha256"], ids.statement_sha256(decl["signature"]))
        self.assertEqual(ids.private_id("Notes.Basic", "Notes.Box.volume_aux"),
                         "private:Notes.Basic:Notes.Box.volume_aux")

    def test_an_ordinal_needs_a_changelog_record(self):
        doc = load("graph-profile.json")
        doc["changelog"] = [c for c in doc["changelog"] if c["event"] != "ordinal_assigned"]
        self.assertProblem(doc, "carries an ordinal, which is positional", "I8")

    def test_the_latest_ordinal_record_names_the_declarations_file(self):
        doc = load("graph-profile.json")
        rid = GRAPH_EXAMPLE + "~2"
        record = next(c for c in doc["changelog"] if c["subject"] == rid)
        self.assertEqual(record["file"], by_id(doc["declarations"], rid)["file"])
        by_id(doc["declarations"], rid)["file"] = "Notes/Unions.lean"      # a copy elsewhere took ~2
        by_id(doc["declarations"], rid)["module"] = "Notes.Unions"
        self.assertProblem(doc, f"the latest ordinal_assigned record gives {rid!r} to a "
                                f"declaration in 'Notes/Basic.lean', and it is in 'Notes/Unions.lean'", "I8")
        doc["changelog"].append(dict(record, at="2026-09-05", file="Notes/Unions.lean",
                                     id=f"2026-09-05/ordinal/{rid}"))
        self.assertValid(V.canonicalize(doc))
        doc["changelog"][-1]["at"] = record["at"]
        self.assertProblem(V.canonicalize(doc), "name different files", "I8")

    def test_an_ordinal_record_outlives_its_retired_id(self):
        doc = load("graph-profile.json")
        self.assertValid(doc)                  # ~3 is recorded, then retired
        doc = load("graph-profile.json")
        doc["changelog"] = [c for c in doc["changelog"]
                            if not (c["event"] == "retired" and c["subject"] == GRAPH_EXAMPLE + "~3")]
        self.assertProblem(doc, "is not a live declaration id, and no later changelog entry retires or renames it",
                           "I9")
        doc = load("graph-profile.json")
        retire = next(c for c in doc["changelog"] if c["event"] == "retired")
        retire["at"] = "2026-08-01"            # retired before it was recorded: not later
        self.assertProblem(doc, "no later changelog entry retires or renames it", "I9")

    def test_an_impossible_changelog_date_is_a_problem_not_a_crash(self):
        doc = load("graph-profile.json")
        rec = next(c for c in doc["changelog"] if c["event"] == "ordinal_assigned")
        rec["at"] = "2026-02-30"
        self.assertProblem(doc, "is not a calendar date or UTC instant", "I9")
        rec["at"] = "2026-09-05T25:00:00Z"
        self.assertProblem(doc, "is not a calendar date or UTC instant", "I9")

    def test_a_field_namespace_is_checked_without_a_parent_name(self):
        doc = load("graph-profile.json")
        field = next(d for d in doc["declarations"] if d.get("kind") == "field")
        parent = by_id(doc["declarations"], field["parent"])
        parent.pop("name", None)
        field["namespace"] = "Totally.Wrong"
        self.assertProblem(doc, "namespace is its parent's full name (its name)", "I8")

    def test_a_passage_with_a_location_quote_may_not_take_a_page_title_hash_id(self):
        doc = load("site-pages.json")
        item = by_id(doc["items"], "passage-2caa5bb1")      # its quote comes from its location
        item["id_source"] = "page_title_hash"
        self.assertProblem(doc, "a passage with a quote (", "I12")

    def test_a_declared_id_allows_capitals_but_not_a_hash_shape(self):
        doc = load("graph-profile.json")
        self.assertIn("example:Unions-of-boxes-are-elementary", {d["id"] for d in doc["declarations"]})
        doc = json.loads(json.dumps(doc).replace("example:Unions-of-boxes-are-elementary", "example:0123456789ab"))
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "a slug of 12 hex digits is reserved for statement hashes", "I8")

    def test_a_private_id_is_module_and_name(self):
        doc = load("pdf-region.json")
        decl = next(d for d in doc["declarations"] if d["id_source"] == "private")
        decl["name"] = "Notes.Box.other"
        self.assertProblem(doc, "a private declaration's id is private:<module>:<name>", "I8")

    def test_a_field_has_a_structure_parent(self):
        doc = load("pdf-region.json")
        field = by_id(doc["declarations"], "Notes.Box.lower")
        del field["parent"]
        self.assertProblem(doc, "missing required key 'parent'", "SCHEMA")
        field["parent"] = "Notes.Box.volume_nonneg"
        self.assertProblem(doc, "a field's parent is a structure or class, not a theorem", "I3")
        doc = load("pdf-region.json")
        by_id(doc["declarations"], "Notes.Box.volume_nonneg")["parent"] = "Notes.Box"
        self.assertProblem(doc, "(not)", "SCHEMA")

    def test_an_unlocated_declared_id_has_no_line_or_statement(self):
        doc = load("graph-profile.json")
        decl = next(d for d in doc["declarations"] if d.get("unlocated"))
        decl["line"] = 3
        self.assertProblem(doc, "(not)", "SCHEMA")
        doc = load("graph-profile.json")
        decl = next(d for d in doc["declarations"] if d.get("unlocated"))
        decl["id_source"] = "statement_hash"
        self.assertTrue(problems(doc))

    # -- links, memberships, artifacts, verdicts --------------------------------
    def test_an_unknown_relation_warns_and_part_is_core(self):
        doc = load("web-passage.json")
        doc["links"][0]["relation"] = "analogy"
        self.assertValid(doc)
        self.assertTrue(any("outside the documented core" in w for w in warnings(doc)))
        self.assertEqual([w.code for w in V.check(doc).warnings], ["W-RELATION"])
        doc["links"][0]["relation"] = "part"
        self.assertEqual(warnings(doc), [])

    def test_an_unattributed_declaration_has_no_link(self):
        doc = load("mixed.json")
        doc["links"].append({"id": "definition-1.1/support/Notes.simp_volume", "item": "definition-1.1",
                             "declaration": "Notes.simp_volume", "role": "support",
                             "provenance": "prov-curation"})
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "'Notes.simp_volume' is linked at", "I13")

    def test_memberships_and_destinations_resolve(self):
        doc = load("graph-profile.json")
        member = next(m for m in doc["memberships"] if "declaration" in m)
        member["artifact"] = "module_doc:Nowhere"
        del member["declaration"]
        self.assertProblem(doc, "'module_doc:Nowhere' is not an id in artifacts[]", "I3")
        doc = load("graph-profile.json")
        doc["memberships"].append(dict(doc["memberships"][0], id="zz-duplicate"))
        self.assertProblem(doc, "repeats the membership", "I3")
        doc = load("graph-profile.json")
        dest = next(d for d in doc["destinations"] if "artifact" in d)
        dest["declaration"] = "Notes.Box"
        self.assertProblem(doc, "must match exactly one alternative (oneOf)", "SCHEMA")

    def test_a_verdict_location_must_show_its_item(self):
        doc = load("mixed.json")
        doc["verdicts"][0]["locations"] = ["definition-1.1@p007", "passage-remark-unions@p007"]
        self.assertProblem(doc, "does not show item 'definition-1.1'", "I3")

    def test_a_fixed_verdict_has_a_fixed_resolution(self):
        doc = load("mixed.json")
        doc["verdicts"][0]["resolution"] = {"state": "open"}
        self.assertProblem(doc, "status is fixed, so the resolution must be fixed", "I3")
        doc = load("mixed.json")
        del doc["verdicts"][0]["resolution"]
        self.assertProblem(doc, "$.verdicts[0].status: status is fixed, so the resolution must be fixed "
                                "(a verdict without a resolution is open)", "I3")

    def test_a_verdict_without_a_resolution_is_open(self):
        doc = load("mixed.json")
        verdict = doc["verdicts"][0]
        del verdict["resolution"]
        verdict["status"] = "unconfirmed"
        self.assertValid(doc)

    def test_an_unknown_verdict_field_is_refused_and_an_x_key_is_not(self):
        """A verdict carries the format's own fields only (the 1.0.0 fields that recorded one tool's verdicts
        are gone, see the CHANGELOG); what a producer adds goes under ``x_``."""
        for key, value in (("verdict_source", "tool"), ("finding", "content"), ("finding_refs", ["0" * 64]),
                           ("pinned_at", "0" * 40)):
            doc = load("mixed.json")
            doc["verdicts"][0][key] = value
            with self.subTest(field=key):
                self.assertEqual(lines(doc), [f"$.verdicts[0].{key}: is not an allowed key here [SCHEMA]"])
            doc["verdicts"][0]["x_" + key] = doc["verdicts"][0].pop(key)
            self.assertValid(doc)

    def test_a_link_confidence_is_refused(self):
        doc = load("web-passage.json")
        doc["links"][2]["confidence"] = 0.9
        self.assertEqual(lines(doc), ["$.links[2].confidence: is not an allowed key here [SCHEMA]"])

    def test_a_field_namespace_is_its_parents_full_name(self):
        doc = load("web-passage.json")
        field = by_id(doc["declarations"], "Ideal.IsPrime.ne_top'")
        self.assertEqual(field["namespace"] + ".ne_top'", field["name"])
        field["namespace"] = "Ideal"
        self.assertProblem(doc, "a projection's namespace is its parent's full name (its name), 'Ideal.IsPrime'",
                           "I8")

    def test_an_input_names_a_file_or_a_source(self):
        doc = load("site-pages.json")
        prov = by_id(doc["provenance"], "prov-text")
        self.assertEqual(prov["inputs"], [{"source": "book-pdf"}])
        prov["inputs"] = [{"source": "no-such-source"}]
        self.assertProblem(doc, "'no-such-source' is not an id in sources[]", "I3")
        prov["inputs"] = [{"source": "book-pdf", "path": "book.pdf", "sha256": "0" * 64}]
        self.assertProblem(doc, "(oneOf)", "SCHEMA")
        prov["inputs"] = [{"source": "book-pdf"}, {"path": "_site/xref.json", "sha256": "0" * 64}]
        self.assertProblem(doc, "inputs: must be sorted by path, then source, one entry each", "I2")
        prov["inputs"].reverse()
        self.assertValid(doc)

    def test_resolution_replacements_resolve(self):
        doc = load("graph-profile.json")
        doc["verdicts"][0]["resolution"]["replaced_by"].append("Notes.Zz")
        self.assertProblem(doc, "'Notes.Zz' is not an id in declarations[]", "I3")

    # -- changelog (I9) ------------------------------------------------------------
    def test_a_retired_id_is_never_reused(self):
        doc = load("mixed.json")
        retired = next(c for c in doc["changelog"] if c["event"] == "retired")
        doc["declarations"].append({
            "id": retired["subject"], "id_source": "statement_hash", "kind": "example",
            "module": "Notes.Exercises", "file": "Notes/Exercises.lean", "private": False,
            "anonymous": True, "statement_sha256": retired["old_statement_sha256"]})
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "is retired, so it may not be used again", "I9")

    def test_a_renamed_subject_is_not_live_and_differs_from_its_successor(self):
        doc = load("graph-profile.json")
        change = next(c for c in doc["changelog"] if c["event"] == "renamed")
        change["subject"] = "Notes.Box"
        self.assertProblem(doc, "'Notes.Box' is renamed, so it may not be used again", "I9")
        change["subject"] = change["successor"] = "Notes.Box.lower"
        self.assertProblem(doc, "the successor differs from the subject", "I9")

    def test_an_orphaned_link_must_name_a_retired_id(self):
        doc = load("mixed.json")
        doc["changelog"] = [c for c in doc["changelog"] if c["event"] != "retired"]
        self.assertProblem(doc, "is orphaned but no changelog entry retires it", "I3")

    def test_an_orphaned_link_needs_a_retired_declaration_not_another_subject(self):
        doc = load("mixed.json")
        retired = next(c for c in doc["changelog"] if c["event"] == "retired")
        retired["subject_kind"] = "item"
        del retired["possible_successor"]
        self.assertProblem(doc, "is orphaned but no changelog entry retires it", "I3")

    def test_restated_names_a_declared_named_or_private_id(self):
        self.assertValid(load("mixed.json"))            # a named id, restated
        doc = load("graph-profile.json")
        restated = {"id": f"2026-09-25/restated/{GRAPH_EXAMPLE}", "at": "2026-09-25", "event": "restated",
                    "subject": GRAPH_EXAMPLE, "subject_kind": "declaration",
                    "old_statement_sha256": "0" * 64, "new_statement_sha256": "1" * 64}
        doc["changelog"].append(restated)
        doc = V.canonicalize(doc)
        self.assertProblem(doc, f"{GRAPH_EXAMPLE!r} is a statement-hash id, which changes with its "
                                f"statement: record retired (and the new id), not restated", "I9")
        doc = load("graph-profile.json")
        doc["changelog"].append(dict(restated, subject="Notes.Gone", id="2026-09-25/restated/Notes.Gone"))
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "'Notes.Gone' is not a live declaration id, and no later changelog entry", "I9")
        doc = load("graph-profile.json")
        doc["changelog"].append(dict(restated, subject="Notes.Box", subject_kind="item",
                                     id="2026-09-25/restated/Notes.Box"))
        doc = V.canonicalize(doc)
        self.assertProblem(doc, "restated records a declaration whose statement changed", "I9")
        doc = load("graph-profile.json")
        private = "private:Notes.Basic:Notes.Box.volume_aux"
        doc["changelog"].append(dict(restated, subject=private, id=f"2026-09-25/restated/{private}"))
        self.assertValid(V.canonicalize(doc))

    def test_restated_on_a_gone_id_needs_a_retirement_that_is_later_not_at_the_same_instant(self):
        """8.4: "retired or renamed by a later entry"; the same date or instant is not later (the
        ordinal_assigned rule says "no earlier" instead, and accepts it)."""
        restated = {"id": "2026-09-25/restated/Notes.Gone", "at": "2026-09-25", "event": "restated",
                    "subject": "Notes.Gone", "subject_kind": "declaration",
                    "old_statement_sha256": "0" * 64, "new_statement_sha256": "1" * 64}
        retired = {"id": "2026-09-25/retired/Notes.Gone", "at": "2026-09-25", "event": "retired",
                   "reason": "removed", "subject": "Notes.Gone", "subject_kind": "declaration"}
        for when, gone in (("2026-09-25", "2026-09-25"), ("2026-09-25", "2026-09-25T00:00:00Z"),
                           ("2026-09-25T12:00:00.5Z", "2026-09-25T12:00:00.50Z"), ("2026-09-25", "2026-09-24")):
            doc = load("graph-profile.json")
            doc["changelog"] += [dict(restated, at=when), dict(retired, at=gone)]
            with self.subTest(restated=when, retired=gone):
                self.assertProblem(V.canonicalize(doc), "'Notes.Gone' is not a live declaration id, and no later "
                                                        "changelog entry retires or renames it", "I9")
        for when, gone in (("2026-09-25", "2026-09-26"), ("2026-09-25", "2026-09-25T00:00:00.000000001Z"),
                           ("2026-09-25T12:00:00Z", "2026-09-25T12:00:00.1Z")):
            doc = load("graph-profile.json")
            doc["changelog"] += [dict(restated, at=when), dict(retired, at=gone, event="renamed",
                                                              successor="Notes.Box") | {"reason": "renamed"}]
            with self.subTest(restated=when, renamed=gone):
                self.assertValid(V.canonicalize(doc))

    # -- page sizes, whitespace ids, the root $schema, x_ keys ---------------------
    def test_a_pt_region_uses_its_pages_size(self):
        doc = load("graph-profile.json")
        rect = by_id(doc["locations"], "definition-1.1@p007-2")["target"]["selector"][0]["rect"]
        rect["x1"] = 1000
        self.assertProblem(doc, "the rect leaves the 612 x 792 pt page", "I7")
        doc["sources"][0]["page_sizes"] = [{"first": 7, "last": 7, "width_pt": 1224, "height_pt": 792}]
        self.assertValid(doc)
        rect["x1"] = 522
        doc["sources"][0]["page_sizes"] = [{"first": 7, "last": 7, "width_pt": 300, "height_pt": 200}]
        self.assertProblem(doc, "the rect leaves the 300 x 200 pt page", "I7")
        doc["sources"][0]["page_sizes"] = [{"first": 8, "last": 9, "width_pt": 300, "height_pt": 200}]
        self.assertValid(doc)          # page 7 is not in the range: page_size applies

    def test_a_whitespace_quote_or_title_is_a_problem_not_a_crash(self):
        doc = load("web-passage.json")
        next(i for i in doc["items"] if i["id_source"] == "quote_hash")["quote"]["exact"] = "  "
        self.assertProblem(doc, "a quote_hash id hashes a quote with text in it; item.quote is only whitespace",
                           "I12")
        doc = load("pdf-region.json")
        next(i for i in doc["items"] if i["id_source"] == "page_title_hash")["title"] = " \t "
        self.assertProblem(doc, "a page_title_hash id hashes a title with text in it", "I12")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "blank.json"
            path.write_text(json.dumps(doc), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = V.main([str(path)])
            self.assertEqual(status, 1)
            self.assertIn(".title: a page_title_hash id hashes a title with text in it", out.getvalue())
            self.assertEqual(err.getvalue(), "")

    def test_the_root_schema_key_may_hold_a_url(self):
        doc = load("pdf-region.json")
        doc["$schema"] = SCHEMA_ID
        self.assertValid(doc)
        self.assertEqual(lines(doc, lints=("external-urls",)), [])

    def test_x_keys_sit_on_records_companion_and_the_root(self):
        doc = load("mixed.json")
        self.assertTrue(any(k.startswith("x_") for k in doc))
        self.assertTrue(any(k.startswith("x_") for k in doc["companion"]))
        self.assertTrue(any(k.startswith("x_") for p in doc["provenance"] for k in p))
        self.assertValid(doc)
        doc["x_elsewhere"] = ["https://example.org/", {"any": [1, None, True, 2.5]}]
        self.assertValid(doc)                              # an x_ value is free (the lint is opt-in)
        doc = load("mixed.json")
        doc["pages"] = 3
        self.assertProblem(doc, "pages", "SCHEMA")         # not an x_ key: the root is closed


class TestCoverage(unittest.TestCase):
    """I5, the six rules of section 5.4, on non-orphaned links."""

    def assertI5(self, doc: dict, fragment: str) -> None:
        found = V.check(doc).problems
        hits = [p for p in found if fragment in str(p)]
        self.assertTrue(hits, f"{fragment!r} not in {[str(p) for p in found]}")
        self.assertEqual({p.code for p in hits}, {"I5"}, hits)

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def item(self, doc: dict, rid: str) -> dict:
        return by_id(doc["items"], rid)

    def links_of(self, doc: dict, rid: str) -> list[dict]:
        return [l for l in doc["links"] if l["item"] == rid and not l.get("orphaned")]

    def test_rule_2_links_without_a_key_need_coverage(self):
        doc = load("mixed.json")
        del self.item(doc, "passage-remark-unions")["coverage"]
        del self.item(doc, "passage-remark-unions")["coverage_note"]
        self.assertI5(doc, "has links but no key link, so it must carry coverage")
        doc = load("mixed.json")
        self.assertNotIn("coverage", self.item(doc, "definition-1.1"))
        self.assertValid(doc)                                       # a key link: coverage is optional
        doc = load("minimal.json")
        doc["links"] = []
        self.assertValid(doc)                                       # no links: no coverage needed either

    def test_rule_3_attributed_needs_a_key_unless_partial_only(self):
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["id"] != "definition-1.1/key/Notes.Box"]
        self.item(doc, "definition-1.1")["coverage"] = "support_only"
        self.assertI5(doc, "has attributed links and no key link")
        self.item(doc, "definition-1.1")["coverage"] = "partial_only"
        self.assertValid(doc)
        doc = load("mixed.json")
        self.assertEqual({l["role"] for l in self.links_of(doc, "lemma-1.4")}, {"attributed"})
        self.assertEqual(self.item(doc, "lemma-1.4")["coverage"], "partial_only")
        self.assertValid(doc)

    def test_rule_4_formalized_needs_a_key_and_five_classes_exclude_one(self):
        doc = load("mixed.json")
        self.item(doc, "passage-remark-unions")["coverage"] = "formalized"
        self.assertI5(doc, "item 'passage-remark-unions' is formalized but has no key link")
        for value in ("partial_only", "support_only", "example_only", "not_formalized", "out_of_scope"):
            doc = load("mixed.json")
            self.item(doc, "definition-1.1")["coverage"] = value
            with self.subTest(coverage=value):
                self.assertI5(doc, f"item 'definition-1.1' is {value} but has a key link")
        doc = load("pdf-region.json")
        self.item(doc, "definition-1.1")["coverage"] = "formalized"
        self.assertValid(doc)

    def test_rule_4_private_only(self):
        doc = load("mixed.json")
        self.assertEqual(self.item(doc, "theorem-1.5")["coverage"], "private_only")
        self.assertValid(doc)
        doc["links"].append({"declaration": "Notes.Box", "id": "theorem-1.5/key/Notes.Box", "item": "theorem-1.5",
                             "provenance": "prov-curation", "role": "key"})
        doc = V.canonicalize(doc)
        self.assertI5(doc, "item 'theorem-1.5' is private_only, so a key link names a private declaration; "
                           "'Notes.Box' is not private")
        doc = load("mixed.json")
        cluster = doc["clusters"][0]["id"]                              # a cluster names no declaration at all
        doc["links"].append({"cluster": cluster, "id": f"theorem-1.5/key/{cluster}", "item": "theorem-1.5",
                             "provenance": "prov-curation", "role": "key"})
        doc = V.canonicalize(doc)
        self.assertI5(doc, f"item 'theorem-1.5' is private_only, so a key link names a private declaration; "
                           f"'theorem-1.5/key/{cluster}' names a cluster")
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["item"] != "theorem-1.5"]
        self.assertI5(doc, "item 'theorem-1.5' is private_only but has no link")
        doc = load("mixed.json")
        doc["links"] = [l for l in doc["links"] if l["id"] != "theorem-1.5/key/private:Notes.Basic:Notes.Box.volume_aux"]
        self.assertValid(doc)                                       # a helper link alone satisfies "at least one"

    def test_rule_5_not_formalized_and_out_of_scope_exclude_key_and_attributed(self):
        for value in ("not_formalized", "out_of_scope"):
            doc = load("mixed.json")
            self.item(doc, "lemma-1.4")["coverage"] = value
            with self.subTest(coverage=value):
                self.assertI5(doc, f"item 'lemma-1.4' is {value} but has an attributed link")
                self.assertI5(doc, "item 'lemma-1.4' has attributed links and no key link")
            doc = load("mixed.json")
            self.item(doc, "passage-remark-unions")["coverage"] = value      # example and support links
            with self.subTest(coverage=value, links="example, support"):
                self.assertValid(doc)

    def test_rule_6_coverage_note_needs_coverage(self):
        doc = load("mixed.json")
        del self.item(doc, "lemma-1.4")["coverage"]
        found = lines(doc)
        self.assertIn("$.items[1].coverage_note: coverage_note needs coverage [I5]", found)
        doc = load("minimal.json")
        doc["items"][0]["coverage_note"] = "A note without a class."
        self.assertEqual(lines(doc), ["$.items[0].coverage_note: coverage_note needs coverage [I5]"])
        doc["items"][0]["coverage"] = "formalized"
        self.assertValid(doc)
        doc["items"][0]["coverage_note"] = ""
        self.assertEqual(codes(doc), ["SCHEMA"])

    def test_orphaned_links_do_not_count(self):
        doc = load("mixed.json")
        orphan = next(l for l in doc["links"] if l.get("orphaned"))
        self.assertEqual(orphan["role"], "example")
        self.item(doc, "definition-1.1")["coverage"] = "formalized"
        self.assertValid(doc)

    def test_an_anonymous_example_may_be_a_key_links_target(self):
        """5.2: example_only is for an item whose only formalisations are anonymous examples that the producer
        links with role example.  An anonymous example that states the whole item is a key link's target, and
        the item is then formalized (or carries no coverage), not example_only."""
        doc = load("pdf-region.json")
        self.assertEqual(self.item(doc, "exercise-1.4")["coverage"], "example_only")
        link = next(l for l in doc["links"] if l["item"] == "exercise-1.4")
        target = by_id(doc["declarations"], link["declaration"])
        self.assertEqual((link["role"], target["kind"], target["anonymous"]), ("example", "example", True))
        link["role"], link["id"] = "key", f"exercise-1.4/key/{link['declaration']}"
        doc = V.canonicalize(doc)
        self.assertI5(doc, "item 'exercise-1.4' is example_only but has a key link")
        self.item(doc, "exercise-1.4")["coverage"] = "formalized"
        self.assertValid(doc)
        del self.item(doc, "exercise-1.4")["coverage"]
        self.assertValid(doc)


class TestNewFields(unittest.TestCase):
    """identifiers, xrefs, toolchain and packages (sections 4.3, 5.1, 5.2)."""

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def test_identifiers_take_a_doi_isbns_and_an_arxiv_id(self):
        doc = load("minimal.json")
        source = doc["sources"][0]
        for good in ({"doi": "10.1000/xyz123"}, {"doi": "10.123456789/a.b/c(d)"}, {"isbn": ["9781234567897"]},
                     {"arxiv": "2601.00001v2"}, {"arxiv": "2601.12345v10"}, {"arxiv": "math.AG/0601001v1"},
                     {"arxiv": "hep-th/9901001v3"}, {"doi": "10.1000/x", "isbn": ["9780000000002", "9781234567897"],
                                                     "arxiv": "2601.00001v1"}):
            source["identifiers"] = good
            with self.subTest(identifiers=good):
                self.assertValid(doc)
        for bad in ({}, {"doi": "11.1000/x"}, {"doi": "10.100/x"}, {"doi": "10.1000/"}, {"doi": "10.1000/a b"},
                    {"isbn": []}, {"isbn": ["1234567890"]}, {"isbn": ["9771234567897"]}, {"isbn": ["978123456789X"]},
                    {"arxiv": "2601.00001"}, {"arxiv": "2601.00001v0"}, {"arxiv": "math.AG/0601001"},
                    {"arxiv": "Math.AG/0601001v1"}, {"arxiv": "2601.001v1"}, {"issn": "1234-5678"},
                    {"doi": "10.1000/x\n"}, {"arxiv": "2601.00001v1\n"}):
            source["identifiers"] = bad
            with self.subTest(identifiers=bad):
                self.assertEqual(set(codes(doc)), {"SCHEMA"}, lines(doc))
                self.assertTrue(all("identifiers" in p.path for p in V.check(doc).problems))

    def test_a_pdf_source_may_be_pinned_by_identifiers_alone(self):
        """5.1: the edition (a DOI, ISBNs, an arXiv id) when the producer does not hold the bytes.  An edition
        has pages, so page= fragments, pages and the page fields apply; a PdfRegionSelector is measured on the
        bytes, so it needs sha256 or git_blob (6.4, I7)."""
        doc = load("pdf-region.json")
        source = doc["sources"][0]
        del source["sha256"]
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("SCHEMA", "$.sources[0]")])
        source["identifiers"] = {"doi": "10.5555/elementary-sets.2026", "isbn": ["9781234567897"]}
        found = V.check(doc).problems                           # the example's two regions, nothing else
        self.assertEqual({(p.code, p.path) for p in found},
                         {("I7", "$.locations[0].target.selector[0].refinedBy"),
                          ("I7", "$.locations[1].target.selector[0]")})
        self.assertEqual({p.message for p in found}, {"a PdfRegionSelector needs the source's bytes; 'notes-pdf' "
                                                      "names none (no sha256 or git_blob): locate by page= or pages "
                                                      "instead"})
        del doc["locations"][0]["target"]["selector"][0]["refinedBy"]      # the page= fragment stays
        del doc["locations"][1]["target"]["selector"][0]                   # the page= fragment and its quote stay
        self.assertValid(doc)
        self.assertTrue({"physical_page_count", "printed_page_offset", "page_size"} <= set(source))
        del source["bytes"], source["url"]
        self.assertValid(doc)
        doc = load("minimal.json")                              # neither the bytes nor the edition: refused
        doc["sources"][0]["identifiers"] = {"arxiv": "2601.00001v2"}
        del doc["sources"][0]["sha256"]
        self.assertValid(doc)
        del doc["sources"][0]["identifiers"]
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = load("web-passage.json")                          # identifiers alone pin a pdf or other source only
        del doc["sources"][0]["revision"]
        doc["sources"][0]["identifiers"] = {"arxiv": "2601.00001v2"}
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc = load("other-media.json")                          # an e-book by its ISBN
        epub = by_id(doc["sources"], "notes-epub")
        del epub["sha256"]
        self.assertEqual(codes(doc), ["SCHEMA"])
        epub["identifiers"] = {"isbn": ["9781234567897"]}
        self.assertValid(doc)

    def test_isbns_are_a_sorted_set(self):
        doc = load("minimal.json")
        doc["sources"][0]["identifiers"] = {"isbn": ["9781234567897", "9780000000002"]}
        self.assertEqual(lines(doc), ["$.sources[0].identifiers.isbn: must be sorted (UTF-16 code units) [I2]"])
        doc["sources"][0]["identifiers"] = {"isbn": ["9780000000002", "9780000000002"]}
        self.assertEqual(codes(doc), ["SCHEMA"])                    # uniqueItems
        canonical = V.canonicalize({**doc, "sources": [dict(doc["sources"][0],
                                                            identifiers={"isbn": ["9781234567897", "9780000000002"]})]})
        self.assertEqual(canonical["sources"][0]["identifiers"]["isbn"], ["9780000000002", "9781234567897"])

    def test_xrefs_are_sorted_unique_pairs_with_a_documented_core(self):
        doc = load("mixed.json")
        item = by_id(doc["items"], "definition-1.1")
        self.assertEqual(item["xrefs"], [{"database": "stacks", "tag": "0A1B"}, {"database": "wikidata", "tag": "Q1234567"}])
        item["xrefs"].reverse()
        self.assertEqual(lines(doc), ["$.items[0].xrefs: must be sorted by (database, tag), one entry each [I2]"])
        item["xrefs"] = [{"database": "stacks", "tag": "0A1B"}, {"database": "stacks", "tag": "0A1B"}]
        self.assertEqual(codes(doc), ["SCHEMA"])                    # uniqueItems
        item["xrefs"] = [{"database": "stacks", "tag": "0A1C"}, {"database": "stacks", "tag": "0A1B"}]
        self.assertEqual(codes(doc), ["I2"])
        item["xrefs"] = [{"database": "stacks", "tag": "0A1B"}, {"database": "stacks", "tag": "0A1C"}]
        self.assertValid(doc)
        self.assertEqual(V.canonicalize({**doc, "items": [dict(item, xrefs=list(reversed(item["xrefs"])))]})
                         ["items"][0]["xrefs"], item["xrefs"])
        item["xrefs"] = [{"database": "kerodon", "tag": "01AB"}, {"database": "lmfdb", "tag": "1.1.1.1"},
                         {"database": "zbmath", "tag": "123.45678"}]
        self.assertValid(doc)
        self.assertEqual([(w.code, w.path) for w in V.check(doc).warnings], [("W-XREF", "$.items[0].xrefs[2].database")])
        self.assertIn("'zbmath' is outside the documented core (kerodon, lmfdb, stacks, wikidata)", warnings(doc)[0])
        for bad in ([{"database": "Stacks", "tag": "0A1B"}], [{"database": "stacks", "tag": "0A 1B"}],
                    [{"database": "stacks", "tag": ""}], [{"database": "stacks"}], [], [{"database": "stacks", "tag": "x", "url": "y"}]):
            item["xrefs"] = bad
            with self.subTest(xrefs=bad):
                self.assertEqual(set(codes(doc)), {"SCHEMA"}, lines(doc))

    def test_toolchain_and_packages(self):
        doc = load("mixed.json")
        c = doc["companion"]
        self.assertEqual(c["toolchain"], "leanprover/lean4:v4.34.0")
        c["packages"].reverse()
        self.assertEqual(lines(doc), ["$.companion.packages: must be sorted by name, one entry each [I2]"])
        self.assertEqual([p["name"] for p in V.canonicalize(doc)["companion"]["packages"]], ["batteries", "mathlib"])
        c["packages"] = [dict(c["packages"][1], rev="0" * 64), c["packages"][1]]
        self.assertEqual(lines(doc), ["$.companion.packages: must be sorted by name, one entry each [I2]"])
        c["packages"] = []
        self.assertValid(doc)
        for bad in ([{"name": "mathlib", "rev": "abc1234"}], [{"name": "", "rev": "0" * 40}],
                    [{"name": "mathlib"}], [{"rev": "0" * 40}], [{"name": "mathlib", "rev": "0" * 40, "url": "x"}]):
            c["packages"] = bad
            with self.subTest(packages=bad):
                self.assertEqual(codes(doc), ["SCHEMA"], lines(doc))
        del c["packages"]
        c["toolchain"] = ""
        self.assertEqual(codes(doc), ["SCHEMA"])
        del c["toolchain"]
        self.assertValid(doc)


class TestDeclarationKinds(unittest.TestCase):
    """constructor, recursor, alias, irreducible_def; parents and the member name rule (5.3)."""

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def with_member(self, kind: str, parent_kind: str, **more) -> dict:
        doc = load("mixed.json")
        doc["declarations"] += [
            {"anonymous": False, "file": "Notes/Basic.lean", "id": "Notes.Color", "id_source": "name",
             "kind": parent_kind, "module": "Notes.Basic", "name": "Notes.Color", "private": False},
            {"anonymous": False, "file": "Notes/Basic.lean", "id": "Notes.Color.red", "id_source": "name",
             "kind": kind, "module": "Notes.Basic", "name": "Notes.Color.red", "namespace": "Notes.Color",
             "parent": "Notes.Color", "private": False, **more}]
        return V.canonicalize(doc)

    @staticmethod
    def member(doc: dict, rid: str = "Notes.Color.red") -> tuple[str, dict]:
        """The member's JSON path and record."""
        i = next(i for i, d in enumerate(doc["declarations"]) if d["id"] == rid)
        return f"$.declarations[{i}]", doc["declarations"][i]

    def test_constructors_and_recursors_belong_to_an_inductive_structure_or_class(self):
        for kind in ("constructor", "recursor"):
            for parent_kind in ("inductive", "structure", "class"):
                with self.subTest(kind=kind, parent=parent_kind):
                    self.assertValid(self.with_member(kind, parent_kind))
            doc = self.with_member(kind, "theorem")
            path, _ = self.member(doc)
            with self.subTest(kind=kind, parent="theorem"):
                self.assertEqual(lines(doc), [f"{path}.parent: a {kind}'s parent is an inductive, structure or "
                                              f"class, not a theorem [I3]"])
        for kind in ("field", "projection"):
            doc = self.with_member(kind, "inductive")
            path, _ = self.member(doc)
            with self.subTest(kind=kind, parent="inductive"):
                self.assertEqual(lines(doc), [f"{path}.parent: a {kind}'s parent is a structure or class, not an "
                                              f"inductive [I3]"])

    def test_a_member_needs_a_parent_and_nothing_else_has_one(self):
        for kind in vocab.ANNOTATION_MEMBER_PARENT_KINDS:
            doc = self.with_member(kind, "structure")
            path, member = self.member(doc)
            del member["parent"]
            with self.subTest(kind=kind):
                self.assertEqual(lines(doc), [f"{path}: is missing required key 'parent' [SCHEMA]"])
        for kind in ("alias", "irreducible_def", "theorem", "inductive"):
            doc = self.with_member(kind, "structure")
            path, member = self.member(doc)
            with self.subTest(kind=kind):
                self.assertEqual(codes(doc), ["SCHEMA"])
                self.assertIn("(not)", lines(doc)[0])
            del member["parent"]
            del member["namespace"]
            self.assertValid(doc)

    def test_a_members_full_name_is_its_parents_name_and_its_own(self):
        for kind in vocab.ANNOTATION_MEMBER_PARENT_KINDS:
            doc = self.with_member(kind, "structure", namespace="Notes")
            path, _ = self.member(doc)
            with self.subTest(kind=kind, field="namespace"):
                self.assertEqual(lines(doc), [f"{path}.namespace: a {kind}'s namespace is its parent's "
                                              f"full name (its name), 'Notes.Color' [I8]"])
            doc = self.with_member(kind, "structure")
            _, member = self.member(doc)
            member["id"] = member["name"] = "Notes.Other.red"
            doc = V.canonicalize(doc)
            path, _ = self.member(doc, "Notes.Other.red")
            with self.subTest(kind=kind, field="name"):
                self.assertEqual(lines(doc), [f"{path}.name: a {kind}'s full name is its namespace, a dot "
                                              f"and its own name [I8]"])
            doc = self.with_member(kind, "structure")
            _, member = self.member(doc)
            del member["name"]
            del member["namespace"]
            with self.subTest(kind=kind, field="id"):
                self.assertValid(doc)                                   # the full name is read from the id
                member["id"] = "Notes.Other.red"
                doc = V.canonicalize(doc)
                path, _ = self.member(doc, "Notes.Other.red")
                self.assertEqual(lines(doc), [f"{path}.id: a {kind}'s full name is its parent's full name "
                                              f"('Notes.Color'), a dot and its own name [I8]"])

    def test_a_members_own_name_is_one_component(self):
        """5.3: the full name is the namespace, a dot and its own name; a dotted remainder is refused, against
        the namespace when it is given and agrees with the parent, else against the parent's full name."""
        for kind in vocab.ANNOTATION_MEMBER_PARENT_KINDS:
            doc = self.with_member(kind, "structure")
            _, member = self.member(doc)
            member["id"] = member["name"] = "Notes.Color.red.dark"
            doc = V.canonicalize(doc)
            path, member = self.member(doc, "Notes.Color.red.dark")
            with self.subTest(kind=kind, against="namespace"):
                self.assertEqual(lines(doc), [f"{path}.name: a {kind}'s full name is its namespace, a dot and "
                                              f"its own name [I8]"])
            del member["namespace"]
            with self.subTest(kind=kind, against="parent"):
                self.assertEqual(lines(doc), [f"{path}.name: a {kind}'s full name is its parent's full name "
                                              f"('Notes.Color'), a dot and its own name [I8]"])
        doc = self.with_member("field", "structure", namespace="Notes")     # a wrong namespace: reported once,
        path, _ = self.member(doc)                                          # the name held against the parent
        self.assertEqual(lines(doc), [f"{path}.namespace: a field's namespace is its parent's full name (its "
                                      f"name), 'Notes.Color' [I8]"])

    def test_a_named_declaration_may_carry_its_signature_and_statement_hash(self):
        """statement_sha256 is required on an anonymous declaration (5.3) and allowed on any other, where it
        is the hash of the signature's hash form (I8): what ids.signature_at returns for a named declaration
        and what a history profile's restated entries record."""
        doc = load("minimal.json")
        decl = doc["declarations"][0]
        decl["signature"] = "theorem Notes.Box.volume_nonneg (b : Box) : 0 <= b.volume"
        decl["statement_sha256"] = ids.statement_sha256(decl["signature"])
        self.assertValid(doc)
        decl["statement_sha256"] = "0" * 64
        self.assertEqual(lines(doc), ["$.declarations[0].signature: its sha256 is not statement_sha256 (the hash "
                                      "of the signature's hash form) [I8]"])
        del decl["signature"]
        self.assertValid(doc)                           # the hash alone, from a producer that computed it

    def test_a_named_example_is_refused(self):
        doc = load("minimal.json")
        doc["declarations"][0]["kind"] = "example"
        self.assertEqual(lines(doc), ["$.declarations[0].anonymous: an example is always anonymous (a named "
                                      "example is refused) [I8]"])


class TestSelectorsAndPlacement(unittest.TestCase):
    """The five selector types and the placement rules of section 6.6."""

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def placed(self, selector: dict, name: str = "pdf-region.json", loc: str = "definition-1.1@p007") -> list[str]:
        doc = load(name)
        location = by_id(doc["locations"], loc)
        location["target"]["selector"][0] = selector
        location.pop("pages", None)                  # placement only: not the page-span mirror rule
        return lines(doc)

    def region(self, page: int = 7) -> dict:
        return {"type": "PdfRegionSelector", "page": page,
                "coordinate_space": {"origin": "top_left", "units": "normalized", "x_axis": "right",
                                     "y_axis": "down", "page_box": "CropBox"},
                "rect": {"x0": 0.1, "y0": 0.1, "x1": 0.2, "y1": 0.2}}

    def page(self, n: int, child: dict | None = None) -> dict:
        sel = {"type": "FragmentSelector", "conformsTo": vocab.CONFORMS_TO_PDF, "value": f"page={n}"}
        if child is not None:
            sel["refinedBy"] = child
        return sel

    def quote(self, child: dict | None = None) -> dict:
        sel = {"type": "TextQuoteSelector", "exact": "Definition 1.1 (Boxes)."}
        if child is not None:
            sel["refinedBy"] = child
        return sel

    def test_the_removed_selector_types_and_the_time_state_are_refused(self):
        for sel in ({"type": "TextPositionSelector", "start": 1, "end": 2},
                    {"type": "DataPositionSelector", "start": 1, "end": 2},
                    {"type": "XPathSelector", "value": "//p"}, {"type": "SvgSelector", "value": "<svg/>"},
                    {"type": "RangeSelector", "startSelector": self.quote(), "endSelector": self.quote()}):
            with self.subTest(type=sel["type"]):
                found = self.placed(sel)
                self.assertEqual(len(found), 1, found)
                self.assertTrue(found[0].startswith("$.locations[0].target.selector[0].type: "), found[0])
                self.assertTrue(found[0].endswith("[SCHEMA]"))
                self.assertIn("is not one of", found[0])
        doc = load("web-passage.json")
        doc["locations"][0]["target"]["state"] = {"type": "TimeState", "sourceDate": "2026-09-01T08:00:00Z"}
        self.assertEqual(lines(doc), ["$.locations[0].target.state: is not an allowed key here [SCHEMA]"])

    def test_a_region_is_top_level_or_refines_a_page_fragment_directly(self):
        self.assertEqual(self.placed(self.region()), [])
        self.assertEqual(self.placed(self.page(7, self.region())), [])
        found = self.placed(self.page(7, self.quote(self.region())))
        self.assertEqual(found, ["$.locations[0].target.selector[0].refinedBy.refinedBy: a PdfRegionSelector is a "
                                 "top-level alternative or the direct refinement of a PDF page= fragment [I7]"])
        found = self.placed(self.quote(self.region()))
        self.assertEqual(len(found), 1)
        self.assertIn("top-level alternative or the direct refinement", found[0])
        found = self.placed(self.page(7, self.region(8)))
        self.assertEqual(found, ["$.locations[0].target.selector[0].refinedBy.page: page 8 disagrees with the "
                                 "refined page=7 [I7]"])

    def test_a_page_inside_a_page_names_the_same_page(self):
        self.assertEqual(self.placed(self.page(7, self.page(7, self.quote()))), [])
        found = self.placed(self.page(7, self.page(8)))
        self.assertEqual(found, ["$.locations[0].target.selector[0].refinedBy.value: page=8 inside page=7 [I7]"])
        found = self.placed(self.page(7, self.quote(self.page(8))))
        self.assertEqual(found, ["$.locations[0].target.selector[0].refinedBy.refinedBy.value: page=8 inside "
                                 "page=7 [I7]"])

    def test_a_refined_pdf_fragment_names_its_page(self):
        sel = {"type": "FragmentSelector", "conformsTo": vocab.CONFORMS_TO_PDF, "value": "nameddest=def-1-1",
               "refinedBy": self.quote()}
        found = self.placed(sel)
        self.assertEqual(found, ["$.locations[0].target.selector[0].value: a PDF fragment that is refined must name "
                                 "its page= [I7]"])

    def test_a_refinement_chain_is_at_most_8_deep(self):
        def chain(n: int) -> dict:
            sel = self.quote()
            for _ in range(n - 1):
                sel = self.quote(sel)
            return sel
        self.assertEqual(self.placed(self.page(7, chain(7))), [])                 # 8 selectors
        found = self.placed(self.page(7, chain(8)))                               # 9 selectors
        self.assertEqual(found, ["$.locations[0].target.selector[0]" + ".refinedBy" * 8 + ": a refinedBy chain is "
                                 "at most 8 selectors deep [I7]"])
        self.assertEqual(V.MAX_REFINEMENT_DEPTH, 8)
        doc = load("web-passage.json")
        doc["locations"][0]["target"]["selector"] = [chain(8)]
        self.assertValid(doc)
        doc["locations"][0]["target"]["selector"] = [chain(9)]
        self.assertEqual(codes(doc), ["I7"])

    def test_the_families(self):
        self.assertEqual(V.ALLOWED_SELECTORS, {
            "pdf": {"FragmentSelector", "TextQuoteSelector", "PdfRegionSelector"},
            "html": {"FragmentSelector", "TextQuoteSelector", "CssSelector", "SitePageSelector"},
            "text": {"FragmentSelector", "TextQuoteSelector"},
            "generic": {"FragmentSelector", "TextQuoteSelector", "CssSelector"}})
        doc = load("other-media.json")
        video = next(l for l in doc["locations"] if l["target"]["source"] == "lecture-video")
        video["target"]["selector"].append({"type": "CssSelector", "value": "video"})
        self.assertValid(doc)
        md = next(l for l in doc["locations"] if l["target"]["source"] == "notes-md")
        md["target"]["selector"].append({"type": "CssSelector", "value": "p"})
        self.assertEqual(codes(doc), ["I7"])


class TestProfilesAndVersions(unittest.TestCase):
    """I14 (section 4.2), the schema of the declared minor and forward mode (section 12)."""

    def assertValid(self, doc: dict) -> None:
        self.assertEqual(lines(doc), [])

    def test_the_profiles_table(self):
        self.assertEqual(V.PROFILES, {
            "audit": {"arrays": ("verdicts",), "fields": ()},
            "graph": {"arrays": ("artifacts", "clusters", "memberships"),
                      "fields": ("companion.graph", "declarations.unlocated", "destinations.artifact",
                                 "items.clusters", "links.cluster")},
            "history": {"arrays": ("changelog",), "fields": ("declarations.replaced_by", "links.orphaned")},
            "site": {"arrays": ("destinations", "snippets"), "fields": ()}})

    def test_a_source_role_is_core_and_needs_no_profile(self):
        """5.1: a document with no verdicts may still say which source it audits or keeps as a reference."""
        doc = load("minimal.json")
        self.assertNotIn("profiles", doc)
        for role in ("audited", "reference"):
            doc["sources"][0]["role"] = role
            with self.subTest(role=role):
                self.assertValid(doc)
        doc["sources"][0]["role"] = "primary"
        self.assertEqual(lines(doc), ['$.sources[0].role: "primary" is not one of "audited", "reference" [SCHEMA]'])
        doc = load("mixed.json")
        del doc["profiles"]["audit"]
        del doc["verdicts"]
        self.assertTrue(any("role" in s for s in doc["sources"]))
        self.assertValid(doc)

    def test_an_owned_array_or_field_needs_its_profile(self):
        expected = {
            "audit": {"$.verdicts"},
            "graph": {"$.clusters", "$.items[0].clusters", "$.items[3].clusters", "$.items[4].clusters",
                      "$.links[3].cluster"},
            "history": {"$.changelog", "$.declarations[3].replaced_by", "$.links[1].orphaned"},
            "site": {"$.destinations", "$.snippets"},
        }
        for name, paths in expected.items():
            doc = load("mixed.json")
            del doc["profiles"][name]
            found = V.check(doc).problems
            with self.subTest(profile=name):
                self.assertEqual({p.code for p in found}, {"I14"}, found)
                self.assertEqual({p.path for p in found}, paths)
                self.assertTrue(all(f"belongs to the {name} profile, which the document does not declare "
                                    f"(profiles.{name})" in p.message for p in found), found)
        doc = load("graph-profile.json")
        del doc["profiles"]["graph"]
        found = {p.path for p in V.check(doc).problems}
        self.assertTrue({"$.companion.graph", "$.artifacts", "$.memberships", "$.clusters", "$.destinations[2].artifact",
                         "$.declarations[7].unlocated"} <= found, found)

    def test_a_declared_profile_may_be_unused_and_the_object_may_be_empty(self):
        doc = load("minimal.json")
        doc["profiles"] = {}
        self.assertValid(doc)
        doc["profiles"] = dict(ALL_PROFILES)
        self.assertValid(doc)
        doc["profiles"] = {"audit": "1"}
        self.assertEqual(codes(doc), ["SCHEMA"])
        doc["profiles"] = {"other": "1.0"}
        self.assertEqual(lines(doc), ["$.profiles.other: is not an allowed key here [SCHEMA]"])
        doc["profiles"] = ["site"]
        self.assertEqual(codes(doc), ["SCHEMA"])

    def test_the_schema_of_the_declared_minor_is_used(self):
        doc = load("minimal.json")
        self.assertEqual(V.select_schema(doc).path, V.schema_path(1, 0))
        self.assertFalse(V.select_schema(doc).forward)
        self.assertEqual(V.schema_path(1, 0).name, "annotations-v1.0.schema.json")
        self.assertEqual(V.schema_id(1, 0), SCHEMA_ID)
        self.assertEqual(V.schema_id(1, 7), "https://w3id.org/formal-companion/annotations/v1.7/schema.json")
        doc["schema_version"] = "1.0\n"
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("SCHEMA", "$.schema_version")])
        doc["schema_version"] = 1
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("SCHEMA", "$.schema_version")])

    def test_an_unknown_major_is_a_problem(self):
        doc = load("minimal.json")
        doc["schema_version"] = "2.0"
        self.assertEqual(lines(doc), ["$.schema_version: no schema for major version 2 (this checker has 1) [SCHEMA]"])
        doc = load("web-passage.json")
        doc["profiles"]["site"] = "2.0"
        self.assertEqual(lines(doc), ["$.profiles.site: no schema for site profile major version 2 (this checker "
                                      "has 1.0) [SCHEMA]"])
        self.assertEqual(V.check(doc).warnings, [])

    def test_a_newer_core_minor_is_checked_in_forward_mode(self):
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.9"
        doc["items"][0]["future_field"] = {"anything": [1, 2]}
        doc["future_array"] = []
        doc["locations"][0]["target"]["selector"][0]["refinedBy"]["future"] = 1
        report = V.check(doc)
        self.assertTrue(report.ok, report.problems)
        self.assertEqual([(w.code, w.path) for w in report.warnings],
                         [("W-NEWER", "$.schema_version"), ("W-NEWER", "$.items[0].future_field"),
                          ("W-NEWER", "$.locations[0].target.selector[0].refinedBy.future"),
                          ("W-NEWER", "$.future_array")])
        self.assertIn("checked against 1.0, keys added since are ignored", report.warnings[0].message)
        self.assertIn("ignored, as the document declares a newer minor", report.warnings[1].message)
        # the semantic checks still run on the keys the checker knows
        doc["links"][0]["declaration"] = "Notes.Nowhere"
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("I3", "$.links[0].declaration")])
        # an unknown enum value still fails
        doc = load("pdf-region.json")
        doc["schema_version"] = "1.9"
        doc["items"][0]["coverage"] = "future_class"
        self.assertEqual([(p.code, p.path) for p in V.check(doc).problems], [("SCHEMA", "$.items[0].coverage")])
        # the same keys under the declared 1.0 are problems
        doc = load("pdf-region.json")
        doc["items"][0]["future_field"] = 1
        self.assertEqual(lines(doc), ["$.items[0].future_field: is not an allowed key here [SCHEMA]"])

    def test_a_newer_profile_minor_is_checked_in_forward_mode(self):
        doc = load("web-passage.json")
        doc["profiles"]["site"] = "1.4"
        doc["destinations"][0]["future_field"] = True
        report = V.check(doc)
        self.assertTrue(report.ok, report.problems)
        self.assertEqual([(w.code, w.path) for w in report.warnings],
                         [("W-NEWER", "$.profiles.site"), ("W-NEWER", "$.destinations[0].future_field")])
        self.assertIn("is newer than this checker's site profile (1.0)", report.warnings[0].message)
        doc["profiles"]["future"] = "1.0"                # a profile this checker does not know, in forward mode
        self.assertTrue(V.check(doc).ok)
        self.assertIn(("W-NEWER", "$.profiles.future"), [(w.code, w.path) for w in V.check(doc).warnings])
        doc = load("web-passage.json")
        doc["destinations"][0]["future_field"] = True
        self.assertEqual(codes(doc), ["SCHEMA"])

    def test_dollar_schema_should_be_the_declared_minors_id(self):
        doc = load("minimal.json")
        doc["$schema"] = SCHEMA_ID
        self.assertEqual(V.check(doc).warnings, [])
        doc["$schema"] = "https://example.org/other-schema.json"
        report = V.check(doc)
        self.assertTrue(report.ok)
        self.assertEqual([(w.code, w.path) for w in report.warnings], [("W-SCHEMA-ID", "$.$schema")])
        self.assertIn(f"is not the $id of the declared schema 1.0, {SCHEMA_ID}", report.warnings[0].message)
        doc["schema_version"] = "1.3"
        doc["$schema"] = V.schema_id(1, 3)
        self.assertEqual([w.code for w in V.check(doc).warnings], ["W-NEWER"])
        doc["$schema"] = SCHEMA_ID
        self.assertEqual([w.code for w in V.check(doc).warnings], ["W-NEWER", "W-SCHEMA-ID"])
        doc["$schema"] = 3
        self.assertEqual(codes(doc), ["SCHEMA"])

    def test_the_cli_prints_the_warnings_with_their_codes(self):
        doc = load("minimal.json")
        doc["schema_version"] = "1.2"
        doc["$schema"] = SCHEMA_ID
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "newer.json"
            path.write_text(V.canonical_dumps(doc), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                status = V.main([str(path), "--canonical"])
            self.assertEqual(status, 0, out.getvalue())
            self.assertIn(f"{path}: warning: $.schema_version: 1.2 is newer than this checker (1.0)", out.getvalue())
            self.assertIn(" [W-NEWER]\n", out.getvalue())
            self.assertIn(" [W-SCHEMA-ID]\n", out.getvalue())
            self.assertTrue(out.getvalue().endswith(": ok (1 sources, 1 provenance, 1 items, 1 declarations, "
                                                    "1 links)\n"), out.getvalue())


LEAN = """\
/-- `Exercise 1.4` -/
example : volume (Box.unit 2) = 1 := by
  sorry

-- the same statement again, reformatted
example :   volume (Box.unit 2)
    = 1 := by simp

example : let f := fun x : ℕ => x + 1
    f 0 = 1 := rfl

example (d : ℕ) := foo_eq d

/- `example:boxes-are-elementary` -/
example : IsElementary (Box.unit 1 : Set ℝ) := by
  exact isElementary_box _

instance : Inhabited Box := ⟨Box.unit 0⟩

instance instNamed : Nonempty Box := ⟨Box.unit 0⟩

noncomputable example : ℝ := 1
"""


class TestMechanicalIds(unittest.TestCase):
    """The scanner as the checker relies on it; tests/test_ids.py covers the algorithm."""

    def scan(self, text: str = LEAN) -> list:
        return ids.scan_file(text, "Notes/Exercises.lean")

    def test_the_scan_finds_every_anonymous_declaration_and_no_named_one(self):
        found = self.scan()
        self.assertEqual([(d.line, d.keyword) for d in found],
                         [(2, "example"), (6, "example"), (9, "example"), (12, "example"),
                          (15, "example"), (18, "instance"), (22, "example")])

    def test_comments_whitespace_and_spacing_do_not_change_the_hash(self):
        first, second = self.scan()[:2]
        self.assertEqual(first.statement_sha256, second.statement_sha256)
        self.assertEqual(first.signature, "example : volume (Box.unit 2) = 1")
        self.assertEqual(first.statement_sha256, ids.statement_sha256(first.signature))
        self.assertEqual(ids.hash_form(first.signature), "example:volume(Box.unit 2)=1")
        self.assertEqual(ids.statement_sha256("example : volume (Box.unit 2) = 1"),
                         ids.statement_sha256("example:volume (Box.unit 2)=1"))
        self.assertEqual(ids.hash_form("fun x ↦ x"), ids.hash_form("λ x => x"))
        self.assertNotEqual(ids.hash_form("f .foo"), ids.hash_form("f.foo"))

    def test_duplicates_take_an_ordinal_and_declared_ids_win(self):
        assigned = ids.assign_ids(self.scan())
        by_line = {d.line: assigned[d] for d in assigned}
        digest = ids.statement_sha256("example : volume (Box.unit 2) = 1")
        self.assertEqual(by_line[2], (f"example:{digest[:12]}", "statement_hash"))
        self.assertEqual(by_line[6], (f"example:{digest[:12]}~2", "statement_hash"))
        self.assertEqual(by_line[15], ("example:boxes-are-elementary", "declared"))
        self.assertTrue(re.fullmatch(r"instance:[0-9a-f]{12}", by_line[18][0]))
        self.assertEqual([rid for rid, _d in ids.ordinal_ids(assigned)], [f"example:{digest[:12]}~2"])
        self.assertEqual(by_line[2][0], PDF_EXAMPLE)

    def test_signature_at_cuts_a_named_declaration_the_same_way(self):
        text = ("theorem t (n : Nat) : n = n := rfl\n\n"
                "def d : Nat → Nat\n  | 0 => 1\n  | n + 1 => n\n\n"
                "def s : Inhabited Nat where\n  default := 0\n\n"
                "structure S where\n  x : Nat := 0\n\n"
                "def u := 1\n\n"
                "axiom a : False\n")
        self.assertEqual(ids.signature_at(text, 1, "theorem"),
                         ("theorem t (n : Nat) : n = n", ids.statement_sha256("theorem t (n : Nat) : n = n")))
        self.assertEqual(ids.signature_at(text, 3, "def")[0], "def d : Nat → Nat")      # a match alternative ends it
        self.assertEqual(ids.signature_at(text, 7, "def")[0], "def s : Inhabited Nat")  # a top-level where ends it
        self.assertIsNone(ids.signature_at(text, 10, "structure"))
        self.assertIsNone(ids.signature_at(text, 13, "def"))                            # untyped
        self.assertIsNone(ids.signature_at(text, 15, "axiom"))                          # no := or where
        self.assertIsNone(ids.signature_at(text, 2, "theorem"))                         # nothing starts there
        lean = "theorem volume_nonneg (B : Box d) : 0 ≤ B.volume := by\n  simp\n"
        decl = by_id(load("pdf-region.json")["declarations"], "Notes.Box.volume_nonneg")
        self.assertEqual(ids.signature_at(lean, 1, "theorem"), (decl["signature"], decl["statement_sha256"]))

    def test_a_bad_docstring_id_line_is_rejected(self):
        text = "/-- formal-companion id: Foo.bar -/\nexample : True := trivial\n"
        (decl,) = self.scan(text)
        self.assertIsNone(decl.declared_id)
        self.assertTrue(decl.rejected_tag.startswith("not-a-declared-id: "), decl.rejected_tag)
        text = "/-- formal-companion id: example:Unit-box -/\nexample : True := trivial\n"
        (decl,) = self.scan(text)
        self.assertEqual(decl.declared_id, "example:Unit-box")

    def test_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            ids.anonymous_id("theorem", "0" * 64)
        with self.assertRaises(ValueError):
            ids.anonymous_id("example", "abc")
        with self.assertRaises(ValueError):
            ids.anonymous_id("example", "0" * 64, 0)
        with self.assertRaises(ValueError):
            ids.passage_quote_id("  ")
        with self.assertRaises(ValueError):
            ids.passage_page_id(0, "title")


class TestPassageIds(unittest.TestCase):

    def test_the_quote_is_nfkc_and_whitespace_normalised(self):
        self.assertEqual(ids.normalize_text("deﬁne  the µ-measure\n"), "define the μ-measure")
        self.assertEqual(ids.passage_quote_id("deﬁne the µ-measure"),
                         ids.passage_quote_id("define  the μ-measure"))
        self.assertRegex(ids.passage_quote_id("a quote"), r"^passage-[0-9a-f]{8}$")
        self.assertNotEqual(ids.passage_quote_id("A quote"), ids.passage_quote_id("a quote"))
        self.assertEqual(ids.normalize_text("a b c　d"), "a b c d")     # the White_Space list
        self.assertEqual(ids.normalize_text("a​b"), "a​b")                   # not White_Space

    def test_the_page_form_uses_the_printed_page_and_the_title(self):
        self.assertRegex(ids.passage_page_id(151, "Maximal inequality"), r"^passage-p151-[0-9a-f]{8}$")
        self.assertEqual(ids.passage_page_id(7, "a  title"), ids.passage_page_id(7, "a title"))

    def test_label_ids(self):
        self.assertEqual(ids.item_label_id("Exercise", "1.2.3"), "exercise-1.2.3")
        self.assertEqual(ids.item_label_id("In-text Definition", "4", "ii"), "in-text-definition-4-ii")
        self.assertEqual(ids.item_label_id("Exercise", "1.4", "b'"), "exercise-1.4-b'")     # a prime stays


class TestAgreementWithJsonschema(unittest.TestCase):
    """Only when the real package is installed; this package never requires it."""

    def setUp(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is not installed")
        self.jsonschema = jsonschema
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_the_schema_is_a_valid_2020_12_schema(self):
        self.jsonschema.Draft202012Validator.check_schema(self.schema)

    def test_python_re_lets_a_trailing_dollar_match_before_a_final_newline_as_the_conformance_readme_says(self):
        """conformance/README.md: python-jsonschema accepts the three trailing-newline traps that the manifest,
        ajv and the package's own evaluator refuse, because Python's ``re`` lets ``$`` match before a final
        newline (docs/annotations.md 9.2 reads a trailing ``$`` as end of string)."""
        real = self.jsonschema.Draft202012Validator(self.schema)
        ours = Validator(self.schema)
        for name in ("trap-id-trailing-newline", "trap-commit-trailing-newline", "trap-version-trailing-newline"):
            path = ROOT / "conformance" / "documents" / "invalid" / f"{name}.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(trap=name):
                self.assertTrue(real.is_valid(doc), "python-jsonschema accepts it, as the README says")
                self.assertTrue(ours.errors(doc), "the package's evaluator refuses it, as the manifest says")

    def test_both_evaluators_agree_on_the_examples_and_on_mutations(self):
        real = self.jsonschema.Draft202012Validator(self.schema)
        ours = Validator(self.schema)
        docs = [load(n) for n in VALID + INVALID]
        rng = random.Random(0)
        values = [None, True, 0, -1, 1.5, "", "x", "1.0", [], {}, {"type": "TextQuoteSelector"}, "page=0",
                  "passage", "numbered", "site", "partial_only", {"doi": "10.1/x"}, [{"database": "stacks", "tag": "1"}]]

        def paths(x, p=()):
            yield p
            if isinstance(x, dict):
                for k, v in x.items():
                    yield from paths(v, p + (k,))
            elif isinstance(x, list):
                for i, v in enumerate(x):
                    yield from paths(v, p + (i,))
        for doc in docs:
            self.assertEqual(real.is_valid(doc), not ours.errors(doc))
        for _ in range(600):
            doc = copy.deepcopy(rng.choice(docs))
            where = rng.choice(list(paths(doc))[1:])
            parent = doc
            for key in where[:-1]:
                parent = parent[key]
            parent[where[-1]] = rng.choice(values)
            with self.subTest(path=where):
                self.assertEqual(real.is_valid(doc), not ours.errors(doc))


class TestTheSpec(unittest.TestCase):

    def text(self) -> str:
        return (ROOT / "docs" / "annotations.md").read_text(encoding="utf-8")

    def test_every_json_block_in_the_spec_parses(self):
        blocks = re.findall(r"```json\n(.*?)```", self.text(), re.S)
        self.assertGreaterEqual(len(blocks), 8)
        for block in blocks:
            with self.subTest(block=block[:40]):
                body = block.strip()
                if body.startswith('"selector"'):
                    body = "{" + body + "}"
                body = body.replace("[ ... ]", "[]")
                json.loads(body)

    def test_the_spec_names_every_invariant_the_checker_enforces(self):
        text = self.text()
        for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13):
            self.assertIn(f"| I{n} |", text)
        if "I14" not in text:
            self.skipTest("the specification predates I14 (profile gating) and is replaced separately")
        self.assertIn("| I14 |", text)
        self.assertNotIn("| I10 |", text, "I10 is retired: the external-urls lint, L1")
        for code in ("W-CONFORMS", "W-MEDIA", "W-RELATION", "W-XREF", "W-NEWER", "L1", "IJSON", "SCHEMA"):
            self.assertIn(f"`{code}`", text)

    def test_the_checkers_invariant_labels_are_the_tables(self):
        """Every invariant but I10 (retired: the external-urls lint, L1) and I11 (check()) has a section."""
        code = (PACKAGE / "validate.py").read_text(encoding="utf-8")
        labels = {int(n) for line in code.splitlines() if line.strip().startswith("# -- I")
                  for n in re.findall(r"I(\d+)", line)}
        self.assertEqual(labels, set(range(1, 15)) - {10, 11})
        self.assertIn("# I11", code)
        self.assertIn("# -- L1", code)

    def test_every_problem_and_warning_carries_a_code_of_the_table(self):
        """The codes are I1..I9, I11..I14 (I10 is retired), IJSON, SCHEMA, L1 and the W- warnings."""
        code = (PACKAGE / "validate.py").read_text(encoding="utf-8")
        emitted = set(re.findall(r'self\.(?:fail|warn)\("([A-Z0-9-]+)"', code))
        emitted |= set(re.findall(r'Problem\("([A-Z0-9-]+)"', code))
        self.assertEqual(emitted, {"IJSON", "SCHEMA", "I1", "I2", "I3", "I4", "I5", "I6", "I7", "I8", "I9",
                                   "I11", "I12", "I13", "I14", "L1", "W-CONFORMS", "W-MEDIA", "W-RELATION",
                                   "W-XREF", "W-NEWER", "W-SCHEMA-ID"})
        self.assertNotIn('"I10"', code)

    def test_the_spec_has_no_em_dash(self):
        self.assertNotIn("—", self.text())


if __name__ == "__main__":
    unittest.main()
