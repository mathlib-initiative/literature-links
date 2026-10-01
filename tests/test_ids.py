"""The id rules (docs/id-algorithm.md): the conformance vectors and the ``ids`` API.

Every file under ``conformance/ids/`` is loaded and every case in it is run
against the reference implementation; a new vector file needs no new test.
The API tests pin what the vectors cannot: the public names, the ``fullmatch``
semantics of the id grammars and the error cases.
"""
from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import ids                                        # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402

VECTORS = ROOT / "conformance" / "ids"
#: The vector files this suite expects to find; extra files are run too.
EXPECTED_FILES = {"lexing.json", "modifiers-and-prefixes.json", "instances.json", "header-end.json",
                  "hash-form.json", "declared-ids.json", "ordinals.json", "named-signatures.json",
                  "passages.json", "item-labels.json"}
REJECTION_CODES = ("tag-not-alone", "not-a-declared-id", "wrong-keyword", "conflicting-tags")


def load_vectors() -> dict[str, list[dict]]:
    files = sorted(VECTORS.glob("*.json"))
    out = {}
    for path in files:
        with open(path, encoding="utf-8") as fh:
            cases = json.load(fh)
        assert isinstance(cases, list) and cases, path
        out[path.name] = cases
    return out


def rejection_codes(rejected: str | None) -> list[str]:
    """The stable codes at the start of each ``; ``-separated entry of ``rejected_tag``."""
    if rejected is None:
        return []
    codes = []
    for entry in rejected.split("; "):
        code = entry.split(":", 1)[0]
        if code in REJECTION_CODES:
            codes.append(code)
    return codes


def expected_entry(decl: ids.AnonymousDecl, assigned: dict, with_file: bool) -> dict:
    """What a vector's expected entry for ``decl`` must say."""
    entry = {"line": decl.line, "keyword": decl.keyword, "signature": decl.signature,
             "hash_form": ids.hash_form(decl.signature), "statement_sha256": decl.statement_sha256,
             "id": assigned[decl][0]}
    if with_file:
        entry["file"] = decl.file
    if decl.declared_id:
        entry["declared_id"] = decl.declared_id
    if decl.rejected_tag:
        entry["rejected_tag"] = rejection_codes(decl.rejected_tag)
    return entry


class TestConformanceVectors(unittest.TestCase):
    """Every case of every file under conformance/ids/ holds."""

    @classmethod
    def setUpClass(cls):
        cls.vectors = load_vectors()

    def test_the_expected_files_exist(self):
        self.assertTrue(EXPECTED_FILES <= set(self.vectors), sorted(EXPECTED_FILES - set(self.vectors)))

    def run_case(self, case: dict) -> None:
        if "expected" in case and "lean" in case:
            decls = ids.scan_file(case["lean"], "Vec/File.lean")
            assigned = ids.assign_ids(decls)
            got = [expected_entry(d, assigned, with_file=False) for d in decls]
            self.assertEqual(got, case["expected"])
            for d in decls:
                self.assertEqual(hashlib.sha256(ids.hash_form(d.signature).encode("utf-8")).hexdigest(),
                                 d.statement_sha256)
                self.assertEqual(ids.normalize_statement(d.signature), d.signature, "display form is idempotent")
                self.assertTrue(ids.HASH_ID.fullmatch(assigned[d][0]) or ids.DECLARED_ID.fullmatch(assigned[d][0]))
        elif "expected" in case and "files" in case:
            decls = []
            for f in case["files"]:
                decls += ids.scan_file(f["lean"], f["path"])
            assigned = ids.assign_ids(decls)
            order = sorted(decls, key=lambda d: (d.file.encode("utf-16-be", "surrogatepass"), d.line))
            got = [expected_entry(d, assigned, with_file=True) for d in order]
            self.assertEqual(got, case["expected"])
        elif "hash_form" in case:
            for sig in case["signatures"]:
                self.assertEqual(ids.hash_form(sig), case["hash_form"], sig)
            digests = {ids.statement_sha256(s) for s in case["signatures"]}
            self.assertEqual(len(digests), 1)
        elif case.get("distinct"):
            forms = [ids.hash_form(s) for s in case["signatures"]]
            self.assertEqual(len(set(forms)), len(forms), forms)
        elif "text" in case and "signature" in case:
            self.assertEqual(ids.normalize_statement(case["text"]), case["signature"])
            self.assertEqual(ids.normalize_statement(case["signature"]), case["signature"])
            self.assertEqual(ids.hash_form(case["text"]), ids.hash_form(case["signature"]))
        elif "text" in case and "normalized" in case:
            self.assertEqual(ids.normalize_text(case["text"]), case["normalized"])
        elif "keyword" in case and "line" in case:
            got = ids.signature_at(case["lean"], case["line"], case["keyword"])
            if "signature" in case:
                self.assertEqual(got, (case["signature"], case["statement_sha256"]))
            else:
                self.assertIsNone(got)
        elif "quote" in case:
            if case.get("error"):
                with self.assertRaises(ValueError):
                    ids.passage_quote_id(case["quote"])
            else:
                self.assertEqual(ids.passage_quote_id(case["quote"]), case["id"])
                self.assertRegex(case["id"], r"\A" + vocab.PASSAGE_QUOTE_ID_PATTERN + r"\Z")
        elif "printed_page" in case:
            if case.get("error"):
                with self.assertRaises(ValueError):
                    ids.passage_page_id(case["printed_page"], case["title"])
            else:
                self.assertEqual(ids.passage_page_id(case["printed_page"], case["title"]), case["id"])
                self.assertRegex(case["id"], r"\A" + vocab.PASSAGE_PAGE_ID_PATTERN + r"\Z")
        elif "kind" in case:
            self.assertEqual(ids.item_label_id(case["kind"], case["number"], case.get("sub")), case["id"])
        else:
            self.fail(f"unknown vector shape: {sorted(case)}")

    def test_every_vector(self):
        count = 0
        for fname, cases in self.vectors.items():
            for case in cases:
                with self.subTest(file=fname, case=case["name"]):
                    self.run_case(case)
                    count += 1
        self.assertGreater(count, 100)

    def test_the_statement_hash_vectors_cover_the_rules(self):
        """At least 60 statement-hash declarations, with pairs that hash equal and pairs that differ."""
        entries = [e for cases in self.vectors.values() for c in cases for e in c.get("expected", [])]
        self.assertGreaterEqual(len(entries), 60)
        self.assertTrue(any("~" in e["id"] for e in entries), "some vector pins an ordinal")
        self.assertTrue(any("declared_id" in e for e in entries))
        self.assertTrue(any("rejected_tag" in e for e in entries))
        self.assertTrue(any(e["keyword"] == "instance" for e in entries))
        groups = [c for cases in self.vectors.values() for c in cases if "hash_form" in c and len(c["signatures"]) > 1]
        self.assertGreaterEqual(len(groups), 5)
        self.assertGreaterEqual(sum(1 for cases in self.vectors.values() for c in cases if c.get("distinct")), 5)

    def test_vectors_are_synthetic_and_self_consistent(self):
        for fname, cases in self.vectors.items():
            names = [c["name"] for c in cases]
            self.assertEqual(len(names), len(set(names)), f"duplicate case name in {fname}")
            for c in cases:
                for e in c.get("expected", []):
                    self.assertEqual(hashlib.sha256(e["hash_form"].encode("utf-8")).hexdigest(), e["statement_sha256"])
                    self.assertTrue(e["id"].startswith(e["keyword"] + ":"))


class TestPublicApi(unittest.TestCase):

    def test_all_is_exactly_the_public_api(self):
        self.assertEqual(sorted(ids.__all__), sorted([
            "AnonymousDecl", "scan_file", "assign_ids", "ordinal_ids", "statement_sha256", "hash_form",
            "normalize_statement", "anonymous_id", "private_id", "signature_at", "item_label_id",
            "passage_quote_id", "passage_page_id", "normalize_text", "HASH_ID", "DECLARED_ID"]))
        for name in ids.__all__:
            self.assertTrue(hasattr(ids, name), name)
        for old in ("strip_comments", "blank_literals", "token_at", "named_signature", "comment_tags",
                    "statement_span", "declared_tag"):
            self.assertFalse(hasattr(ids, old), f"{old} is not public any more")
        self.assertEqual([f.name for f in dataclasses.fields(ids.AnonymousDecl)],
                         ["file", "line", "keyword", "statement_sha256", "typed", "declared_id", "signature",
                          "rejected_tag", "comment_tags"])

    def test_the_grammars_are_vocab_s_and_use_fullmatch(self):
        self.assertIn(vocab.HASH_ID_PATTERN, ids.HASH_ID.pattern)
        self.assertIn(vocab.DECLARED_ID_PATTERN, ids.DECLARED_ID.pattern)
        for good in ("example:0123456789ab", "instance:0123456789ab~2", "instance:0123456789ab~10"):
            self.assertTrue(ids.HASH_ID.fullmatch(good), good)
            self.assertTrue(ids.HASH_ID.match(good), good)
        for bad in ("example:0123456789ab\n", "example:0123456789ab~1", "example:0123456789abc",
                    " example:0123456789ab", "example:0123456789ab ", "theorem:0123456789ab",
                    "example:0123456789AB", "example:0123456789ab~02"):
            self.assertIsNone(ids.HASH_ID.fullmatch(bad), repr(bad))
            self.assertIsNone(ids.HASH_ID.match(bad), repr(bad))
        for good in ("example:foo", "instance:Ex.1_2-b", "example:9lives", "example:0123456789abc"):
            self.assertTrue(ids.DECLARED_ID.fullmatch(good), good)
        for bad in ("example:foo\n", "example:0123456789ab", "example:0123456789ab~3", "example:-x",
                    "example:_x", "example:a b", "example:", "example:foo​", "instance:f﻿"):
            self.assertIsNone(ids.DECLARED_ID.fullmatch(bad), repr(bad))
            self.assertIsNone(ids.DECLARED_ID.match(bad), repr(bad))

    def test_statement_sha256_is_the_hash_form_s(self):
        sig = "example (x : ℕ) : x = x"
        self.assertEqual(ids.hash_form(sig), "example(x:ℕ):x=x")
        self.assertEqual(ids.statement_sha256(sig), hashlib.sha256("example(x:ℕ):x=x".encode()).hexdigest())
        self.assertEqual(ids.statement_sha256("example (x:ℕ) :\n  x = x"), ids.statement_sha256(sig))
        self.assertEqual(ids.statement_sha256("example /- c -/ (x : ℕ) : x = x"), ids.statement_sha256(sig))
        self.assertEqual(ids.hash_form("fun x ↦ x"), ids.hash_form("λ x => x"))
        self.assertNotEqual(ids.hash_form("f.foo"), ids.hash_form("f .foo"))

    def test_normalize_statement_is_the_display_form(self):
        self.assertEqual(ids.normalize_statement("  example /- c -/ : \"a  b\" =\n\t x  -- t\n"), 'example : "a  b" = x')
        self.assertEqual(ids.normalize_statement("example : a/- c -/= b"), "example : a = b")
        self.assertEqual(ids.normalize_statement("x y"), "x y", "only the four whitespace code points collapse")
        self.assertEqual(ids.normalize_statement("x\u000by"), "x\u000by")

    def test_id_constructors_and_their_errors(self):
        digest = "0" * 64
        self.assertEqual(ids.anonymous_id("example", digest), "example:000000000000")
        self.assertEqual(ids.anonymous_id("instance", digest, 3), "instance:000000000000~3")
        self.assertEqual(ids.private_id("Notes.Basic", "Notes.Box.volume_aux"), "private:Notes.Basic:Notes.Box.volume_aux")
        with self.assertRaises(ValueError):
            ids.anonymous_id("theorem", digest)
        with self.assertRaises(ValueError):
            ids.anonymous_id("example", "abc")
        with self.assertRaises(ValueError):
            ids.anonymous_id("example", digest, 0)
        with self.assertRaises(ValueError):
            ids.private_id("", "x")
        with self.assertRaises(ValueError):
            ids.passage_quote_id("  ")
        with self.assertRaises(ValueError):
            ids.passage_page_id(0, "title")
        with self.assertRaises(ValueError):
            ids.passage_page_id(True, "title")
        with self.assertRaises(ValueError):
            ids.item_label_id("---", "1")
        with self.assertRaises(ValueError):
            ids.item_label_id("Lemma", "")

    def test_normalize_text_uses_the_explicit_white_space_list(self):
        self.assertEqual(ids.normalize_text("deﬁne  the µ-measure\n"), "define the μ-measure")
        self.assertEqual(ids.normalize_text(" a b\u0085c　"), "a b c")
        self.assertEqual(ids.normalize_text("a\u001cb\u001dc\u001ed\u001fe"), "a\u001cb\u001dc\u001ed\u001fe")
        self.assertEqual(ids.passage_quote_id("deﬁne the µ-measure"), ids.passage_quote_id("define  the μ-measure"))
        self.assertNotEqual(ids.passage_quote_id("A quote"), ids.passage_quote_id("a quote"))
        self.assertRegex(ids.passage_page_id(151, "Maximal inequality"), r"\Apassage-p151-[0-9a-f]{8}\Z")
        self.assertEqual(ids.item_label_id("Exercise", "1.2.3"), "exercise-1.2.3")
        self.assertEqual(ids.item_label_id("In-text Definition", "4", "ii"), "in-text-definition-4-ii")
        self.assertEqual(ids.item_label_id("Exercise", "1.4", "b'"), "exercise-1.4-b'")     # sub is verbatim
        self.assertEqual(ids.item_label_id("Lemma", "3", "f''"), "lemma-3-f''")


class TestScanning(unittest.TestCase):

    LEAN = ("/-- `example:first` -/\nexample : True := trivial\n\n"
            "example (x : ℕ) :\n    x = x := rfl\n\n"
            "public instance : Foo := ⟨1⟩\ninstance (priority := 100)\n    named : Foo := ⟨1⟩\n"
            "example (x : ℕ) : x = x := rfl\n"
            "/- `example:tag` prose -/\nexample (d : ℕ) := t\n")

    def scan(self):
        return ids.scan_file(self.LEAN, "Notes/A.lean")

    def test_scan_file_finds_the_anonymous_declarations(self):
        found = self.scan()
        self.assertEqual([(d.line, d.keyword, d.typed) for d in found],
                         [(2, "example", True), (4, "example", True), (7, "instance", True),
                          (10, "example", True), (12, "example", False)])
        self.assertEqual(found[0].declared_id, "example:first")
        self.assertEqual(found[0].comment_tags, ("example:first",))
        self.assertEqual(found[1].signature, "example (x : ℕ) : x = x")
        self.assertEqual(found[1].statement_sha256, found[3].statement_sha256)
        self.assertEqual(found[2].signature, "instance : Foo")
        self.assertEqual(found[4].signature, "example (d : ℕ) := t")
        self.assertEqual(rejection_codes(found[4].rejected_tag), ["tag-not-alone"])
        self.assertEqual(found[4].comment_tags, ("example:tag",))
        self.assertIsNone(found[4].declared_id)
        for d in found:
            self.assertEqual(d.file, "Notes/A.lean")
            self.assertEqual(d.statement_sha256, ids.statement_sha256(d.signature))

    def test_assign_ids_and_ordinal_ids(self):
        found = self.scan()
        assigned = ids.assign_ids(found)
        digest = found[1].statement_sha256
        self.assertEqual(assigned[found[0]], ("example:first", "declared"))
        self.assertEqual(assigned[found[1]], (f"example:{digest[:12]}", "statement_hash"))
        self.assertEqual(assigned[found[3]], (f"example:{digest[:12]}~2", "statement_hash"))
        self.assertEqual([rid for rid, _d in ids.ordinal_ids(assigned)], [f"example:{digest[:12]}~2"])
        self.assertIs(ids.ordinal_ids(assigned)[0][1], found[3])

    def test_ordinals_follow_utf16_path_order_then_line(self):
        a = ids.scan_file("example : True := trivial\n", "Vec/～.lean")
        b = ids.scan_file("example : True := trivial\n", "Vec/\U0001d400.lean")
        c = ids.scan_file("example : True := trivial\n", "Vec/A/B.lean")
        d = ids.scan_file("example : True := trivial\n", "Vec/A.lean")
        assigned = ids.assign_ids(a + b + c + d)
        ordinal = {decl.file: assigned[decl][0].partition("~")[2] for decl in a + b + c + d}
        self.assertEqual(ordinal, {"Vec/A.lean": "", "Vec/A/B.lean": "2", "Vec/\U0001d400.lean": "3",
                                   "Vec/～.lean": "4"})

    def test_signature_at(self):
        text = ("theorem foo (x : ℕ) :\n    x = x := rfl\ndef f : ℕ → ℕ\n  | 0 => 1\naxiom ax : True\n"
                "example : True := trivial\nstructure S : Type where\n  x : ℕ\n")
        self.assertEqual(ids.signature_at(text, 1, "theorem"),
                         ("theorem foo (x : ℕ) : x = x", ids.statement_sha256("theorem foo (x : ℕ) : x = x")))
        self.assertEqual(ids.signature_at(text, 3, "def")[0], "def f : ℕ → ℕ")
        self.assertIsNone(ids.signature_at(text, 5, "axiom"))
        self.assertEqual(ids.signature_at(text, 6, "example"), (ids.scan_file(text, "T")[0].signature,
                                                                  ids.scan_file(text, "T")[0].statement_sha256))
        self.assertIsNone(ids.signature_at(text, 7, "structure"))
        self.assertIsNone(ids.signature_at(text, 2, "theorem"))
        self.assertIsNone(ids.signature_at(text, 1, "lemma"))
        for word in ("open", "private", "alias", "namespace", ""):      # not a keyword of 7.3: refused, not cut
            with self.assertRaisesRegex(ValueError, "not a declaration keyword with a signature"):
                ids.signature_at("open Foo in private theorem t : True := trivial\n", 1, word)
        self.assertEqual(ids.signature_at("open Foo in private theorem t : True := trivial\n", 1, "theorem")[0],
                         "theorem t : True")

    def test_scanner_regressions(self):
        """The bugs the release candidate fixed, one line each (the vectors have the full set)."""
        def sigs(text):
            return [d.signature for d in ids.scan_file(text, "T")]
        self.assertEqual(sigs("public instance : Foo := ⟨1⟩\n"), ["instance : Foo"])
        self.assertEqual(sigs("instance (priority := 100)\n    fooBar : Foo := ⟨1⟩\n"), [])
        self.assertEqual(sigs("instance (priority := (100 : ℕ)) : Foo := ⟨1⟩\n"), ["instance (priority := (100 : ℕ)) : Foo"])
        self.assertEqual(sigs("/-- doc -/ example (x : ℕ) :\n    x + 0 = x := rfl\n"), ["example (x : ℕ) : x + 0 = x"])
        self.assertEqual(sigs("instance : Foo Bool\n    | true => 1\n    | false => 2\n"), ["instance : Foo Bool"])
        self.assertEqual(sigs("example : P a\n  b ∧\nQ c := sorry\n"), ["example : P a b ∧ Q c"])
        self.assertEqual(sigs("def «a\"b» := 1\nexample : True := trivial\ndef c := \"x\"\n"), ["example : True"])
        self.assertEqual(sigs("example : let f : ℕ → ℕ | _ => 1; f 0 = 1 := rfl\n"), ["example : let f : ℕ → ℕ | _ => 1; f 0 = 1"])
        self.assertEqual(sigs("example : a/- c -/= b := h\n"), ["example : a = b"])
        self.assertEqual(sigs("﻿example : True := trivial\n"), ["example : True"])
        stolen = ids.scan_file("theorem t : True := trivial -- `example:stolen`\nexample : True := trivial\n", "T")
        self.assertIsNone(stolen[0].declared_id)
        same_line = ids.scan_file("/-- formal-companion id: example:bar -/ example : True := trivial\n", "T")
        self.assertEqual(same_line[0].declared_id, "example:bar")
        legacy = ids.scan_file("/-- other-tool id: example:bar -/\nexample : True := trivial\n", "T")
        self.assertIsNone(legacy[0].declared_id)
        for note in ('  /- c -/ library_note "foo"\n', '/- multi\nline -/ library_note "foo"\n',
                     'library_note "foo"\n', '#adaptation_note\n'):            # 12.1 (3): the note's body
            hidden = ids.scan_file(note + "/-- `example:hidden` -/\nexample : True := trivial\n", "T")
            self.assertIsNone(hidden[0].declared_id, note)
        read = ids.scan_file('/- c -/ theorem t : True := trivial\n/-- `example:read` -/\n'
                             'example : True := trivial\n', "T")
        self.assertEqual(read[0].declared_id, "example:read")

    def test_scan_file_never_crashes_on_odd_input(self):
        nested = tuple("example : " + 's!"{' * depth + "x" + '}"' * depth + " := rfl\n" for depth in (333, 5000))
        for text in ("", "\n", "example", "instance", "example :", "/-", "--", "\"", "'", "«", "r#\"", "s!\"{",
                     "@[", "open Foo in", "#guard_msgs in", "example : True :=", "instance (priority := 1",
                     "﻿", "\r\n\r\n", "example : \"unterminated\nexample : True := trivial\n",
                     "example : x |\n| y := z\n", 's!"{s!"{', 's!"{ r#"}"# ',
                     'example : s!"{"}"} = 1 := rfl\n') + nested:
            with self.subTest(text=text[:40]):
                for d in ids.scan_file(text, "T"):             # the nested holes were once a RecursionError
                    self.assertEqual(d.statement_sha256, ids.statement_sha256(d.signature))
                    self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", d.statement_sha256))
        self.assertEqual(ids.scan_file(nested[0], "T")[0].signature, nested[0][:-len(" := rfl\n")])

    def test_a_lone_surrogate_is_refused_with_a_value_error(self):
        """Section 2: the file is UTF-8, so text holding a lone surrogate (a ``surrogateescape`` decode of
        bad bytes) is outside the algorithm; it is refused with a ValueError, not a UnicodeEncodeError."""
        bad = "a" + chr(0xDCFF) + "b"
        for call in (lambda: ids.scan_file(f"example : {bad} = 1 := rfl\n", "T"),
                     lambda: ids.statement_sha256(bad), lambda: ids.passage_quote_id(bad),
                     lambda: ids.passage_page_id(1, bad)):
            with self.assertRaisesRegex(ValueError, "lone surrogate"):
                call()
        self.assertEqual(ids.scan_file("example : ab = 1 := rfl\n", "T")[0].signature, "example : ab = 1")

    def test_scan_file_is_linear_in_the_number_of_lines(self):
        """Line numbers come from a table of line starts and the limit search copies no list, so a generated
        file of many one-line declarations scans in linear time (both were quadratic once)."""
        text = "example : True := trivial\n" * 60000
        start = time.perf_counter()
        decls = ids.scan_file(text, "T")
        elapsed = time.perf_counter() - start
        self.assertEqual([d.line for d in decls[-3:]], [59998, 59999, 60000])
        self.assertLess(elapsed, 5.0, f"60000 declarations took {elapsed:.1f}s: a quadratic pass takes over ten")


if __name__ == "__main__":
    unittest.main()
