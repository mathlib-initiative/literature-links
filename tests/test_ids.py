"""The format's id rules (docs/annotations.md section 5): the display form, the hash form, passage and label ids.

The vectors below are pinned: an implementation of the format in any language
must give the same results, and a change to one of them re-keys ids.
"""
from __future__ import annotations

import hashlib
import importlib.util
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

from formal_companion_annotations import ids                                        # noqa: E402
from formal_companion_annotations import vocab                                      # noqa: E402

#: Signatures with the same hash form, and that form.
SAME_HASH_FORM = [
    (["example (x : T) : x = x", "example (x:T) : x = x", "example ( x : T ) : x=x", "example (x :T): x = x"],
     "example(x:T):x=x"),
    (["example : (fun x => x) = id", "example : (fun x ↦ x) = id", "example : (λ x => x) = id", "example : (λx↦x) = id"],
     "example:(fun x=>x)=id"),
    (["example (a b : ℕ) : a + b = b + a", "example (a b : ℕ) :\n    a + b = b + a",
      "example (a b : ℕ) : -- note\n  a + b = b + a", "example /- c -/ (a b : ℕ) : a + b = b + a"],
     "example(a b:ℕ):a+b=b+a"),
    (["example : ¬ p ∨ q → r", "example : ¬p∨q→r", "example : ¬ p ∨ q→ r"], "example:¬p∨q→r"),
    (["instance : Foo (Bar ℕ)", "instance : Foo (Bar  ℕ)", "instance:Foo(Bar ℕ)"], "instance:Foo(Bar ℕ)"),
    (['example : f "a" = \'b\'', 'example : f"a" = \'b\'', 'example : f "a"=\'b\''], 'example:f "a"=\'b\''),
    (["example : «my thing».foo = 1", "example : «my thing».foo=1"], "example:«my thing».foo=1"),
    (["example (x₁ : ℝ) (𝓝 : ℕ) : x₁ = x₁ ∧ 𝓝 = 𝓝", "example (x₁ : ℝ) (𝓝:ℕ):x₁=x₁∧𝓝=𝓝"], "example(x₁:ℝ)(𝓝:ℕ):x₁=x₁∧𝓝=𝓝"),
    (["example : a b = c", "example : a/- c -/b = c", "example : a -- c\n b = c"], "example:a b=c"),
    (["example : f = (fun x => x)", "example : f = (fun x = > x)"], "example:f=(fun x=>x)"),
    (["example : «x»r\"a\" = 1"], "example:«x» r\"a\"=1"),
    (["example : s = s!\"a {x} b\"", "example : s = s! \"a {x} b\""], 'example:s=s! "a {x} b"'),
    (['example : s!"{ {a} "b" }" = 1', 'example : s!"{ {a} "b" }"=1'], 'example:s! "{ {a} "b" }"=1'),
    (['example : s!"{ /- " -/ x}" y = 1', 'example : s!"{ /- " -/ x}" y=1'], 'example:s! "{ /- " -/ x}" y=1'),
]
#: Signatures whose hash forms all differ: the hash is syntactic.
DISTINCT = [
    ["example : f.foo = 1", "example : f .foo = 1", "example : f. foo = 1", "example : f . foo = 1"],
    ["example (a : T) (b : T) : a = b", "example (a b : T) : a = b", "example (x : T) (b : T) : x = b"],
    ["example : A → B", "example : A -> B", "example : ∀ x, p x", "example : forall x, p x"],
    ["example : a b = c", "example : ab = c"],
    ['example : s = "a b"', 'example : s = "a  b"', 'example : s = "a\\nb"', 'example : s = r"a b"'],
    ["example : f «a».b = 1", "example : f «a» .b = 1", "example : f «a b».c = 1"],
    ["example : f '' s = t", "example : f'' s = t", "example : f ' ' = t"],
    ["example : λ = 1", "example : Π = 1", "example : Σ = 1", "example : α = 1"],
    ["example : x.1 = 1.5", "example : x .1 = 1.5", "example : x.1 = 1 .5"],
]
#: Text and its display form (``normalize_statement``).
DISPLAY = [
    ('  example /- c -/ : "a  b" =\n\t x  -- t\n', 'example : "a  b" = x'),
    ('example (x : ℕ) : x = "a  b".length', 'example (x : ℕ) : x = "a  b".length'),
    ("example : a/- c -/= b", "example : a = b"),
    ("example :\n    -- a comment\n    letI : Foo := bar\n    Baz", "example : letI : Foo := bar Baz"),
    ('example : "a\nb" = "a\n  b"', 'example : "a\nb" = "a\n  b"'),
    ("example /- outer /- nested -/ still -/ : True", "example : True"),
    ('example : r#"a "  b"# = s', 'example : r#"a "  b"# = s'),
    ('example : s!"{f "x  y"}  z" = s', 'example : s!"{f "x  y"}  z" = s'),
    ("example : f 'a'  'b' = x'  y'", "example : f 'a' 'b' = x' y'"),
    ("example : '\\n'  = «a  b»", "example : '\\n' = «a  b»"),
    ("x\u000by  z", "x\u000by z"),
    ("x  y", "x  y"),
    ("a /--/ b", "a"), ("a /-- c -/ b", "a b"), ("a /-! c -/ b", "a b"), ("example : a /- b", "example : a"),
    ('s!"{ /- " -/ x}  c"  y', 's!"{ /- " -/ x}  c" y'), ("example : « a /- c -/ b", "example : « a b"),
]
#: (quote, id): the quote_hash id.
QUOTES = [
    ("Let  μ be a measure.", "passage-cd290c07"), ("deﬁne the µ-measure now", "passage-d71775f6"),
    ("define the μ-measure now", "passage-d71775f6"), ("A quote", "passage-de8b1bbd"), ("a quote", "passage-acfd5319"),
    ("a b\u0085c d\u000be", "passage-52cf9f06"), ("a b c d e", "passage-52cf9f06"),
    ("a\u001cb", "passage-3b03cf1a"),
]
#: (printed page, title, id): the page_title_hash id.
TITLES = [(151, "Maximal inequality", "passage-p151-cabb8ef1"), (7, "a  title", "passage-p7-aa4e9c10"),
          (7, "a title", "passage-p7-aa4e9c10")]
#: (kind, number, sub, id): the label id.
LABELS = [("Exercise", "1.2.3", None, "exercise-1.2.3"), ("In-text Definition", "4", "ii", "in-text-definition-4-ii"),
          ("  Théorème (main) ", "2", None, "th-or-me-main-2"), ("Section 2 Lemma", "5", None, "section-2-lemma-5"),
          ("Lemma", "1", "", "lemma-1"), ("Exercise", "1.4", "b'", "exercise-1.4-b'"), ("Lemma", "3", "f''", "lemma-3-f''"),
          ("İx", "1", None, "i-x-1")]


class TestTheStatementHash(unittest.TestCase):

    def test_formatting_comments_and_the_two_aliases_do_not_change_the_hash_form(self):
        for signatures, form in SAME_HASH_FORM:
            for signature in signatures:
                with self.subTest(signature=signature):
                    self.assertEqual(ids.hash_form(signature), form)
                    self.assertEqual(ids.statement_sha256(signature),
                                     hashlib.sha256(form.encode("utf-8")).hexdigest())

    def test_everything_else_does(self):
        for signatures in DISTINCT:
            with self.subTest(signatures=signatures):
                self.assertEqual(len({ids.hash_form(s) for s in signatures}), len(signatures))

    def test_the_display_form(self):
        for text, display in DISPLAY:
            with self.subTest(text=text):
                self.assertEqual(ids.normalize_statement(text), display)
                self.assertEqual(ids.normalize_statement(display), display, "idempotent")

    def test_the_hash_form_of_a_text_is_the_hash_form_of_its_display_form(self):
        rng = random.Random(0)
        pieces = ["example", " ", "  ", "\n", "\t", "(x : ℕ)", ":", "=", "f.foo", " .foo", "λ", "↦", "=>", "'a'", "x'",
                  '"a  b"', "«p q»", "-- c\n", "/- c -/", "/- a /- b -/ -/", 'r#"q"#', 's!"{x}"', "ℝ", "₁", "Π"]
        for _ in range(2000):
            text = "".join(rng.choice(pieces) for _ in range(rng.randint(1, 12)))
            with self.subTest(text=text):
                self.assertEqual(ids.hash_form(text), ids.hash_form(ids.normalize_statement(text)))

    def test_the_example_ids_are_the_hash_rule(self):
        self.assertEqual(ids.anonymous_id("example", ids.statement_sha256("example : volume (Box.unit 2) = 1")),
                         "example:a3be9ccfbb38")
        self.assertEqual(ids.anonymous_id("instance", ids.statement_sha256("instance : IsProbabilityMeasure coinMeasure")),
                         "instance:99758575708c")
        self.assertEqual(ids.anonymous_id("example", "0" * 64, 3), "example:000000000000~3")
        self.assertEqual(ids.private_id("Notes.Basic", "Notes.Box.volume_aux"), "private:Notes.Basic:Notes.Box.volume_aux")

    def test_bad_input_is_a_value_error(self):
        for call in (lambda: ids.anonymous_id("theorem", "0" * 64), lambda: ids.anonymous_id("example", "abc"),
                     lambda: ids.anonymous_id("example", "0" * 64, 0), lambda: ids.private_id("", "x"),
                     lambda: ids.statement_sha256("example : " + chr(0xD800)),
                     lambda: ids.passage_quote_id("x" + chr(0xD800))):
            with self.assertRaises(ValueError):
                call()


class TestTheIdGrammars(unittest.TestCase):

    def test_hash_and_declared_ids_full_match_vocabs_grammar(self):
        self.assertIn(vocab.HASH_ID_PATTERN, ids.HASH_ID.pattern)
        self.assertIn(vocab.DECLARED_ID_PATTERN, ids.DECLARED_ID.pattern)
        for good in ("example:0123456789ab", "instance:0123456789ab~2", "instance:0123456789ab~10"):
            self.assertTrue(ids.HASH_ID.fullmatch(good) and ids.HASH_ID.match(good), good)
        for bad in ("example:0123456789ab\n", "example:0123456789ab~1", "example:0123456789abc", " example:0123456789ab",
                    "theorem:0123456789ab", "example:0123456789AB", "example:0123456789ab~02"):
            self.assertIsNone(ids.HASH_ID.match(bad), repr(bad))
        for good in ("example:foo", "instance:Ex.1_2-b", "example:9lives", "example:0123456789abc",
                     "example:L1-seminorm-ae-laws"):
            self.assertTrue(ids.DECLARED_ID.fullmatch(good), good)
        for bad in ("example:foo\n", "example:0123456789ab", "example:0123456789ab~3", "example:-x", "example:_x",
                    "example:a b", "example:", "theorem:foo", "Foo.bar", "example:foo​"):
            self.assertIsNone(ids.DECLARED_ID.match(bad), repr(bad))


class TestItemIds(unittest.TestCase):

    def test_passage_ids_hash_the_normalised_quote_or_title(self):
        for quote, rid in QUOTES:
            with self.subTest(quote=quote):
                self.assertEqual(ids.passage_quote_id(quote), rid)
        for page, title, rid in TITLES:
            self.assertEqual(ids.passage_page_id(page, title), rid)
        for call in (lambda: ids.passage_quote_id("     "), lambda: ids.passage_page_id(0, "title"),
                     lambda: ids.passage_page_id(True, "title"), lambda: ids.passage_page_id(3, " \t\n")):
            with self.assertRaises(ValueError):
                call()

    def test_normalize_text_is_nfkc_and_the_white_space_list(self):
        self.assertEqual(ids.normalize_text("  deﬁne  the µ-measure\n"), "define the μ-measure")
        self.assertEqual(ids.normalize_text("a\u001cb\u001fc"), "a\u001cb\u001fc", "not White_Space")
        self.assertEqual(ids.normalize_text("a​b　c"), "a​b c")
        self.assertEqual(ids.normalize_text("A"), "A", "case is kept")

    def test_label_ids(self):
        for kind, number, sub, rid in LABELS:
            with self.subTest(kind=kind, sub=sub):
                self.assertEqual(ids.item_label_id(kind, number, sub), rid)
        for kind, number in (("---", "1"), ("Lemma", "")):
            with self.assertRaises(ValueError):
                ids.item_label_id(kind, number)


if __name__ == "__main__":
    unittest.main()
