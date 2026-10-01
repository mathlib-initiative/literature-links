# The id algorithm

This document is normative. It states, step by step, how a producer derives
the mechanical ids of `docs/annotations.md` section 7: the statement-hash id
of an anonymous Lean declaration, its declared-id override, the ordinals, and
the ids of passages and numbered items. The key words MUST, MUST NOT, SHOULD
and MAY are to be read as in RFC 2119.

`src/formal_companion_annotations/ids.py` is the reference implementation.
The files under `conformance/ids/` are the test vectors: an implementation in
any language MUST reproduce every one of them. Where this text and a vector
disagree, one of them has a bug; report it.

The rules are frozen with the format. Changing one re-keys every id it
produces.

## 1. Character sets

All positions count Unicode code points, never bytes or UTF-16 units.

**1.1 Whitespace.** Everywhere in sections 2 to 13, *whitespace* means
exactly these four code points: U+0009 (tab), U+000A (line feed), U+000D
(carriage return), U+0020 (space). Nothing else is whitespace, whatever its
Unicode properties.

**1.2 Word characters.** A *word character* is one of:

- `A`–`Z` (U+0041–U+005A), `a`–`z` (U+0061–U+007A), `0`–`9` (U+0030–U+0039);
- `_` U+005F, `'` U+0027, `!` U+0021, `?` U+003F, `.` U+002E;
- Greek and Coptic U+0370–U+03FF, except λ U+03BB, Π U+03A0 and Σ U+03A3;
- Greek Extended U+1F00–U+1FFE;
- Letterlike Symbols U+2100–U+214F (ℕ, ℤ, ℚ, ℝ, ℂ, ℓ, ...);
- Mathematical Alphanumeric Symbols U+1D49C–U+1D59F;
- subscripts U+2080–U+2089, U+2090–U+209C, U+1D62–U+1D6A and U+2C7C.

This is the set of code points that can appear inside a Lean 4 identifier,
with the dot included so that `Foo.bar`, `x.1`, `1.5` and a leading-dot
`.inl` are single tokens.

**1.3 Brackets.** The *opening brackets* are `(` U+0028, `[` U+005B, `{`
U+007B, `⟨` U+27E8, `⦃` U+2983 and `⟦` U+27E6; the *closing brackets* are `)`
U+0029, `]` U+005D, `}` U+007D, `⟩` U+27E9, `⦄` U+2984 and `⟧` U+27E7.

**1.4 `White_Space`** (passage ids only, section 13). The 25 code points
with the Unicode `White_Space` property: U+0009, U+000A, U+000B, U+000C,
U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000, U+2001, U+2002, U+2003,
U+2004, U+2005, U+2006, U+2007, U+2008, U+2009, U+200A, U+2028, U+2029,
U+202F, U+205F, U+3000. An implementation MUST use this list and MUST NOT use
a library's notion of whitespace (Python's `\s` and `str.split()`, for
instance, also match U+001C–U+001F).

## 2. Input

1. The file is decoded as UTF-8.
2. A leading U+FEFF (byte order mark) is removed.
3. Every U+000D U+000A pair is replaced by U+000A.
4. Lines are the pieces between U+000A code points; the first line is line 1.
   No other code point ends a line.

Everything below works on the resulting text *T*.

## 3. Lexing

Lexing finds the *spans* of *T*: the comments and the literals. Spans never
overlap and are found left to right. A span has a *kind*: `doc`, `moddoc`,
`block`, `line` (the comment kinds) or `string`, `char`, `guil` (the literal
kinds).

Scanning starts at offset 0. At each step, find the smallest offset *j* at or
after the current position where one of `/-`, `--`, `"`, `'` or `«` begins
(the two-character sequences must be present in full). If there is none,
lexing is finished. Otherwise apply the rule for what begins at *j*; each
rule says where scanning resumes.

**3.1 Block comment (`/-`).** The kind is `doc` when `/--` begins at *j*,
`moddoc` when `/-!` begins at *j*, otherwise `block`. The body starts after
the opener: 3 code points for `doc` and `moddoc`, 2 for `block`. From there,
with a nesting depth of 1, repeatedly find the next occurrence of `/-` or
`-/` (the leftmost; they cannot begin at the same offset): `/-` raises the
depth by one, `-/` lowers it by one; move past the two characters and
continue. The span ends after the `-/` that brings the depth to 0. If the
text ends first, the span ends at the end of the text. Scanning resumes at
the end of the span. (So `/-- -/` is a closed doc comment and `/--/` is not,
as in Lean.)

**3.2 Line comment (`--`).** The span runs to the next U+000A, exclusive, or
to the end of the text. Scanning resumes at that newline.

**3.3 String literal (`"`).** Let *h* be the number of `#` code points
immediately before *j*, and *r* the code point before those. The literal is:

- *raw* if *r* is `r` (U+0072) and the code point before *r* is not a word
  character (or *r* is at offset 0). The span begins at *r*. Its body starts
  after the `"` at *j* and ends after the first `"` that is followed by *h*
  `#` code points; the span includes those `#`. No escape is recognised.
- otherwise *plain*, and *interpolated* when the two code points before *j*
  are `s!`, `m!` or `f!` and the code point before those is not a word
  character (or there is none). The span begins at *j*. Its body is read from
  *j* + 1: a `\` skips the next code point; a `"` ends the span after itself;
  in an interpolated literal, a `{` opens a *hole* that ends after the `}`
  that balances it, where inside the hole every comment, string, char and
  `«…»` (all rules of this section, applied recursively) is skipped whole and
  only `{` and `}` outside those count; every other code point is body.

In both cases, when the text ends first the span ends at the end of the
text. Scanning resumes at the end of the span. The look-back for `#` and `r`
never reaches into an earlier span.

**3.4 Char literal (`'`).** If the code point before *j* is a word character,
the `'` is a prime: scanning resumes at *j* + 1. Otherwise the span is the
first of these shapes that matches at *j*, and scanning resumes at its end:

1. `'`, one code point that is neither `\` nor `'`, `'` (three code points);
2. `'\x`, two hex digits (`0`–`9`, `A`–`F`, `a`–`f`), `'`;
3. `'\u`, four hex digits, `'`;
4. `'\`, any one code point, `'`.

If none matches, the `'` is not a literal and scanning resumes at *j* + 1.

**3.5 Guillemet identifier (`«`).** The span runs to and including the next
`»` (U+00BB). If there is none, the `«` is not a literal and scanning resumes
at *j* + 1.

## 4. The code view

The *code view* *S* is *T* with every span made opaque. *S* has the same
length as *T* and the same newlines:

- in a comment span, every code point other than U+000A becomes U+0020;
- in a `string` or `char` span, every code point other than U+000A becomes
  `"` (U+0022);
- in a `guil` span, every code point strictly between the `«` and the `»`,
  other than U+000A, becomes U+0020.

The scanner reads *S* to find declarations and to cut headers. It reads *T*
for the signature text and for the comments.

A *word token* of *S* at an offset is the maximal run of word characters
starting there. "The word token `w` at offset *i*" means the run starting at
*i* is exactly `w`.

## 5. Lines, columns and command-start lines

**5.1 Column.** The *column* of a line is the number of whitespace code
points at its start in *T*, counted up to the first code point that is not
whitespace (a comment opener counts as not whitespace). A line whose first
code point lies inside a span that began on an earlier line has column 0.

**5.2 First token.** The *first token* of a line is found in *S*: skip
whitespace from the line start; what begins there is the first token, if
any. (Comments are blank in *S*, so a line that holds only a comment has no
first token.)

**5.3 Keyword lists.** These lists are closed.

*Modifiers*: `private`, `protected`, `public`, `noncomputable`, `unsafe`,
`partial`, `nonrec`, `meta`, `local`, `scoped`.

*Prefix words*: `open`, `set_option`, `variable`, `include`, `omit`,
`attribute`, `unseal`, `seal`, `universe`, `suppress_compilation`,
`unsuppress_compilation`, `count_heartbeats`, `#guard_msgs`.

*Command words*: the modifiers, the prefix words, and `theorem`, `lemma`,
`def`, `abbrev`, `instance`, `example`, `structure`, `class`, `inductive`,
`axiom`, `opaque`, `irreducible_def`, `alias`, `namespace`, `section`,
`end`, `export`, `mutual`, `deriving`, `import`, `module`, `macro`,
`macro_rules`, `syntax`, `notation`, `notation3`, `infix`, `infixl`,
`infixr`, `prefix`, `postfix`, `elab`, `elab_rules`, `declare_syntax_cat`,
`binder_predicate`, `unif_hint`, `initialize`, `builtin_initialize`,
`simproc`, `simproc_decl`, `dsimproc`, `dsimproc_decl`, `builtin_simproc`,
`builtin_dsimproc`, `register_option`, `register_builtin_option`,
`register_simp_attr`, `register_label_attr`, `register_hint`,
`register_linter_set`, `register_grind_attr`, `grind_pattern`, `run_cmd`,
`run_meta`, `run_elab`, `declare_config_elab`, `declare_command_config_elab`,
`declare_core_config_elab`, `add_decl_doc`, `recommended_spelling`,
`deprecated_module`, `deprecated_syntax`, `tactic_extension`, `library_note`,
`assert_not_exists`, `assert_not_imported`, `assert_exists`,
`initialize_simps_projections`, `proof_wanted`, `extend_docs`, `extend_doc`,
`mk_iff_of_inductive_prop`, `insert_to_additive_translation`,
`declare_aesop_rule_sets`, `add_aesop_rules`, `erase_aesop_rules`,
`lrat_proof`, `recall`, `whatsnew`.

A *head token* at an offset of *S* is `@[`, or `#` followed by an ASCII
letter and then word characters (a `#`-command such as `#check`, taken as
one token), or a word token.

**5.4 Command-start line.** A line *starts a command* when either

- the first code point after its leading whitespace in *T* opens a `doc` or
  `moddoc` comment span (a docstring or module doc), or
- its first token (5.2) is a head token that is `@[`, a `#`-command, a
  modifier or a command word.

The *first offset* of a command-start line is the offset of that comment
opener or of that first token.

## 6. Finding declarations: heads

A *head* is the part of a command before its keyword: attributes, modifiers
and one-line prefixes. Heads are parsed from *S*.

**6.1 Head parse.** Given an offset *i* (the first offset of a command-start
line) and a set of target keywords, repeat:

1. Skip whitespace (newlines included). If the text ends, there is no head.
   The first non-whitespace offset reached this way is the *head start*.
2. If `@[` begins here: skip to just after the `]` that balances the `[`,
   counting only `[` and `]` (in *S*, so brackets inside literals do not
   count); if none, there is no head. Continue at step 1.
3. Otherwise take the head token here; if there is none, there is no head.
   - If it is a target keyword: the head is found; the *keyword offset* is
     here.
   - If it is a modifier: continue at step 1 after it.
   - If it is a prefix word: find, on the same line and after it, the first
     word token `in` at bracket depth 0 (depth counts the brackets of 1.3
     from the prefix word on, never below 0); if there is none on this line,
     there is no head. Continue at step 1 after that `in`.
   - Anything else: there is no head.

**6.2 Scan.** Take the command-start lines in order. For each, run the head
parse from its first offset with targets `example` and `instance`. When a
head is found with its keyword on line *L*, record it and skip every
command-start line up to and including *L*. (A command-start line that lies
inside a head, such as an attribute line above the keyword, therefore never
starts a second declaration.)

Each recorded head is a candidate declaration. Its *column* is the column
(5.1) of the line holding the head start. Its *line*, the `line` of the
declaration, is the line holding the keyword.

**6.3 Anonymous instance.** An `example` is always anonymous. For an
`instance`, read *S* after the keyword: skip whitespace; if `(` follows and,
after optional whitespace, the word token `priority` begins, skip to just
after the `)` that balances that `(` (counting `(` and `)` only), or to the
end of the text when no `)` balances it, and skip whitespace again. The
instance is *anonymous* if the text has ended or the
code point now reached is `:` or an opening bracket `(`, `{`, `[` or `⦃`;
otherwise it is *named* and is not an anonymous declaration.

## 7. The end of the header

**7.1 Limit.** The *limit* of a declaration is the first offset (5.4) of the
first command-start line after the keyword's line whose column is less than
or equal to the declaration's column, or the end of the text when there is
none.

**7.2 Header end.** Read *S* from just after the keyword to the limit with a
bracket depth (starts at 0; an opening bracket adds one, a closing bracket
subtracts one but never below 0), a flag *typed* (false), a counter
*pending* (0) and a flag *bar* (false). Word tokens are read whole. At depth
0:

1. `:=`: if *typed* and *pending* > 0, subtract one from *pending*, clear
   *bar*, move past the `:=` and continue. Otherwise, if *typed*, the header
   ends here (*terminated*). If not *typed*, the header is *untyped*: it
   ends at the limit.
2. `:` not followed by `=`: set *typed*.
3. When *typed*, `|` that is the first non-whitespace code point of its line
   in *S* and is followed by whitespace or the end of the text: a
   match-alternative line; the header ends here (*terminated*). Any other
   `|` sets *bar* when *pending* > 0.
4. When *typed*, `↦` or `=>`: if *pending* > 0 and *bar* is set, subtract one
   from *pending* and clear *bar* (a pattern-matching `let` in the type has
   no `:=` of its own).
5. When *typed*, the word token `where`: the header ends here (*terminated*).
6. When *typed*, one of the word tokens `let`, `have`, `letI`, `haveI`,
   `let_fun`: add one to *pending*, clear *bar*.

If the limit is reached, the header ends at the limit and is not terminated.
The declaration is *typed* when the flag is set.

**7.3 Named declarations.** The same cut gives the optional `signature` of a
named declaration whose keyword is `theorem`, `lemma`, `def`, `abbrev`,
`instance`, `opaque` or `irreducible_def`: the head parse of 6.1 with that
keyword as target, then 7.1 and 7.2. A named declaration has a signature
only when the header is typed and terminated. An `axiom` therefore has none:
its header has no `:=`, `where` or alternative, so nothing terminates it and
it always runs to the limit. The same holds for an `opaque` without a value.
A `structure`, `class` or `inductive` has none either. `signature_at` takes
the seven keywords above, `axiom`, `example`, `structure`, `class` and
`inductive`, returns nothing where this section gives no signature, and
raises `ValueError` for any other word.

## 8. The display form (`signature`)

The *statement text* is *T* from the keyword offset to the header end
(exclusive). The `signature` is its *display form*, `normalize_statement`:

1. Lex the statement text (section 3; it starts in code, so its spans are
   those of *T* that lie in it).
2. Replace every comment span by one U+0020.
3. Outside `string`, `char` and `guil` spans, replace every maximal run of
   whitespace by one U+0020. The spans themselves are kept verbatim,
   whitespace and newlines included.
4. Remove whitespace at both ends.

The display form is idempotent. A checker verifies that a `signature` is in
display form by applying `normalize_statement` and comparing. Because the
placement of a comment relative to whitespace does not matter after step 3,
`a /- c -/ b`, `a/- c -/b` and `a b` all display as `a b`.

## 9. The hash form and the statement hash

`statement_sha256` is the SHA-256, as 64 lowercase hex digits, of the UTF-8
encoding of the *hash form* *H*(`signature`).

**9.1 Tokens.** Read the display form left to right, producing tokens. Each
token is *wordlike* or a *symbol*.

1. A `'` whose preceding code point is not a word character (or which is at
   offset 0) and which begins a char literal (3.4, shapes 1–4): the whole
   literal is one wordlike token.
2. An `r` that is not preceded by a word character and is followed by zero or
   more `#` and a `"`: the whole raw string literal (3.3) is one wordlike
   token.
3. A word character: the maximal run of word characters starting here,
   together with any `«…»` groups (a `«` with a later `»`) that touch the
   run, joined into one wordlike token. Precisely, a wordlike *word token* is
   a maximal sequence of pieces that are each a run of word characters or a
   `«…»` group, with no whitespace or other code point between pieces. (A
   `'` that is not a char literal is a word character and joins the run.)
4. A `"`: the whole string literal (3.3, plain or interpolated, determined
   by the code points before it as in 3.3) is one wordlike token.
5. `↦` (U+21A6): the symbol token `=>` (two code points, U+003D U+003E).
6. `λ` (U+03BB): the wordlike token `fun`.
7. Whitespace: no token. A comment (which the display form no longer
   contains): no token.
8. Any other code point: a symbol token holding that one code point.

At each position rules 1 and 2 are tried before rule 3. A piece sequence
(rule 3) ends where a char literal or a raw string begins: after a `«…»`
group, an `r"` or a `'` that opens a literal starts a new token. So
`«x»r"a"` is the two tokens `«x»` and `r"a"`, joined as `«x» r"a"`, and
`«x»'a'` is `«x»` and `'a'`.

Steps 5 and 6 are the whole alias table. It is closed: `→`/`->`, `∀`/`forall`
and every other pair of spellings are different tokens.

**9.2 Join.** *H* is the concatenation of the tokens, with one U+0020
inserted between two adjacent tokens exactly when both are wordlike. No
space ever touches a symbol token. Rule of thumb: a space only where removing
it would merge two names.

So `(x:T)`, `(x : T)` and `( x : T )` all give `(x:T)`; `fun x ↦ x` and
`λ x => x` give `fun x=>x`; `f .foo` gives `f .foo` and `f.foo` gives
`f.foo`; a line break or a comment between two tokens changes nothing.
`hash_form` accepts any text, treating comments as whitespace, so
`hash_form(text)` equals `hash_form(normalize_statement(text))` for text
whose literals are closed. (Step 4 of section 8 strips trailing whitespace
even when it lies inside an unterminated literal, while `hash_form` keeps the
literal verbatim. A `statement_sha256` is always taken from the display form,
so the two never disagree on an id.)

## 10. The id

An anonymous declaration's id is the keyword, `:`, and the first 12 hex
digits of `statement_sha256`: `example:<12 hex>` or `instance:<12 hex>`.
`vocab.HASH_ID_PATTERN` is the grammar; a checker MUST match ids against it
with full-match semantics (no trailing newline or other text).

## 11. Ordinals

The ordinal scope is the whole companion: every `.lean` file tracked by git
at `companion.commit` in the companion's repository. A producer MUST pass the
declarations of all of them to `assign_ids` at once; an id assigned from a
subset is wrong.

1. Order the anonymous declarations by repository-relative POSIX path,
   compared as sequences of UTF-16 code units, then by line.
2. A declaration with a declared id (section 12) takes it, takes no ordinal
   and shifts none.
3. Among the others, in that order, the first declaration whose id (section
   10) is `X` keeps `X`; the second takes `X~2`, the third `X~3`, and so on.
   The count is per id, so it is per keyword and per 12-hex prefix.

Ordinals are positional: adding or deleting a copy can move `~2` to another
declaration. The changelog rule of `docs/annotations.md` (`ordinal_assigned`)
is unchanged.

## 12. Declared ids

**12.1 The run of comments above.** Take the comment spans that end at or
before the head start, nearest first, and collect them into the *run* while
every condition holds; the first comment that breaks one ends the run and is
not part of it:

1. The text of *T* between the end of the comment and the head start (for the
   nearest one) or the start of the previously collected comment (for the
   others) is whitespace only. Blank lines are therefore allowed, and an
   attribute, modifier or `... in` prefix is not between them, because it
   belongs to the head.
2. The comment starts its own line: the text of *T* from the start of its
   line to the comment is whitespace only. A comment that follows code on a
   line is never directly above.
3. A `doc` comment is not the note body of a `library_note` or
   `#adaptation_note` command: find the last non-whitespace code point before
   the comment; if it is inside a comment span, this condition holds;
   otherwise, if the first token (5.2) of its line is `library_note` or
   `#adaptation_note`, the doc comment belongs to that command and the run
   ends.

Only these comments are read. A comment placed inside the head, after an
attribute or a prefix, is ignored: a tag comment MUST come before the whole
head.

**12.2 The body of a comment** is its text without the opener (`--` for a
line comment; `/--`, `/-!` or `/-`) and without the closing `-/` when
present, with whitespace removed from both ends.

**12.3 Candidates and rejections.** For each comment of the run, nearest
first:

1. If the body begins with `` `example: `` or `` `instance: `` it is
   *tag-like*. It is a *tag comment* when the body is exactly one backtick,
   one or more code points that are neither a backtick nor whitespace, and
   one backtick. A tag-like body that is not a tag comment is rejected with
   code `tag-not-alone`. The inner text of a tag comment MUST full-match
   `vocab.DECLARED_ID_PATTERN` (`<keyword>:<slug>`; a slug of 12 lowercase
   hex digits, with or without `~k`, is excluded by that grammar); otherwise
   it is rejected with `not-a-declared-id`. A matching inner text is a
   candidate. Any comment kind may be a tag comment, including a line comment
   ``-- `example:foo` `` and a docstring.
2. If the comment is a `doc` comment, take each of its lines (split at
   U+000A only), with whitespace removed from both ends. A line that begins
   with `formal-companion id:` yields the rest of the line with whitespace
   removed from both ends; that value MUST full-match
   `vocab.DECLARED_ID_PATTERN`, else it is rejected with `not-a-declared-id`.
   A matching value is a candidate. Zero or more whitespace code points MAY
   separate the colon from the id. A docstring that merely mentions an id
   elsewhere in a line declares nothing.

Then:

3. A candidate whose keyword (the part before `:`) is not the declaration's
   keyword is rejected with `wrong-keyword` and dropped.
4. If more than one distinct candidate remains, all are rejected with
   `conflicting-tags` and the declaration has no declared id.
5. Otherwise the remaining candidate, if any, is the declared id; its
   `id_source` is `declared`. The same candidate stated twice is one
   candidate.

An implementation MUST report the rejection codes of a declaration
(`rejected_tag` in the reference implementation: the codes in the order
found, each followed by a colon and free text; the free text is not
normative). A rejected tag never becomes an id; the declaration takes the
candidate that survives rules 3 to 5, or its statement-hash id when none
does.

`comment_tags` (informative, for producers that join on a legacy tag): every
tag-shaped opening `` `<keyword>:<slug>` `` at the start of a body in the
run, whether or not the comment declares anything.

## 13. Passages and numbered items

**13.1 `normalize_text`.** Apply Unicode NFKC; then replace every maximal
run of `White_Space` code points (1.4) by one U+0020; then remove
`White_Space` code points at both ends. Case is kept. NFKC comes first
because it maps U+00A0 and most of U+2000–U+200A to U+0020 and folds
ligatures and the micro sign, which differ between PDF text extractors.

**13.2 Passage with a quote**: `passage-` followed by the first 8 hex digits
of the SHA-256 of the UTF-8 encoding of `normalize_text(quote)`. The
normalised quote MUST NOT be empty.

**13.3 Passage without a quote**: `passage-p<printed page>-` followed by the
first 8 hex digits of the SHA-256 of the UTF-8 encoding of
`normalize_text(title)`. The printed page is a positive integer written in
decimal without leading zeros; the normalised title MUST NOT be empty.

**13.4 Numbered item**: `<slug>-<number>`, followed by `-<sub>` when the
item has a `sub`. The slug is the item's `kind` lower-cased (Unicode default
case mapping), with every maximal run of code points outside `a`–`z` and
`0`–`9` replaced by one `-` and any `-` at the ends removed. `number` and
`sub` are copied verbatim: a prime in `sub` (`b'`) stays. The slug and the
number MUST NOT be empty.

## 14. Known limits

The hash is syntactic. These edits change a statement-hash id and are not
formatting-only by this document's definition:

1. renaming a binder;
2. regrouping binders: `(a b : T)` and `(a : T) (b : T)` differ;
3. any change of notation outside the alias table of 9.1 (`→` for `->`,
   `Type*` for `Type _`, ...);
4. a change of context that is not in the header: `variable`, `open`,
   `namespace`, `set_option`, `universe`.

And these inputs are read in a way that may surprise:

5. Lean is whitespace-sensitive in a few places that the hash form is not:
   `a[i]` and `a [i]`, `(e).f` and `(e) .f` hash the same.
6. Whitespace between two symbol code points is dropped, so notations that
   differ only in how symbols are grouped hash the same (`a < |b|` and
   `a <| b |`, neither of which is likely to be a real statement).
7. A type continuation line that begins with `|` followed by whitespace is
   read as a match alternative and ends the header; `|x| ≤ 1` at the start
   of a line (no space after the bar) is not. So a `match ... with` or a
   `fun` inside the type whose alternatives start lines cuts the header at
   the first of them: `theorem t : f x = match x with` followed by a line
   `  | 0 => 1` gets a signature that ends in `with`.
8. A typed header with no `:=`, `where` or match-alternative line before
   the next command-start line runs to that line, and an untyped header
   hashes the whole command up to it; a command that is not in the lists of
   5.3 (a project's own command syntax) is not a boundary.
9. Interpolated strings are recognised by the `s!`, `m!`, `f!` prefixes
   only; a string that Lean interpolates by its syntax alone (`throwError
   "..."`) is lexed as a plain string, so a `"` inside one of its holes ends
   it early.
10. A string literal inside a header is kept verbatim: `"a  b"` and `"a b"`
    are different statements, as they are in Lean.
11. An alternative `| pat => rhs` on the header's own line is not a
    terminator (rule 3 of 7.2 needs the bar first on its line), so the
    header runs to the limit: a named declaration written that way has no
    signature, and an anonymous instance written that way hashes its
    alternatives.
12. Only the first command on a line is found. A second declaration on the
    same line (`example : True := trivial example : False := sorry`) is not
    scanned.

## 15. Test vectors

`conformance/ids/` holds JSON files; each file is an array of cases. A case
is one of:

- **scan** `{"name", "lean", "expected", "note"?}`: `lean` is a file text;
  `expected` lists every anonymous declaration the scanner finds, in order,
  as `{"line", "keyword", "signature", "hash_form", "statement_sha256",
  "id", "declared_id"?, "rejected_tag"?}`. `id` is the id `assign_ids` gives
  when this text is the companion's only file (so it carries the ordinal or
  the declared id); `declared_id` is present when one was declared;
  `rejected_tag` is the list of rejection codes (12.3), in order, when there
  were any.
- **multi-file scan** `{"name", "files": [{"path", "lean"}], "expected"}`:
  as above, over several files; each expected entry carries `"file"` as
  well, and the ordinals are assigned over all files (section 11).
- **hash form** `{"name", "signatures", "hash_form"}`: every signature in
  the list MUST have exactly this hash form (a group of formatting-only
  variants); or `{"name", "signatures", "distinct": true}`: the hash forms
  of the listed signatures MUST be pairwise different.
- **display form** `{"name", "text", "signature"}`:
  `normalize_statement(text)` MUST equal `signature`.
- **named signature** `{"name", "lean", "line", "keyword", "signature"?,
  "statement_sha256"?}`: `signature_at` MUST return these, or nothing when
  `signature` is absent.
- **passage** `{"name", "quote", "id"}` or `{"name", "printed_page",
  "title", "id"}`; with `"error": true` instead of `id` when the input MUST
  be refused.
- **item label** `{"name", "kind", "number", "sub"?, "id"}`.
- **normalize text** `{"name", "text", "normalized"}`.

The Lean text of every vector is synthetic.

## 16. Why the finer rules are as they are (Informative)

The rules above are normative. This section explains the choices a reader
is most likely to question; it adds no rule.

1. **Match-alternative line (7.2 step 3).** A simpler rule, "a line whose
   first non-whitespace character is `|`", would cut a real type
   continuation line such as `|x - y| ≤ ε` and truncate the header. The
   rule therefore also requires whitespace after the bar, which every match
   alternative has (`| 0 => ...`).
2. **`«…»` joins a word token (9.1 step 3).** If a `«…»` identifier were a
   token of its own, `f «a».b` and `f «a» .b` would hash the same, the very
   collision the dot rule avoids for plain names. So a `«…»` group is part
   of the word token it touches.
3. **Literals are verbatim in the display form (8, step 3).** Whitespace is
   collapsed outside literals only, so `"a  b"` and `"a b"` stay different
   statements, as they are in Lean. A comment is still one space, and
   comments and whitespace collapse together.
4. **Line endings (2, step 3).** CRLF is folded to LF before anything else,
   so converting a file's line endings changes no id even when a header
   holds a multi-line string literal.
5. **Pattern-matching `let` (7.2 steps 3 and 4).** A `let` in a type whose
   value is given by alternatives has no `:=`; the pending binder is released
   by the first `=>`/`↦` after a `|` at depth 0. `have h : |a| = 1 := ...`
   in a type still consumes its own `:=`, since no `=>` precedes it.
6. **No-terminator headers (7.2).** When no terminator precedes the next
   command-start line, the header ends at that line. An indentation rule
   (end before the next line indented no deeper than the keyword) is not
   used as a fallback: a continuation at column 0 never truncates, whatever
   follows.
7. **Named instance (6.3).** The instance is anonymous exactly when a binder
   opener or the type colon follows; anything else, including an
   antiquotation `$x` inside a syntax quotation, counts as a name, so text in
   quotations is not scanned as a declaration.
8. **Ordinal key (11).** Duplicates are counted per 12-hex id, not per full
   digest, so two statements whose digests share a prefix cannot produce one
   id twice.
9. **Rejection codes (12.3).** The codes `tag-not-alone`,
   `not-a-declared-id`, `wrong-keyword` and `conflicting-tags` make the
   report of a rejected tag language-neutral and testable.
10. **Prefix words and command words (5.3).** The prefix words are every
    real `... in` prefix of Lean and Mathlib. The command-word list is the
    union of Lean's and Mathlib's command keywords as of Lean 4.24; a
    docstring or module doc at the start of a line starts a command too.
11. **Comments inside a head (12.1).** A tag comment between an attribute
    and the keyword is not read; it is neither declared nor rejected. A tag
    belongs above the whole head.
12. **Interpolated strings (3.3).** Only the `s!`, `m!` and `f!` prefixes
    mark a string as interpolated; inside a hole, nested literals and
    comments are skipped, and the whole literal is one token.
