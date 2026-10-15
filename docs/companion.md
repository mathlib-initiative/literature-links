# Literature Links specification

An annotation links one informal source, or a location in it, to one formal
destination. The [JSON Schema](../schema/companion.schema.json) gives its
structure, and [validation](#validation) adds two checks. The format has no
version field; it carries the version of the release. Records valid under 1.x
stay valid in later 1.x; a breaking change bumps the major version. This page
defines the format; [tools.md](tools.md) documents the checker, its Python API,
the command line and how files are found and read.

```json
{
  "source": { "type": "html", "uri": "informal.html" },
  "location": { "fragment": "reflexivity" },
  "target": "formal.html#reflexivity"
}
```

A link does not claim equivalence, proof or review, or that the target exists.
The format is inspired by the
[W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) but is
not a serialization of it. Here `target` is the formal side; in the W3C model
the target is the thing being annotated.

## Terms

An *annotation*, or record, is one JSON object in this format, and an
*annotation file* is a JSON or JSONL document that carries annotations
([Discovery](#discovery)). A *companion* is the set of annotations about one
informal source, such as a book, article or wiki, with any files they keep
beside them, such as a copy of the source. A *producer* writes annotations, a
*reader* turns annotation files into records and applies
[folder defaults](#folder-defaults), a *consumer*, such as a viewer, uses the
records, and a *validator* checks them.

Here "must", "must not", "should" and "may" state requirements, in the sense of
RFC 2119, though they are not capitalized. An annotation is invalid exactly
when it breaks a rule in [Validation](#validation): the JSON rules, the JSON
Schema or one of the two checks. The other requirements bind producers, readers
and consumers, and no validator can check them.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `source.type` | Yes | `pdf`, `latex`, `html` or `generic` |
| `source.uri` | Yes | A [reference](#references) to the informal resource, usually the companion's copy |
| `source.pin` | No | A [pin](#pins) citing the informal resource outside the companion |
| `target` | No | A reference to the formal destination, or an object with `uri`, `pin` and `extensions` |
| `target.uri` | Yes, when `target` is an object | A [reference](#references) to the formal destination |
| `location` | No | An object selecting part of the source |
| `status` | No | How far the passage is [formalized](#status-kind-label-and-note): a nonempty string, or an object with `value`, `pin` and `extensions` |
| `kind`, `label`, `note` | No | Nonempty strings that [describe](#status-kind-label-and-note) the link |
| `id` | No | A nonempty string label, not necessarily unique |
| `extensions`, `source.extensions`, `target.extensions`, `status.extensions` | No | Objects of [application data](#extensions) |
| `$schema` | No | A reference used as a tooling hint |

Only `source` is required. Without `target`, the annotation records the
informal passage alone. A string `target` says the same as an object with that
`uri`: `"x"` and `{ "uri": "x" }` are one link. Other fields are invalid at the
top level, in `source`, in `target` and `status` objects, in built-in pins and
in built-in locations. Two targets or two passages need two annotations. No
field is inherited from another record, only from
[folder defaults](#folder-defaults). An array is not an annotation.

## Location

Without `location`, the annotation links the whole source. A `null` location is
invalid. In `generic` mode any object is valid, including `{}`. In the other
modes `location` must take one of the forms below, so `{}` is invalid. An empty
generic location is not the same as an absent one.

A location with a `profile` key is application-defined in every mode. `profile`
is a [reference](#references) that names the convention, and the convention
gives the other keys their meaning. Only `profile` is checked. Use it when no
built-in form fits, rather than declaring the source `generic`.

```json
"location": { "profile": "https://example.org/profiles/section-snippet/v1",
              "section": "Subgroups", "snippet": "the index of a subgroup" }
```

A consumer must not treat an unresolved, ambiguous or unsupported location as
the whole source. A location whose `profile` it does not know is unsupported.
The consumer keeps the location and reports why it is unresolved. It reports
missing or ambiguous matches, such as duplicate labels or IDs, and never picks
the first one.

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
document rooted at `source.uri` and in the files it reads with `\input` and
`\include`, at any depth; other inclusion commands, macro expansion and
generated labels are the application's concern. `lines` is an inclusive range
of positive integers, with end at least start, in the file at `source.uri`.
Lines count from 1, and the bytes CRLF, CR and LF each end a line, so the count
is the same whether the file is UTF-8, Latin-1 or another ASCII-compatible
encoding.

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

### Generic

A generic location is any JSON object, such as `{ "table": "results", "row": "42" }`.
Its producer and consumer define it. A `profile` key names the convention, as in
every mode.
Text offsets need a unit defined by the application.

## Pins

`uri` is the local pin: the reference a consumer opens, usually a relative
path to the companion's own copy of the resource, though any reference is
valid. A `pin` is the global pin: a citation that identifies the resource
outside the companion, the way a bibliography entry does. A pin has a `type`,
which chooses its keys. Every other key is optional, and a pin with only a
`type` is valid.

| `type` | Keys |
|---|---|
| `website` | `title`, `owner`, `url`, `revision`, `date`, `retrieved`, `sha256`, `identifiers` |
| `book` | `title`, `author`, `publisher`, `edition`, `date`, `isbn`, `url`, `retrieved`, `sha256`, `identifiers` |
| `paper` | `title`, `author`, `venue`, `volume`, `number`, `pages`, `date`, `doi`, `arxiv`, `url`, `retrieved`, `sha256`, `identifiers` |
| `repository` | `url`, `commit`, `path`, `line`, `module`, `declaration`, `sha256`, `identifiers` |
| `generic` | Any keys the application defines; a `url` is still a reference |

Other keys are invalid in the built-in types; put them in `identifiers` or use
`generic`. In the built-in types, values are nonempty strings, except that
`author` is a string or a nonempty array of strings, `line` is a positive
integer, `identifiers` maps names such as `wikidata`, `zbl` or `oldid`, under
the rule for [extension](#extensions) keys, to strings, and `sha256` is 64
lowercase hex digits: the SHA-256 of the bytes that the `uri` next to the pin
points at. A status pin has no `uri` next to it, so there `sha256` is the
SHA-256 of the file the pin names. `commit` is a full Git object ID: 40
lowercase hex digits, or 64 in a SHA-256 repository. `date` and `retrieved` are
strings; ISO 8601 is recommended but not checked. `revision` is a site's own
revision identifier, and `url` is a [reference](#references). A generic pin
checks only `url`.

```json
"pin": { "type": "website", "title": "C*-algebra", "owner": "Wikipedia",
         "url": "https://en.wikipedia.org/w/index.php?title=C*-algebra&oldid=1374776629",
         "revision": "1374776629", "retrieved": "2026-10-01" }
```

```json
"pin": { "type": "repository", "url": "https://github.com/leanprover-community/mathlib4",
         "commit": "<40 hex digits>", "path": "Mathlib/Analysis/CStarAlgebra/Classes.lean",
         "module": "Mathlib.Analysis.CStarAlgebra.Classes", "declaration": "CStarAlgebra" }
```

A pin describes; it does not verify. Whether the local copy matches the pinned
bytes, and whether the pinned revision still exists, is for tools to check.

## Status, kind, label and note

`status`, `kind`, `label` and `note` are optional nonempty strings that describe
the link. They are the producer's claims, and the format verifies none of them.
`status` says how far the producer judges the informal item to be formalized:
in what `status.pin` cites when there is one, and otherwise in the formal
library the producer had in mind. `formalized`, `partial` and `not_formalized`
are the recommended values. Even `formalized` next to a `target` is a judgment,
not a checked equivalence. `kind` names the informal item; `definition`,
`theorem`, `lemma`, `proposition`, `example`, `remark` and `exercise` are
recommended. `label` is a short title and `note` is free text. Any nonempty
string is valid, and applications agree on values among themselves.

`status` may also be an object with `value`, `pin` and `extensions`. `value` is
the string above, so `"partial"` and `{ "value": "partial" }` say the same thing.
`pin` cites what the status was judged against, such as the formal library at a
commit. Every key is optional, so `{}` is valid and says nothing.

```json
"status": { "value": "not_formalized",
            "pin": { "type": "repository", "url": "https://github.com/leanprover-community/mathlib4",
                     "commit": "<40 hex digits>" } }
```

A record with no `target` and a `not_formalized` status claims a checked
absence, and the status `pin` says where it was checked. A record with neither
is merely unlinked.

## Extensions

`extensions` maps nonempty keys to any JSON values. A key contains none of the
characters that a [reference](#references) excludes. Namespaced keys such as `org.example.tool` are recommended. Annotation,
source, target and status extensions never merge with each other. Consumers keep
unknown values unchanged and never fetch or run them. An extension is not a
trusted claim.

## References

`source.uri`, `target` or `target.uri`, a pin's `url`, a location's `profile`
and `$schema` are nonempty URI or IRI references. They contain no `White_Space`,
no C0 or C1 control (U+0000–001F, U+007F–009F), no bidirectional formatting or
zero-width character (U+200B–200F, U+202A–202E, U+2066–2069, U+FEFF) and
neither U+FFFE nor U+FFFF, so a link cannot display as another; and each `%`
starts a percent-encoding such as `%20`. Relative and absolute references are
allowed, including names such as `urn:isbn:9780000000000`. The check is
lexical: it does not parse the reference, so `http://[x` passes.

A relative reference resolves against the URI of the document that carries
the annotation: the file, or the retrieval URI of the response that delivered
the record, as in [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986#section-5).
This holds inside [JSONL](#discovery) files too. It never resolves against
the source, the `id`, the repository or the working directory. Code that holds
an annotation in memory must keep that base. Moving an annotation means keeping
the base or rewriting the references.

Extension strings are not references. To link a Lean declaration, give
`target.uri` a URL, such as the file at a commit, and name the declaration in
`target.pin.declaration`; a bare name in `target` is read as a relative reference.
Percent-encode `%`, spaces, `#` and `?` in file names. A fragment in `source.uri` is
kept as part of the reference but selects nothing; in built-in modes `location`
is the selection.

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
- Otherwise the record's value wins. Arrays are replaced, not merged.
- A `null` removes the inherited member. Where nothing is inherited, the
  record's value is kept as written.

This is [JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396) with the
record as the patch, except that a `null` with nothing to remove is kept, so a
record read without defaults is read exactly as written. The rules name no
member: any member can have a default, `extensions` included. So a string
`target` or `status` replaces an inherited object, `pin` included; write
`{ "uri": ... }` or `{ "value": ... }` to keep it.

```json
{ "source": { "type": "pdf", "uri": "../notes.pdf" },
  "target": { "pin": { "type": "repository", "url": "https://example.org/formal",
                       "commit": "<40 hex digits>" } } }
```

With that file as `chapter-1/_defaults.json`, a record in `chapter-1/` or
below needs only what is its own, such as a `location` and a `target.uri`.

Defaults files nest. A reader applies the `_defaults.json` in the annotation
file's folder and in each folder above it, outermost first, so the nearest one
wins. Each defaults file merges over the ones above it by the rules above, so a
`null` in a defaults file removes an outer default, and one with nothing above
it to remove is kept and reaches every record below. For local files that goes
up to the root of the file system. A reader that fetches annotations over the
web is given a base URL, the root of the companion, and never looks above it;
given none, it applies no defaults. A [JSONL](#discovery) file takes defaults
like any annotation file, one record at a time.

A relative reference in a defaults file resolves against the defaults file.
A reader that merges records rewrites the inherited references in
[References](#references) so that they resolve the same way from the
annotation's file; extension strings are copied unchanged.

Validation applies to the merged record, so a record may leave out `source`
when a defaults file supplies it. A defaults file that is not a JSON object,
or that a reader cannot read, is a problem, and the records below it are not
read.

## Validation

Validation checks the JSON rules below, the JSON Schema, and two things the
schema cannot express: a PDF `rect` has positive size and fits the page, and
LaTeX `lines` are in order. Neither of the two applies to a location with a
`profile`. Validation never resolves locations, fetches resources or judges
mathematics. Where the schema asks for an integer, a JSON number with no
fractional part counts, so `2.0` is a valid `page`, as in JSON Schema.

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
