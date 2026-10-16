# Literature Links specification

An annotation records a correspondence between two documents, or parts of
them, such as a passage of a book and a Lean declaration. Its `subject` and
`object` each list the ends on one side, and its `relation` may say how the
sides relate. The [JSON Schema](../schema/companion.schema.json) gives its
structure, and [validation](#validation) adds two checks. The format has no
version field; it carries the version of the release. Records valid under 2.x
stay valid in later 2.x; a breaking change bumps the major version. This page
defines the format; [tools.md](tools.md) documents the checker, its Python API,
the command line and how files are found and read.

```json
{
  "subject": [ { "type": "html", "uri": "notes/groups.html", "location": { "fragment": "lagrange" } } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d",
                "location": { "declaration": "Subgroup.card_subgroup_dvd_card" } } ]
}
```

Without a `relation`, a record claims only that its sides correspond, not
equivalence, proof or review. No record claims that its ends exist.

## Terms

An *annotation*, or record, is one JSON object in this format, and an
*annotation file* is a JSON or JSONL document that carries annotations
([Discovery](#discovery)). An *end* is a document, or a part of one: an object
with a `type`, a `uri` and optionally a `location`. A *side* is the list of
ends in `subject` or in `object`. A *companion* is the set of annotations about
one informal source, such as a book, article or wiki, with any files they keep
beside them, such as a copy of the source. A *producer* writes annotations, a
*reader* turns annotation files into records and applies
[folder defaults](#folder-defaults), a *consumer*, such as a viewer, uses the
records, and a *validator* checks them.

Here "must", "must not", "should" and "may" state requirements, in the sense of
RFC 2119, though they are not capitalized. An annotation is invalid exactly
when it breaks a rule in [Validation](#validation): the JSON rules, the JSON
Schema or one of the two checks. The other requirements bind producers, readers
and consumers, and no validator can check them. Every field is its producer's
claim: validation checks its form, never its truth. Where this page recommends
values for a field, any other nonempty string is valid too, and applications
agree on its meaning among themselves.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `subject` | Yes | A list of one or more ends: by convention the side being annotated, which is the informal side when there is one |
| `object` | Yes | A list of ends, possibly [empty](#unlinked-passages-and-checked-absences): the other side |
| `relation` | No | How the subject [relates](#relation) to the object |
| `junk` | No | A list of one or more of the object's [junk values](#relation) |
| `status` | No | How far the subject is [formalized](#status-kind-id-and-note) |
| `kind` | No | What the subject is, such as `theorem` |
| `id` | No | A name for the subject, shared by the records about it |
| `note` | No | Free text |
| `extensions` | No | An object of [application data](#extensions) |
| `$schema` | No | A [reference](#references) used as a tooling hint |

Each end is an object:

| Field | Required | Meaning |
|---|---|---|
| `type` | Yes | `pdf`, `latex`, `html`, `lean` or `generic` |
| `uri` | Yes | A [reference](#references) to the document, usually the companion's copy; for `lean`, the project |
| `location` | No | An object selecting part of the document ([Location](#location)) |
| `version` | No | Which [revision](#ends) of the document, such as a Git commit |
| `sha256` | No | The SHA-256 of the bytes at `uri` |
| `citation` | No | A CSL-JSON item describing the work |
| `identifiers` | No | Identifiers in other registries, by name |
| `title` | No | A readable name for the part, such as "Theorem 1.4 (Lagrange)" |
| `role` | No | How the end takes part in the record |
| `extensions` | No | An object of application data |

Every string field in these tables is nonempty. Other fields are invalid in a
record, in an end and in a built-in location.

The ends on one side are taken jointly. A theorem that runs over a page break
is one subject with two PDF ends, and a statement split over two declarations
is one object with two Lean ends. The record relates the two sides as wholes,
and the order of the ends carries no meaning. Independent links stay separate
records: a passage that two declarations each state is two records. No field is
inherited from another record, only from [folder defaults](#folder-defaults).
An array is not an annotation.

## Relation

`relation` is a nonempty string, read "subject *relation* object". These values
are recommended:

| `relation` | Reading |
|---|---|
| `exactMatch` | The sides state the same definition or claim, up to notation and junk values |
| `closeMatch` | The sides state nearly the same thing, with differences a reader should know, such as whether 0 is a natural number, whether an interval is closed, or a normalization constant |
| `broadMatch` | The object is more general: for a definition, a larger class; for a theorem, the object states the claim with no stronger hypotheses and no weaker conclusion |
| `narrowMatch` | The subject is more general, in the same sense |
| `relatedMatch` | The sides are related in another way, such as a lemma the proof uses |
| `hasPart` | The object states one part of the subject, such as one of several claims of a theorem or one clause of a definition |
| `noMatch` | A checked absence: the object, typically a whole project at a `version`, was searched and holds nothing that matches the subject |

The first five are the
[SKOS mapping relations](https://www.w3.org/TR/skos-reference/#mapping), which
Wikidata's [P4390](https://www.wikidata.org/wiki/Property:P4390) also uses, read
in the same direction: in SKOS too, `broadMatch` says that the object is the
broader side. For example, Mathlib's `isCyclic_subgroup_units` says that a
finite subgroup of the units of an integral domain is cyclic. A record whose
subject says this of the multiplicative group of a field, and whose object is
that declaration, is a `broadMatch`: every field is an integral domain.

`hasPart`, like `noMatch`, is not a SKOS value. It has the direction of Dublin
Core's [`hasPart`](https://www.dublincore.org/specifications/dublin-core/dcmi-terms/terms/hasPart/)
and Wikidata's [has part(s)](https://www.wikidata.org/wiki/Property:P527).

The relation holds between the sides as wholes. Exporting a record pairwise,
one statement for each pair of a subject end and an object end, as SKOS, SSSOM
and Wikidata expect, is faithful only when each side has one end.

Mathlib often makes a function total by giving it a fixed value where the
informal notion is undefined, such as `x / 0 = 0`, `Real.log 0 = 0`, or 0 as
the `Nat.card` of an infinite type. These are *junk values*. An object that
agrees with the subject wherever the subject is defined, and differs only
through junk values, is an `exactMatch`. Cases that the object reaches only
through junk values never make it broader: `broadMatch` needs real generality
within the subject's meaning, such as weaker hypotheses or a larger class.

The optional `junk` field lists the junk values that the object assigns where
the subject is undefined or says nothing. Each item is a nonempty string, in
plain words or Lean notation. Like `relation`, it describes the correspondence,
so with several object ends it covers the side as a whole. It never changes the
relation, and an absent `junk` claims nothing: it does not say there are none.
Mathlib's `Subgroup.card_subgroup_dvd_card` states Lagrange's theorem with
`Nat.card`, so an infinite group satisfies it only through a junk value. A
record that links it to the theorem for finite groups is an `exactMatch` with
`"junk": ["Nat.card of an infinite type is 0"]`.

### Unlinked passages and checked absences

A record with `"object": []` records its subject, a passage that nobody has
linked yet. Its empty object claims nothing about whether a counterpart exists.
A *checked absence* claims more: the producer extracted the statement, searched
a formal library at a version, and found no counterpart. It is a `noMatch`
record whose object is the library at that version, usually a `lean` end with
no location:

```json
{ "subject": [ { "type": "pdf", "uri": "notes.pdf", "location": { "page": 8 }, "title": "Remark 1.5" } ],
  "object": [] }
```

```json
{ "subject": [ { "type": "pdf", "uri": "notes.pdf", "location": { "page": 8 }, "title": "Remark 1.5" } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d" } ],
  "relation": "noMatch" }
```

The first says the remark is not linked. The second says that Mathlib at that
commit was searched and holds nothing that matches it. With an empty object, a
record has nothing to relate, so it should have no `relation`.

A `noMatch` object end should have a `version`. A producer that does not know
the version it searched writes `"object": []` with `"status": "not_formalized"`
instead.

## Status, kind, id and note

`status`, `kind`, `id` and `note` are optional nonempty strings. `status` says
how far the producer judges the subject to be formalized, in the formal library
the producer has in mind. `formalized`, `partial` and `not_formalized` are the
recommended values. It describes the subject, not the link, so records about
one subject should agree, and a folder of records can set it in
[folder defaults](#folder-defaults). Even `formalized` next to an object is a
judgment, not a checked equivalence, and `not_formalized` does not say where
anyone looked; a [checked absence](#unlinked-passages-and-checked-absences)
does. `kind` names what the subject is; `definition`, `theorem`, `lemma`,
`proposition`, `example`, `remark`, `exercise`, `proof` and `proof_step` are
recommended. `id` names the subject. Records about one subject should share it,
so a consumer can group them; it need not be unique across subjects. `note` is
free text.

## Ends

`uri` says where a copy of the document is, and that copy may be local.
`version` says which revision it is: a Git commit, a Wikipedia `oldid` or an
arXiv version. So an end can open the companion's own copy and still name the
revision, and a Wikipedia article keeps its readable URL with the `oldid`
beside it:

```json
{ "type": "html", "uri": "https://en.wikipedia.org/wiki/C*-algebra", "version": "1374776629",
  "location": { "fragment": "Abstract_characterization" }, "identifiers": { "wikidata": "Q263809" } }
```

For a `lean` end, `version` should be the full commit: a Git object ID of 40
lowercase hex digits, or 64 in a SHA-256 repository, not a branch or a tag.
`sha256` is 64 lowercase hex digits: the SHA-256 of the bytes that `uri` points
at. Whether the local copy matches `sha256`, and whether the revision still
exists, is for tools to check.

`citation` describes the work as a
[CSL-JSON](https://github.com/citation-style-language/schema) item, the
bibliography format that Zotero, Pandoc and citeproc read. Its `id` and `type`
are required nonempty strings. Its other keys are CSL's, and validation does
not check them. A work's DOI goes in `citation`, as CSL's `DOI`. `identifiers`
maps the names of registries that CSL has no field for, such as `wikidata`,
`arxiv` or `zbmath`, to nonempty strings, and its keys follow the rule for
[extension](#extensions) keys. An identifier may name the work, such as an
arXiv ID, or what the end selects, such as the Wikidata item of a theorem.

```json
{ "type": "pdf", "uri": "notes.pdf",
  "sha256": "6c6a04b64488546e49f0ebb4c6310bb091487b5861b5b525985faec6e80c2e7f",
  "citation": { "id": "notes", "type": "book", "title": "Lecture Notes on Groups",
                "author": [ { "family": "Author", "given": "A." } ], "issued": { "date-parts": [ [2026] ] } } }
```

`title` is a readable name for the part that the end selects;
`citation.title` names the work. `role` says how the end takes part in the
record, such as `states`, `defines`, `uses` or `supports`. Applications define
its values.

## Location

Without `location`, an end is the whole document. A `null` location is
invalid. Under `generic` any object is valid, including `{}`. Under the other
types `location` must take one of the forms below, so `{}` is invalid. An empty
generic location is not the same as an absent one.

A location with a `profile` key is application-defined under every type.
`profile` is a [reference](#references) that names the convention, and the
convention gives the other keys their meaning. Only `profile` is checked. Use
it when no built-in form fits, rather than declaring the document `generic`.

```json
"location": { "profile": "https://example.org/profiles/section-snippet/v1",
              "section": "Subgroups", "snippet": "the index of a subgroup" }
```

A consumer must not treat an unresolved, ambiguous or unsupported location as
the whole document. A location whose `profile` it does not know is
unsupported. The consumer keeps the location and reports why it is unresolved.
It reports missing or ambiguous matches, such as duplicate labels or IDs, and
never picks the first one.

### PDF

`{ "page": 3, "rect": [0.1, 0.2, 0.6, 0.15] }` or
`{ "page": 3, "quote": { "exact": "a finite group", "prefix": "Let G be " } }`

`page` counts physical pages from 1, ignoring page labels. A PDF location may
carry `rect` or `quote` beside `page`, not both; with neither it selects the
whole page.

`rect` is `[x, y, width, height]` as fractions of the displayed page box after
the page's rotation. As in ISO 32000, that box is the CropBox clipped to the
MediaBox, or the MediaBox when there is no CropBox, and a page inherits either
box and its `Rotate` entry from the page tree when it does not set them. The
origin is the top-left corner and y grows down. The values are in [0, 1], width
and height are positive, and x + width and y + height are at most 1. The sums
are taken in IEEE 754 double arithmetic, so a width computed as 1 − x always
fits.

`quote` is the quote object of [HTML](#html), with the same rules for `exact`,
`prefix` and `suffix`. It matches the text of that one physical page, `prefix`
and `suffix` included, so it never crosses a page break. That text is what a
PDF text extractor reads from the page, in reading order, with each run of
`White_Space`, as defined under [HTML](#html), replaced by one space and both
ends trimmed. Do not change case or normalize Unicode. Hyphenation, ligatures
and differences between extractors are the application's concern. A quote that
matches nowhere on the page is missing, and one that matches at more than one
position, overlapping or not, is ambiguous: as in [Location](#location), a
consumer reports it and never picks the first match.

### LaTeX

Use exactly one of `{ "label": "thm:lagrange" }` or `{ "lines": [12, 18] }`.

`label` is the literal argument of a `\label` command. It is looked up in the
document rooted at the end's `uri` and in the files it reads with `\input` and
`\include`, at any depth; other inclusion commands, macro expansion and
generated labels are the application's concern. `lines` selects
[lines](#lines) of the file at `uri`.

### HTML

Use exactly one of these:

- `fragment` is the decoded value of an element's `id` attribute. It does not
  start with `#` and contains no `White_Space` or control character; use `css`
  for an ID that does. `name` attributes do not count. It is not
  percent-decoded again, so `"a%20b"` is a literal ID.
- `css` is a nonempty CSS selector. Validation does not parse it. A selector
  that matches more than one element is an ambiguous match.
- `quote` is `{ "exact": "...", "prefix": "...", "suffix": "..." }`. `exact` is
  nonempty. The optional `prefix` and `suffix` are the text just before and
  after the match. When given, a match must be immediately preceded and
  followed by them; they narrow the match and are not part of the selection.
  Consumers keep all three as written and compare them as written with the
  text layer below, so write them with single spaces and no other
  `White_Space`. Each matching position counts, overlapping or not: an `exact`
  of `aa` matches the text `aaa` at two positions, which is ambiguous.

A quote matches this text layer. Parse the resource with the HTML parsing
algorithm, scripting disabled, and run no scripts: the layer never depends on
what a script would add or change, and `noscript` content is ordinary text.
Take the `textContent` of the body, or of the document element if there is no
body, without `script`, `style` and `template` elements in any namespace, SVG
and MathML included. Replace each run of `White_Space` with one space and trim
both ends. Do not change case, normalize Unicode or add spaces between
elements, so `<b>natural</b><i>number</i>` gives `naturalnumber`. Hidden text
counts, including MathML `annotation` and `annotation-xml` content such as the
TeX copy some sites keep beside each formula; for a passage that runs through
formulas, `css` or `fragment` is often the more robust choice. Shadow DOM and
iframes do not count. `White_Space` means U+0009–000D, U+0020, U+0085,
U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F and U+3000. Other text
conventions need a `profile`.

### Lean

`{ "declaration": "Subgroup.card_subgroup_dvd_card" }`, optionally with
`module` and `lines`, or `{ "module": "Mathlib.GroupTheory.Coset.Card" }`,
optionally with `lines`.

A `lean` end's `uri` is the project: a repository URL, which is recommended, or
a path to a checkout, such as `..` when the annotations live in a folder of the
project. Its `version` is the commit. Without a location, the end is the whole
project.

`declaration` is the fully qualified name of a declaration, as Lean prints it.
Validation does not parse it. A name is unique within a project at a commit,
and it survives the file moves that make paths and line numbers stale.

`module` is a dotted module name, such as `Mathlib.GroupTheory.Coset.Card`, and
selects that module's source file in the project. Beside a declaration it is a
hint for finding the source or the documentation page. If the declaration is
not in that module, the declaration wins.

`lines` requires `module` and selects [lines](#lines) of the module's file.
With a module alone, `lines` is how an end selects an item with no name. This
end selects the `example` that starts on line 12 of a module in the project
that holds the annotations:

```json
{ "type": "lean", "uri": "..", "version": "<40 hex digits>",
  "location": { "module": "Notes.Groups", "lines": [12] } }
```

Beside a declaration, `lines` narrows it to the part on those lines, such as a
proof step. A record that means the whole declaration leaves `lines` out. Lines
outside the declaration, or in a module that does not hold it, are unresolved.
Line numbers mean something only at the end's `version`.

At the commit below, `Subgroup.card_dvd_of_injective` proves its claim with a
`calc` block of two steps. The first starts on line 82 and counts the group as
the range of `f`; the second starts on line 83 and applies Lagrange's theorem.
This record links the first step of a proof in the notes to the first `calc`
step:

```json
{
  "subject": [ { "type": "pdf", "uri": "notes.pdf", "location": { "page": 9, "rect": [0.12, 0.4, 0.76, 0.06] },
                 "title": "Proof of Corollary 1.7, first step" } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d",
                "location": { "declaration": "Subgroup.card_dvd_of_injective",
                              "module": "Mathlib.GroupTheory.Coset.Card", "lines": [82] } } ],
  "relation": "exactMatch",
  "kind": "proof_step"
}
```

### Lines

`lines` in a LaTeX or Lean location is `[start, end]` or `[n]`, positive
integers with end at least start. `[start, end]` selects those lines,
inclusive; a producer that knows a single line writes `[n, n]`. `[n]` selects
the outermost item that starts on line n, and the consumer finds where it ends:
in LaTeX, an environment whose `\begin` is there; in Lean, a declaration,
`example`, `have`, `calc` step or tactic block. Lines count from 1, and the
bytes CRLF, CR and LF each end a line, so the count is the same whether the file
is UTF-8, Latin-1 or another ASCII-compatible encoding.

### Generic

A generic location is any JSON object, such as `{ "table": "results", "row": "42" }`.
Its producer and consumer define it. A `profile` key names the convention, as in
every type. A kind of document with no type of its own, such as Markdown, is
`generic`. Text offsets need a unit defined by the application.

## Extensions

`extensions`, on the record and on each end, maps nonempty keys to any JSON
values. A key contains none of the characters that a [reference](#references)
excludes. Namespaced keys such as `org.example.tool` are recommended. The
record's extensions and each end's never merge with each other. Consumers keep
unknown values unchanged and never fetch or run them. An extension is not a
trusted claim.

## References

`$schema`, each end's `uri` and a location's `profile` are nonempty URI or IRI
references. They contain no `White_Space`, no C0 or C1 control (U+0000–001F,
U+007F–009F), no bidirectional formatting or zero-width character
(U+200B–200F, U+202A–202E, U+2066–2069, U+FEFF) and neither U+FFFE nor U+FFFF,
so a link cannot display as another; and each `%` starts a percent-encoding
such as `%20`. Relative and absolute references are allowed, including names
such as `urn:isbn:9780000000000`. The check is lexical: it does not parse the
reference, so `http://[x` passes.

A relative reference resolves against the URI of the document that carries
the annotation: the file, or the retrieval URI of the response that delivered
the record, as in [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986#section-5).
This holds inside [JSONL](#discovery) files too. It never resolves against
another end, the `id`, the repository or the working directory. Code that holds
an annotation in memory must keep that base. Moving an annotation means keeping
the base or rewriting the references.

No other string is a reference, including `version`, a Lean name and the
strings in `citation`, `identifiers` and `extensions`. To link a Lean
declaration, use a `lean` end and name the declaration in its location; a bare
name in `uri` is read as a relative reference. Percent-encode `%`, spaces, `#`
and `?` in file names. A fragment in an end's `uri` is kept as part of the
reference but selects nothing; under every type but `generic`, `location` is
the selection.

A valid annotation grants no permission to open or run anything. `$schema` never
changes which schema applies. The schema's `$id` and a location's `profile` are
names, not downloads.

## Folder defaults

A file named `_defaults.json` holds one JSON object: members shared by every
[annotation file](#discovery) in its folder and in the folders below it. It is
not an annotation. Each record read from those files is the defaults merged
with the record as written:

- A member the record leaves out is inherited.
- Where both hold an object, the two merge member by member, at any depth.
- Otherwise the record's value wins. Arrays are replaced, not merged, except
  for the ends below.
- A `null` removes the inherited member. Where nothing is inherited, the
  record's value is kept as written.

This is [JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396) with the
record as the patch, except that a `null` with nothing to remove is kept, so a
record read without defaults is read exactly as written.

One more rule covers ends. In a defaults file, `subject` or `object` may be an
object, an *end template*: the members that the ends on that side share. Where
the inherited side is a template and the side written over it, in a record or
in another defaults file, is a list:

- Each end that has no `uri` member merges over the template by the rules
  above: its own members win, and a `null` removes a template member.
- An end that has its own `uri` names its own document. It is complete as
  written and takes nothing from the template.
- An item that is not an object is kept as written.

A `location` is never merged: one written over a template's, in an end or in
another template, replaces it whole. A record that leaves a side out gets a
list holding the template alone, and `"object": []` stays empty. A record that
writes a side as an object merges with the template member by member, and the
result is invalid, since a side is a list. The rule applies only to `subject`
and `object` at the top level; `citation`, `extensions` and every other member
merge as above.

With this file as `chapter-1/_defaults.json`:

```json
{ "subject": { "type": "pdf", "uri": "../notes.pdf",
               "sha256": "6c6a04b64488546e49f0ebb4c6310bb091487b5861b5b525985faec6e80c2e7f" },
  "object": { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
              "version": "db584cd6d46c92f209a44c0f1c829460d327499d" } }
```

this record in `chapter-1/`, whose statement on page 7 is corrected by an
errata sheet:

```json
{ "subject": [ { "location": { "page": 7 }, "title": "Theorem 1.4 (Lagrange)" },
               { "type": "pdf", "uri": "../errata.pdf", "location": { "page": 1 } } ],
  "object": [ { "location": { "declaration": "Subgroup.card_subgroup_dvd_card" } } ],
  "relation": "exactMatch", "junk": [ "Nat.card of an infinite type is 0" ] }
```

reads as:

```json
{ "subject": [ { "type": "pdf", "uri": "../notes.pdf",
                 "sha256": "6c6a04b64488546e49f0ebb4c6310bb091487b5861b5b525985faec6e80c2e7f",
                 "location": { "page": 7 }, "title": "Theorem 1.4 (Lagrange)" },
               { "type": "pdf", "uri": "../errata.pdf", "location": { "page": 1 } } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d",
                "location": { "declaration": "Subgroup.card_subgroup_dvd_card" } } ],
  "relation": "exactMatch", "junk": [ "Nat.card of an infinite type is 0" ] }
```

The errata end names its own file, so it does not take the hash of
`notes.pdf`. A record in the same folder that writes
`{ "subject": [ { "location": { "page": 9 } } ], "relation": "noMatch" }`
leaves `object` out, so its object is the template alone: a checked absence in
Mathlib at that commit. One that writes `"object": []` instead is merely
unlinked. Below a template that selects a declaration or gives a `role`, a
checked absence writes its object end in full: `type`, `uri` and `version`.

Defaults files nest. A reader applies the `_defaults.json` in the annotation
file's folder and in each folder above it, outermost first, so the nearest one
wins. Each defaults file merges over the ones above it by the rules above. Two
templates merge member by member, so an outer template may leave a member such
as `uri` for an inner one to give. A list in a defaults file is completed from
the template above it, as a record's is, and then replaces that template for
every record below. A record there that writes its own list gets nothing from
either, so keep the side a template if records below write ends without a
`uri`. A `null` in a defaults file removes an outer default; one with nothing
above it to remove is kept and reaches every record below. For local files that
goes up to the root of the file system. A reader that fetches annotations over
the web is given a base URL, the root of the companion, and never looks above
it; given none, it applies no defaults. A [JSONL](#discovery) file takes
defaults like any annotation file, one record at a time.

A relative reference in a defaults file resolves against the defaults file.
A reader that merges records rewrites the inherited references in
[References](#references), in templates and in lists of ends alike, so that
they resolve the same way from the annotation's file; strings in `citation`
and `extensions` are copied unchanged.

Validation applies to the merged record, so a record may leave out `subject` or
`object` when a defaults file supplies it. A defaults file that is not a JSON
object, or that a reader cannot read, is a problem, and the records below it
are not read.

## Validation

Validation checks the JSON rules below, the JSON Schema, and two things the
schema cannot express, in each end: a PDF `rect` has positive size and fits the
page, and `lines` end no earlier than they start. Neither of the two applies to
a location with a `profile`. Validation never resolves locations, fetches
resources or judges mathematics. Where the schema asks for an integer, a JSON
number with no fractional part counts, so `2.0` is a valid `page`, as in JSON
Schema.

JSON input must have unique keys, finite numbers and no unpaired surrogates,
even inside opaque data. An implementation may reject very large or deeply
nested input, a number outside the IEEE 754 double range, or a nonzero number
that rounds to zero. Consumers that use doubles keep integers exact only up to
2⁵³ − 1, so use strings for exact decimals and large identifiers.

[The checker](tools.md#python-api) implements these rules.

## Discovery

An annotation file is a JSON or JSONL document, whether a file or a web
response. A JSON document carries one annotation, an object; an array is not
one. A JSONL document carries one annotation object on each nonblank line, and
is how one document carries several. A document is JSONL when its file name or
URL path ends in `.jsonl` or `.ndjson`, ignoring case, or when a web response
declares the media type `application/jsonl` or `application/x-ndjson`;
otherwise it is JSON. Annotation files are UTF-8, and a reader may reject a
byte order mark, as [RFC 8259](https://www.rfc-editor.org/rfc/rfc8259#section-8.1)
allows. How the tools find and read files is in [tools.md](tools.md#discovery).
