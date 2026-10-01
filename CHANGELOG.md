# Changelog

Releases of formal-companion-annotations. The package follows semantic
versioning tied to the format's version (`docs/annotations.md` section 7).
The format's own version is a document's `schema_version`; each profile has
its own version in `profiles`.

## 1.0.0rc3 (unreleased)

The repository now holds only the schema, the specification, the checker
and a few examples. Nothing in the format changed: the checker accepts and
refuses the same documents with the same codes and paths, and writes the
same canonical bytes.

- The schema's descriptions say what every field and value means; they
  replace the separate vocabulary document and the specification's field
  tables. The specification states only what the schema cannot.
- One schema file: the wheel ships `schema/` as the package's schema
  directory, with no second copy in `src/`.
- The Lean source scanner left `ids` (`scan_file`, `assign_ids`,
  `ordinal_ids`, `signature_at`, `AnonymousDecl`): finding declarations in
  Lean is a producer's work. `ids` keeps the format's id rules.
- The conformance suite, its Node job, the issue templates and the
  informative documents are removed; the tests are three files.

## 1.0.0rc2 (2026-10-01, tag only)

- **The schema's `$id`** is the raw URL of the schema file on this
  repository's default branch,
  `https://raw.githubusercontent.com/mathlib-initiative/formal-companion-annotations/main/schema/annotations-v1.0.schema.json`,
  in place of a `w3id.org` identifier. The format depends on no external
  registration; `docs/w3id/` is removed. `vocab.ANNOTATION_SCHEMA_ID_BASE`
  and `validate.schema_id()` follow. A document that carries `$schema` with
  the rc1 value gets warning `W-SCHEMA-ID`; nothing else changes.

## 1.0.0rc1 (2026-10-01, tag only)

The first release candidate of the format, `schema_version` `"1.0"`,
identifier `formal-companion/annotations`. It replaces the private `v1.0.0`
tag of 2026-09-28, which was cut before the format had a reader and is
withdrawn: do not use it. The tag was deleted from the repository on
2026-10-01. Nothing public consumed that tag,
and this release is not compatible with it: the identifier, the id rules,
the vocabulary and several fields changed.

### The format

- **Identifier.** The root `schema` is `"formal-companion/annotations"` and
  the docstring id line is `formal-companion id: <id>`. The schema's `$id`
  is `https://w3id.org/formal-companion/annotations/v1.0/schema.json`, one per
  format minor (`docs/w3id/` holds the redirect to register).
- **Core and profiles.** The core is the header plus `sources`, `items`,
  `declarations`, `links`, `provenance`, `locations` and `unattributed`.
  Four optional profiles, declared in the new root `profiles` object and
  versioned on their own, hold the rest: `graph` (`clusters`, `memberships`,
  `artifacts`, `companion.graph`, `item.clusters`, cluster-targeted links,
  `declaration.unlocated`), `site` (`destinations`, `snippets`), `audit`
  (`verdicts`) and `history` (`changelog`, `link.orphaned`,
  `declaration.replaced_by`). A profile's keys need the profile declared
  (invariant I14). A reader ignores profiles it does not implement.
  `source.role` stays in the core: a document with no verdicts can still say
  which source it audits or keeps as a reference.
- **Selectors.** Exactly five selector types: `FragmentSelector`,
  `TextQuoteSelector`, `CssSelector`, `PdfRegionSelector`, `SitePageSelector`.
  `TextPositionSelector`, `DataPositionSelector`, `XPathSelector`,
  `SvgSelector`, `RangeSelector` and `target.state` are left out of 1.0. A
  PDF fragment may not repeat a parameter.
- **Sources.** New optional `identifiers` (`doi`, `isbn`, `arxiv`). A `pdf`
  source may be pinned by `identifiers` alone when the producer knows the
  edition but does not hold the bytes (an `other` source too); `page=`
  fragments, `pages` and the page fields apply to it, a `PdfRegionSelector`
  does not (I7: geometry needs the bytes). A site source's `sha256` is
  defined over the pages listed in `page_hashes`, which a hashed site source
  must carry; each entry names a file in the site-path grammar.
- **Items.** `coverage` is `formalized`, `partial_only`, `support_only`,
  `example_only`, `private_only`, `not_formalized` or `out_of_scope`
  (`partial` renamed, `private_only` new). `example_only` is for an item
  whose only formalisations are anonymous examples linked with role
  `example`; an anonymous example may be a `key` link's target, and the
  item is then `formalized`. New optional `coverage_note` and
  `xrefs` (`{database, tag}`, core databases `stacks`, `kerodon`,
  `wikidata`, `lmfdb`). `cluster_fallback` is removed (derivable). `sub`
  (on items, links and verdicts) admits primes, `b'` or `f''`, which the
  label id carries verbatim (`exercise-1.4-b'`).
- **Declarations.** New kinds `constructor`, `recursor`, `alias`,
  `irreducible_def`. An `example` is always anonymous.
- **Links.** `confidence` is removed. `part` joins the core relation tokens.
  Invariant I5 is rewritten. An `attributed` link needs a `key` link unless
  the item's coverage is `partial_only`, and each coverage class says which
  link roles it allows.
- **Companion.** New optional `toolchain` and `packages` (`{name, rev}`).
- **Verdicts.** The four fields that carried one audit tool's own verdict,
  finding kind, finding ids and pinned commit are removed; a producer keeps
  such data under `x_` keys. The vocabulary is the format's own.
- **Ids.** The statement hash now hashes a token-normalised form of the
  header, so formatting-only edits (line breaks, comments, `(x:T)` vs
  `(x : T)`, `=>` vs `↦`, `λ` vs `fun`) keep the id; the display `signature`
  keeps the readable form. Whitespace and identifier characters are defined
  explicitly. The rules are stated as an algorithm, with test vectors.
  Ordinals (`~k`) are counted over every `.lean` file tracked at
  `companion.commit`.
- **Scanner fixes.** `public` and `meta` modifiers; a named instance whose
  name is on a later line; typed headers continued at column 0; a trailing
  comment on the previous line no longer declares an id; same-line
  docstrings; match alternatives at any indentation; `«…»` identifiers; a
  leading BOM; nested brackets in attributes; `attribute [...] in` and
  `unseal ... in` prefixes.
- **Validity.** Documents are I-JSON: finite numbers, integers within
  ±(2^53 - 1), no lone surrogates, nesting at most 64 deep. Every date and
  timestamp in the document is checked (I9), leap seconds accepted. Physical
  pages are at least 1 (I6). I4 applies to passages only: a numbered item is
  located by its number and may have no location, quote or pages. The URL
  rule (former I10) is no longer part of validity. It is the opt-in lint `external-urls` (`L1`), which now scans
  keys and every scheme and exempts fields by path.
- **Compatibility.** One schema file per format minor
  (`schema/annotations-v1.0.schema.json`); the checker validates against the
  minor a document declares, and warns rather than fails on unknown keys of a
  newer minor. Reader and producer conformance rules are in the
  specification.

### The checker and the package

- Problems and warnings carry stable codes (`SCHEMA`, `IJSON`, `I1` to
  `I14` with `I10` retired, `L1`, `W-...`); `validate.check` returns
  `Problem(code, path, message)` records. New flags `--format json` and
  `--lint NAME`.
- Fixed: `--canonical` accepted CRLF files. Schema and checker regexes
  matched a trailing newline and non-ASCII digits; every pattern is now
  dialect-neutral and `schemacheck` refuses the others. Float pages, huge
  numbers, lone surrogates and deep nesting raised tracebacks; they now exit
  2 with a message, never a traceback, never "invalid". `page=999&page=7`
  hid a page. Negative physical pages passed. `--print-canonical` wrote in
  the locale's encoding and never validated first; it now sorts the
  document, validates the result and writes UTF-8. `at` values outside the
  changelog were not checked. A field's full name was unchecked without
  `name`. Two passes were quadratic. Uppercase `md5=` hex was refused. The
  CLI stopped at the first unreadable file. Both known issues of the
  withdrawn tag (`1e400`, `--print-canonical` on malformed input) are gone.
- Also fixed before the candidate: `--print-canonical`
  wrote problem lines to standard output; the canonical writer raised on a
  value outside I-JSON; a comment above a `library_note` hid the note; 333
  nested interpolation holes overflowed the scanner; a lone surrogate in Lean
  text raised an encoding error; the scan was quadratic in a file's lines;
  `ids.signature_at` accepted any word as a keyword (it raises `ValueError`).
  The checker now refuses what the specification already forbade: a
  `private_only` key link to a cluster (I5), a `restated` entry at the same
  instant as the retirement (I9), a member whose own name holds a dot (I8),
  and a quad whose corners all lie on one line (I7).
- The public API is defined by this repository alone. Scanner internals left
  `ids.__all__`; `ids.signature_at` and `ids.hash_form` joined it.
- Docs: the specification was rewritten (RFC 2119 keywords, a glossary, a
  data-model overview, conformance and pairing sections); the README leads
  with a complete minimal document.
- Infrastructure: a language-neutral conformance suite, a Node `ajv` job
  and a JavaScript reference implementation of the canonical form in CI, a
  `release` workflow publishing to PyPI through trusted publishing (a
  release candidate as a pre-release), issue templates.

### Where it comes from

The format was first written inside another repository of the same
organisation and extracted into this one with its history preserved.
