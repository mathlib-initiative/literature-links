# The formal-companion annotation format, version 1.0

**Status.** Release candidate of format version 1.0. This document is
normative. The JSON Schema, `schema/annotations-v1.0.schema.json`, is
normative too: it states every field, its type and, in its descriptions,
what each field and value means. This document states only what the schema
cannot. The reference checker is `src/formal_companion_annotations/`.

**Conventions.** The key words MUST, MUST NOT, SHOULD, SHOULD NOT and MAY are
to be read as in RFC 2119. A code span names a literal key or value. "The
checker" means any conforming checker (section 8).

## 1. Purpose

A companion is a Lean repository that formalises a written source, item by
item. This format records, in one JSON document per companion, which
declarations state which items of which pinned sources, and where each item
sits in its source. A PDF overlay, a rendered site, an audit and a diff of
two companions can then read and write the same file.

## 2. The document

A document is one JSON object. Its header is `schema` (always
`"formal-companion/annotations"`), `schema_version`, the optional
`profiles` and `$schema`, and `companion` (the repository and the commit
described). The rest are arrays of records: `sources` (pinned editions),
`items` (numbered items and unnumbered passages), `declarations`, `links`
(an item attributed to a declaration), `provenance`, `locations` (W3C Web
Annotation targets), `unattributed`, and the arrays of the four profiles
(section 3). Every record has a string `id`. Every object is closed. The
schema gives every field. A record, `companion` and the root also take
extension keys matching `^x_[a-z0-9_]+$`, with any value. They are a
producer's own data. The checker MUST NOT read them, except under the
`external-urls` lint (4.10). No other object takes extension keys. A
required array MAY be empty. An absent optional array means "this document
does not say".

## 3. Core and profiles

The **core** is the header and the arrays `sources`, `items`,
`declarations`, `links`, `provenance`, `locations` and `unattributed`.
Everything else belongs to one of four **profiles**. A document declares
each profile it uses in the root `profiles` object, with that profile's own
`"<major>.<minor>"`:

```json
{"audit": "1.0", "graph": "1.0", "history": "1.0", "site": "1.0"}
```

This table is the complete list of what a profile owns.

| profile | root arrays | fields on other records |
|---|---|---|
| `graph` | `clusters`, `memberships`, `artifacts` | `companion.graph`, `items[].clusters`, `links[].cluster`, `declarations[].unlocated`, `destinations[].artifact` |
| `site` | `destinations`, `snippets` | none |
| `audit` | `verdicts` | none |
| `history` | `changelog` | `links[].orphaned`, `declarations[].replaced_by` |

A source's `role` is core: a document with no verdicts MAY still say which
source it audits.

**I14 (profile gating).** A root array or field that a profile owns MUST
NOT appear unless the document declares that profile. So a destination
with an `artifact` target needs both `site` and `graph`, and a `~k` id
needs `history` (5.4). A declared profile with none of its keys is valid,
and `profiles` MAY be empty.

A reader that does not implement a profile MUST ignore that profile's
arrays and fields, and MUST NOT fail because of them.

## 4. Validity

A document is **valid** when it is I-JSON (4.1), the schema of its
declared minor accepts it (4.2) and every invariant holds (4.3 to 4.8).
Warnings (4.9) and lints (4.10) do not affect validity. Every problem and
warning has a stable code.

### 4.1 I-JSON

A document MUST be I-JSON (RFC 7493) within these limits:

- UTF-8, no byte-order mark, no duplicate key, no `NaN` or `Infinity`;
- every number finite, every integer-valued number within
  [-(2^53 - 1), 2^53 - 1], every numeric literal at most 400 characters;
- no lone surrogate in a string or a key;
- nesting at most 64 levels deep.

The checker MUST refuse anything else. A file that breaks a limit is
unreadable. On a value already in memory, each breach is a problem with
code `IJSON`, and nothing else is checked. An integer-valued number is an
integer whatever its spelling: `6.0` and `1e3` are `6` and `1000`.

### 4.2 Schema

The checker MUST validate the document against the schema of the minor it
declares (section 7). A schema failure has code `SCHEMA`. Every `pattern`
in the schema means the same under ECMA-262 (with the `u` flag) and Python
`re`. Patterns use explicit classes and no `\d`, `\w`, `\s`, `\b`, `.`
outside a class, named groups or inline flags. A trailing `$` is the end of
the string, never "before a final newline". Beyond shapes, the schema
states what a `form`, `kind`, `id_source`, `scope`, `resolution`, `state`
or `event` requires or excludes, how each kind of source is pinned, one
target per link, membership and destination, and full commit ids
everywhere except `resolution.commits`.

### 4.3 Invariants

The checker MUST check these after the schema accepts the document. I10 is
retired and its number is not reused.

| code | invariant |
|---|---|
| I1 | Ids MUST be unique within each array. |
| I2 | Every root array MUST be sorted by `id`. Every list of ids or strings that the schema marks unique (`items`, `anchors`, `clusters`, `relations.*`, `related_to`, `legacy_ids`, `agents`, `signals`, `locations`, `alternate_urls`, `identifiers.isbn`, `resolution.commits`, `resolution.replaced_by`) MUST be sorted. Each keyed list MUST be sorted by its key with one entry per key: a verdict's `declarations` by `declaration`, `provenance.inputs` by `path` and then by `source` (file entries first), `page_hashes` by `path`, `page_sizes` by `first`, `xrefs` by `(database, tag)`, `companion.packages` by `name`. The order is section 6's. |
| I3 | Every reference MUST resolve, an input's `source` included. A link MUST name a live declaration, or be `orphaned` and name a declaration id that a `retired` changelog entry names; only a link to a declaration MAY be orphaned, and an orphaned link MUST NOT name a live id. A verdict's `locations` MUST each show its item. A verdict with `status: fixed` MUST have a `fixed` resolution; a verdict without `resolution` is open. A declaration MUST have at most one snippet. `(item, target, role, sub)` MUST be unique among links, and `(cluster, target, role)` among memberships. A `field` or `projection` MUST have a `structure` or `class` parent; a `constructor` or `recursor` an `inductive`, `structure` or `class` parent. An item MUST NOT relate to itself. |
| I4 | Every passage MUST have a location, a `quote` or `pages`. A numbered item is located by its number and MAY have none. |
| I5 | The coverage rules of 4.4 MUST hold. |
| I6 | The page and source rules of 4.5 MUST hold. `(source, kind, number, sub)` MUST be unique among numbered items. |
| I7 | The selector and location rules of 4.6 MUST hold. |
| I8 | The declaration rules of 4.7 MUST hold. |
| I9 | Every date and timestamp in the document MUST be a real calendar date or UTC instant, and the changelog rules of 4.8 MUST hold. |
| I11 | When the canonical form is required (`--canonical`), the file's bytes MUST be the canonical form (section 6). |
| I12 | Item ids MUST follow 5.5 for their `id_source`. The quote or title a mechanical id hashes MUST NOT be only whitespace. A `declared` item id MUST NOT take a mechanical passage shape. |
| I13 | An unattributed declaration MUST have no non-orphaned link. |
| I14 | Profile gating (section 3) MUST hold. |

### 4.4 Coverage (I5)

An item's `coverage` and its non-orphaned links MUST agree:

1. A `key` link says that its target states the whole item, whatever the
   target's kind. An anonymous `example` MAY be a key link's target; the
   item is then `formalized`, or carries no `coverage`.
2. An item with links and no `key` link MUST carry `coverage`.
3. An item with an `attributed` link MUST have a `key` link, unless its
   `coverage` is `partial_only`. Then the attributed links are the partial
   statements, and their `relation` SHOULD be `special_case` or `part`.
4. A `formalized` item MUST have a `key` link. A `partial_only`,
   `support_only`, `example_only`, `not_formalized` or `out_of_scope` item
   MUST NOT have one. A `private_only` item MUST have at least one link,
   and each of its `key` links MUST name a declaration with
   `private: true`.
5. A `not_formalized` or `out_of_scope` item MUST NOT have a `key` or
   `attributed` link.
6. `coverage_note` MUST NOT appear without `coverage`.

### 4.5 Sources and pages (I6)

A source is a **PDF** when its `kind` is `pdf`, or `other` with
`media_type` `application/pdf`. Its physical page is its printed page plus
`printed_page_offset`.

- `physical_page_count`, `printed_page_offset`, `page_size` and
  `page_sizes` MUST appear only on a PDF. `page_sizes` ranges MUST have
  `first <= last`, MUST NOT overlap, and MUST lie within
  `physical_page_count` when it is given. A page's size is its
  `page_sizes` range when one lists it, else `page_size`.
- `pages` MUST be about a PDF: an item's source, a link's item's source,
  or a location's source. `last` MUST NOT be before `first`. Every physical page it names MUST be at least 1 and, when the
  source gives `physical_page_count`, at most that.
- A **site** source (`scope: site`) is one `web` source for a whole
  rendered site. Its `sha256` is the sha256 of the UTF-8 manifest with one
  line `"<sha256 of the page's bytes>  <path>\n"` per `page_hashes` entry
  (two spaces, as `sha256sum` writes), the lines in section 6's order of
  `path`. The checker MUST recompute it. A `page_hashes` path names a file:
  it MUST NOT end in `/`. `page_hashes` MUST list every page that a
  `SitePageSelector` on the source names; a path ending in `/` names its
  `index.html`.

### 4.6 Selectors and locations (I7)

A location's `target.selector` is a list of **alternatives** in preference
order: each selects the same span, and a reader uses the first it
understands. It is never a union. `refinedBy` narrows its parent.

**Families.** Each source follows the rules of one family. `pdf` is a PDF
(4.5). `html` is kind `web`, or `other` with `text/html` or
`application/xhtml+xml`. `text` is kind `tex` or `lean`, or `other` with
any other `text/*` type. `generic` is any other medium. A selector's type
MUST be one its source's family allows:

| family | selector types |
|---|---|
| `pdf` | `FragmentSelector`, `TextQuoteSelector`, `PdfRegionSelector` |
| `html` | `FragmentSelector`, `TextQuoteSelector`, `CssSelector`, `SitePageSelector` |
| `text` | `FragmentSelector`, `TextQuoteSelector` |
| `generic` | `FragmentSelector`, `TextQuoteSelector`, `CssSelector` |

**Fragments.** A `FragmentSelector.value` MUST NOT start with `#`.
`conformsTo` is an open IRI. These IRIs have a grammar, and the value MUST
follow it; a known IRI on a source of another family MUST be refused. In
every grammar a number is ASCII digits, and an integer has at most 9
digits.

- `http://tools.ietf.org/rfc/rfc8118`, and its synonym
  `http://tools.ietf.org/rfc/rfc3778` (pdf): `&`- or `#`-separated
  `name=value` parameters, `name` among `page`, `nameddest`, `structelem`,
  `comment`, `ef`, `zoom`, `view`, `viewrect`, `highlight`, `search`,
  `fdf`. A parameter MUST NOT repeat. `zoom` takes 1 or 3 numbers,
  `viewrect` 4, and `highlight` 4 (left, right, top, bottom) with
  left <= right and top <= bottom. `page` is a positive integer within
  `physical_page_count`. A refined PDF fragment MUST name its `page`.
- `http://tools.ietf.org/rfc/rfc5147` (text): `char=` or `line=`, then a
  position or a range `a,b`, `a,` or `,b`, then any number of
  `;length=N[,charset]` or `;md5=<32 hex>`. In a range, `a < b`. Positions
  are zero-based points between units, so editor lines 42 to 47 are
  `line=41,47`. `char=` counts Unicode code points.
- `http://tools.ietf.org/rfc/rfc3236` (html): an element id: no
  whitespace, no `#`.
- `http://www.w3.org/TR/media-frags/` (html, generic): `&`-joined
  dimensions. `xywh=[pixel:|percent:]x,y,w,h` with `w` and `h` positive and
  a `percent:` region within 100. `t=[npt:][start][,end]` with at least one
  end, times `sec[.f]`, `mm:ss[.f]` or `h:mm:ss[.f]` (minutes and seconds
  below 60) and start before end. `track=` and `id=` take a name without
  whitespace.

**Placement.** A `PdfRegionSelector` MUST be a top-level alternative or the
direct refinement of a PDF `page=` fragment, and then its `page` MUST be
that page. A `page=` fragment inside another MUST name the same page. A
`SitePageSelector` MUST be a top-level alternative, and only on a site
source. On a site source every top-level alternative MUST be a
`SitePageSelector`. A `refinedBy` chain MUST be at most 8 selectors deep.

**Regions.** A `PdfRegionSelector` MUST be on a source that names its bytes
(`sha256` or `git_blob`); a source pinned by `identifiers` alone has pages
but no geometry. Its `page` MUST be within `physical_page_count` when that
is given. `top_left` goes with `y_axis` `down` and `bottom_left` with `up`.
A rect MUST have `x0 < x1` and `y0 < y1`. A quad MUST have at least three
distinct corners, not all on one line. Coordinates MUST be finite;
`normalized` ones MUST lie in [0, 1]; `pt` ones MUST be at least 0 and,
when the page's size is known, within it.

**Locations.** Every item a location shows MUST be on its source. A
location with no items MUST be named by a declaration's `anchors` or a
link's `locations`. When a location has `pages`, every page its selectors
name MUST lie within them. A link's `locations` MUST be on its item's
source. A declaration's anchor shows the declaration's own text: it MUST
be on a `lean` or `web` source, or an `other` source whose family is
`html` or `text`.

### 4.7 Declarations (I8)

- The id MUST follow 5.1 for its `id_source`, and the flags MUST agree: a
  `name` declaration is neither `private` nor `anonymous`, a `private` one
  is `private` and not `anonymous`, and a `statement_hash` or `declared`
  one is `anonymous`. A `name` declaration's `name`, when present, MUST
  equal its id. An anonymous declaration MUST NOT carry `name`. An
  `example` MUST be anonymous.
- A `signature` MUST be in display form (5.2), and when `statement_sha256`
  is present, it MUST be the statement hash of the signature (5.3). This
  holds for named declarations too.
- A hash id's keyword MUST equal `kind`, and its 12 hex digits MUST be the
  first 12 of `statement_sha256` when that is given.
- A `~k` id MUST meet the ordinal rule of 5.4.
- A declaration MUST NOT be its own parent. A member's `namespace`, when
  given, MUST be its parent's full name. A member's full name MUST be that
  namespace (or else its parent's full name), a dot, and one more name
  component. A full name is `name`, else a `name` declaration's id, else the
  name part of a `private` id.

### 4.8 Dates and the changelog (I9)

A date is the start of its day, UTC. Instants compare with their full
fractional precision. A leap second is accepted only at `23:59:60`.

- A `retired` or `renamed` id MUST NOT be live.
- A `successor` or `possible_successor` MUST be live in the subject's array
  and MUST differ from the subject.
- `restated` MUST name a declaration id that is declared, named or
  private, never a statement-hash id: a new statement is a new hash id,
  recorded as `retired` and a new id. The id MUST be live, or retired or
  renamed by a strictly later entry.
- `ordinal_assigned` MUST name a declaration's `~k` statement-hash id. The
  id MUST be live, or retired or renamed by an entry no earlier.

### 4.9 Warnings

A warning never makes a document invalid. The checker MUST report these:

| code | when |
|---|---|
| `W-CONFORMS` | a `FragmentSelector` has no `conformsTo`, or one the checker does not know; its value is not checked |
| `W-MEDIA` | a Media Fragments name that is no dimension, or a repeated dimension (the last one wins) |
| `W-RELATION` | a link `relation` outside the core: `exact`, `generalization`, `special_case`, `part`, `invocation`, `related` |
| `W-XREF` | an xref `database` outside the core: `stacks`, `kerodon`, `wikidata`, `lmfdb` |
| `W-NEWER` | the document declares a core or profile minor newer than the checker knows, or carries a key that only such a minor defines (section 7) |
| `W-SCHEMA-ID` | the root `$schema` is not the `$id` of the declared minor's schema |

### 4.10 The external-urls lint

A lint is opt-in and not part of validity. The checker MUST run it only
when asked. Version 1.0 has one, `external-urls`, with code `L1`. It fails
on every string value and object key, anywhere in the document and at any
depth of an `x_` value, that holds a URL-like reference: `<scheme>://` for
any RFC 3986 scheme anywhere in the string, or a protocol-relative `//`, a
`javascript:`, `data:`, `mailto:` or `file:` at its start. Exactly these
paths are exempt: `sources[*].url`, `sources[*].alternate_urls[*]`,
`destinations[*].href`, the root `$schema`, a selector's `conformsTo`, the
`exact`, `prefix` and `suffix` of a `TextQuoteSelector` in a location's
`target.selector` tree, and `items[*].quote.*`. Exemptions are by path,
never by key name alone.

## 5. Ids

Every id is a string of 1 to 256 characters without whitespace, unique in
its array (I1), and never reused once retired (I9). Ids of locations and
links are free. Ids of declarations and items follow the rules below, as
the record's `id_source` says. The rules are frozen with the format:
changing one re-keys documents.

### 5.1 Declaration ids

| `id_source` | id |
|---|---|
| `name` | the fully qualified Lean name; it MUST NOT start with `private:`, `example:`, `instance:` or `:` |
| `private` | `private:<module>:<name>`, from the declaration's `module` and `name` |
| `statement_hash` | `<keyword>:<12 hex>` or `<keyword>:<12 hex>~<k>` |
| `declared` | `<keyword>:<slug>` |

The keyword is `example` or `instance`: these are the anonymous
declarations. The 12 hex digits are the first 12 lowercase hex digits of
the statement hash (5.3). `k` is a decimal integer of at least 2, without
leading zeros. A slug starts with an ASCII letter or digit, continues with
ASCII letters, digits, `.`, `_` and `-`, and is never 12 lowercase hex
digits, with or without `~k`. Ids are matched whole, never as a prefix. A
producer records a declared id however it chooses; a common way is a
comment next to the declaration in the Lean source.

The **statement text** of a declaration is its header: from its keyword to
the `:=`, top-level `where` or match alternative that ends a typed header.
An untyped header's statement text is the whole command. `signature` is
the display form of the statement text, and `statement_sha256` the
statement hash. A `statement_sha256` is required on an anonymous
declaration unless it is `unlocated`.

### 5.2 The display form

Whitespace here is exactly U+0009, U+000A, U+000D and U+0020.

**Lexing.** The display form needs the comments and literals of the text.
Scan from the start. At each step find the next `/-`, `--`, `"`, `'` or `«`.

- `/-` opens a block comment: `/--` a doc comment, `/-!` a module doc.
  Nested `/-` and `-/` count; the comment ends after the `-/` that closes
  the first, or at the end of the text.
- `--` opens a line comment, which runs to the next U+000A, exclusive.
- `"` opens a string. It is **raw** when `r` and zero or more `#` stand
  before it, with no word character before the `r`. A raw string ends
  after the first `"` followed by as many `#`, and has no escapes.
  Otherwise `\` escapes the next code point and the next `"` ends the
  string. A string is **interpolated** when `s!`, `m!` or `f!` stands
  before its `"`, with no word character before that. In an interpolated
  string a `{` opens a hole that runs to its balancing `}`. Comments and
  literals inside a hole are skipped whole, and only the braces outside
  them count.
- `'` opens a char literal unless a word character stands before it (then
  it is a prime). The literal is `'x'` (x neither `\` nor `'`), `'\xHH'`,
  `'\uHHHH'` or `'\` any code point `'`. If none of these matches, the `'`
  is no literal.
- `«` opens a guillemet identifier, which runs to the next `»`. If there is
  none, the `«` is no literal.

A literal or comment that the text ends inside runs to the end.

**The display form** (`ids.normalize_statement`):

1. Replace every comment by one U+0020.
2. Outside string, char and guillemet literals, replace every run of
   whitespace by one U+0020. Literals are kept verbatim, whitespace and
   newlines included.
3. Remove whitespace from both ends.

The display form is idempotent. So `a /- c -/ b`, `a/- c -/b` and `a b` all
display as `a b`.

### 5.3 The hash form and the statement hash

A **word character** is an ASCII letter or digit, `_`, `'`, `!`, `?` or
`.`; Greek and Coptic U+0370 to U+03FF except λ U+03BB, Π U+03A0 and Σ
U+03A3; Greek Extended U+1F00 to U+1FFE; Letterlike Symbols U+2100 to
U+214F; Mathematical Alphanumeric Symbols U+1D49C to U+1D59F; and the
subscripts U+2080 to U+2089, U+2090 to U+209C, U+1D62 to U+1D6A and U+2C7C.

**Tokens.** Read the text left to right. Each token is **wordlike** or a
**symbol**. At each position, in this order:

1. a char literal (5.2), when no word character stands before the `'`, is
   one wordlike token;
2. a raw string (5.2), when no word character stands before the `r`, is one
   wordlike token;
3. a maximal run of word characters and `«…»` groups (a `«` with a later
   `»`), with nothing between them, is one wordlike token; a char literal
   or a raw string that starts after a `«…»` group starts a new token;
4. a string (plain or interpolated) is one wordlike token;
5. `↦` U+21A6 is the symbol token `=>`;
6. `λ` U+03BB is the wordlike token `fun`;
7. whitespace and comments give no token;
8. any other code point is a symbol token on its own.

Rules 5 and 6 are the whole alias table. `→` and `->`, `∀` and `forall`,
and every other pair of spellings stay different.

**Join.** The **hash form** (`ids.hash_form`) is the tokens concatenated,
with one U+0020 between two adjacent tokens exactly when both are wordlike.
No space ever touches a symbol token.

The **statement hash** is the sha256, as 64 lowercase hex digits, of the
UTF-8 bytes of the hash form of the display form. So `(x:T)`, `(x : T)`
and `( x : T )` agree, `fun x ↦ x` and `λ x => x` give `fun x=>x`, `f .foo`
and `f.foo` differ, and a line break or a comment between two tokens
changes nothing. A binder rename, a regrouping of binders, notation outside
the alias table and a change of context all change the hash.

### 5.4 Ordinals

When two anonymous declarations of one companion would get the same hash
id, the later ones take `~2`, `~3` and so on. They are counted over every
`.lean` file tracked by git at `companion.commit`, ordered by
repository-relative path (compared by UTF-16 code units) and then by line.
A declaration with a declared id takes no ordinal and shifts none.

An ordinal is positional, so a document records it. A live `~k` id MUST
have `ordinal_assigned` changelog entries (the `history` profile). The
latest of them, by `at`, MUST name the declaration's `file`. When several
latest entries name different files, the id MUST be refused. A move that
keeps every recorded id in its recorded file is invisible to one document:
for a statement that has, or may get, a textual twin, declare an id.

### 5.5 Item ids

| `id_source` | id |
|---|---|
| `label` (numbered) | `<slug>-<number>`, then `-<sub>` when `sub` is present and not empty |
| `quote_hash` (passage) | `passage-<first 8 hex of the sha256 of the normalised quote>` |
| `page_title_hash` (passage) | `passage-p<printed page>-<first 8 hex of the sha256 of the normalised title>` |
| `declared` | any id but the two `passage-` shapes above |

The **slug** is the `kind` lower-cased, every run of code points outside
`a-z` and `0-9` replaced by one `-`, and `-` removed from both ends. It
MUST NOT be empty; otherwise declare the id. `number` and `sub` are copied
verbatim, a prime included: `exercise-1.4-b'`.

The **normaliser** (`ids.normalize_text`) is Unicode NFKC, then every run of
`White_Space` code points replaced by one U+0020, then `White_Space`
removed from both ends. Case is kept. `White_Space` is exactly U+0009 to
U+000D, U+0020, U+0085, U+00A0, U+1680, U+2000 to U+200A, U+2028, U+2029,
U+202F, U+205F and U+3000. The hash is the sha256 of the UTF-8 bytes of
the normalised text.

The **quote** is `item.quote.exact` when the item has one. Otherwise it is
the `exact` of the first `TextQuoteSelector` of the item's first location
(locations in id order, alternatives in order, each followed by its
`refinedBy` chain). A passage with a quote MUST take the `quote_hash` id
or a declared one. The **printed page** is `pages.first` on the printed
basis, or the physical page less `printed_page_offset`; it MUST be at
least 1, and is written in decimal.

The same normalised quote on the same source is the same passage. Two
different passages with the same mechanical id are a duplicate id (I1):
declare one of them.

## 6. Canonical form

The canonical text follows RFC 8785 (JCS) for everything that decides
bytes, with a fixed layout.

- **Order.** Strings compare by their UTF-16 code units, the order RFC 8785
  gives object keys and JavaScript's default `Array.prototype.sort` gives
  strings. It differs from code point order only for a character above
  U+FFFF against one in U+E000 to U+FFFF. Numbers compare by value.
- **Numbers.** ECMAScript `Number::toString` of the IEEE double: the
  shortest digits that round-trip, no `.0` on an integer, plain notation
  for 1e-6 <= |x| < 1e21 and exponent notation (`1e+21`, `1e-7`) outside
  it, `-0` written `0`.
- **Strings.** Escaped as `JSON.stringify` does: `\"`, `\\`, `\b`, `\f`,
  `\n`, `\r`, `\t`, other control characters as `\u00xx` in lower-case
  hex, everything else as UTF-8.
- **Layout.** Object keys in the order above, a two-space indent, one
  member or element per line, `": "` after a key, `{}` and `[]` when
  empty, LF line ends, a final newline, no byte-order mark.
- **Arrays.** Record arrays sorted by `id`, and the unique lists and keyed
  lists of I2 sorted as I2 says. Selector lists keep their order, which is
  a preference, and so does `evidence`.

A producer in a language whose JSON writer reorders keys (JavaScript's
`JSON.stringify` puts integer-like keys first) MUST order keys itself.

## 7. Versions and compatibility

`schema_version` is `"<major>.<minor>"`, and so is each profile's version
in `profiles`. A minor only adds optional keys or enum values: a document
valid under X.Y is valid under X.(Y+1). A major changes something a reader
of the previous major cannot ignore: a key removed or made required, a
value removed or given another meaning, a rule tightened, the canonical
form or an id rule changed. A release MAY raise a profile's minor without
changing `schema_version`.

There is one schema file per core minor,
`schema/annotations-v<major>.<minor>.schema.json`. Its `$id` is the raw URL
of that file on the repository's default branch,
`https://raw.githubusercontent.com/mathlib-initiative/formal-companion-annotations/main/schema/annotations-v<major>.<minor>.schema.json`.
A released schema file never changes, so the URL always serves the bytes
the `$id` names. The `$id` is an identifier and MUST NOT be fetched. A
document need not carry `$schema`.

The checker MUST validate a document against the schema of the minor it
**declares**, so a document that says `"1.0"` and uses a key of 1.1 fails.
For a core or profile minor newer than it knows, the checker MUST use the
newest schema it has for that major in **forward mode**. An unknown key of
a closed object and an unknown profile name are then `W-NEWER` warnings,
not problems, and the invariants run on the keys it knows. An unknown enum
value still fails. An unknown major, core or profile, is a `SCHEMA`
problem.

The package `formal-companion-annotations` follows semantic versioning. Its
MAJOR is the core major: package X reads documents of core major X. A new
core minor, a new profile version, a new lint or a new public Python name
is a MINOR release. A fix that changes no rule is a PATCH; a fix to a
checker that wrongly accepted a forbidden document is a patch, and the
changelog says so. Problem and warning codes, exit statuses, the shapes of
the output lines and each module's `__all__` are under semantic versioning.
The wording of a message is not.

## 8. Conformance

**A conforming document** MUST be valid and SHOULD be in canonical form.

**A conforming writer** MUST write only valid documents and SHOULD write
them in canonical form. It MUST declare the lowest core minor, and the
lowest minor of each profile, whose schema admits the document, and MUST
NOT write a key outside those schemas except an extension key. It MUST pin
every source and declare every profile whose keys it uses.

**A conforming reader** MUST accept any document of a core major it
implements. It MUST ignore keys it does not know in a document that
declares a newer minor, extension keys it does not understand, and the
arrays and fields of a profile it does not implement. It MUST treat
`target.selector` as alternatives. It MUST NOT fetch `$schema`, a schema
`$id` or a `conformsTo` IRI.

**A conforming checker** MUST apply section 4 and report every problem
and warning with its code, MUST run a lint only when asked, MUST apply
section 7's choice of schema and forward mode, and MUST make no network
request.

**The reference checker** is the command
`formal-companion-annotations-validate`. It prints
`<file>: <path>: <message> [<code>]` for each problem,
`<file>: warning: <path>: <message> [<code>]` for each warning,
`<file>: ok (<counts>)` for a valid document, and
`<file>: cannot read: <message>` on standard error for an unreadable file.
It exits 0 when every document is valid, 1 when one is invalid, and 2
when one is unreadable, on a usage error, a broken install or an internal
error; 2 wins over 1. It checks every document it is given and never
shows a traceback. `--canonical` compares the file's exact bytes with the
canonical form (I11). `--print-canonical` sorts one document, validates
the sorted document, and only then writes its canonical form to standard
output as UTF-8; its problems and warnings go to standard error.
