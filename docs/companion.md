# Annotation reference

An annotation links one informal source, or a location in it, to one formal
destination. The [JSON Schema](../schema/companion.schema.json) gives its
structure, and [validation](#validation) adds two checks. The format has no
version field; it carries the version of the release. Records valid under 1.x
stay valid in later 1.x; a breaking change bumps the major version.

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

## Fields

| Field | Required | Meaning |
|---|---|---|
| `source.type` | Yes | `pdf`, `latex`, `html` or `generic` |
| `source.uri` | Yes | A [reference](#references) to the companion's copy of the informal resource |
| `source.pin` | No | A [pin](#pins) citing the informal resource outside the companion |
| `target` | No | A reference to the formal destination, or an object with `uri`, `pin` and `extensions` |
| `location` | No | An object selecting part of the source |
| `status` | No | A [fact](#facts): a nonempty string, or an object with `value`, `pin` and `extensions` |
| `kind`, `label`, `note` | No | Nonempty strings: [facts](#facts) about the link |
| `id` | No | A nonempty string label, not necessarily unique |
| `extensions`, `source.extensions`, `target.extensions`, `status.extensions` | No | Objects of [application data](#extensions) |
| `$schema` | No | A reference used as a tooling hint |

Only `source` is required. Without `target`, the annotation records an informal
passage with no formal counterpart. Other fields are invalid at the top level,
in `source`, in `target` and `status` objects, in built-in pins and in built-in
locations. Two targets or two passages need two annotations. No field is
inherited from another record, only from [folder defaults](#folder-defaults).
An array is not an annotation.

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
the whole source. A location whose `profile` it does not know is unsupported. It
keeps the location and reports its status. It reports missing or ambiguous
matches, such as duplicate labels or IDs, and never picks the first one.

### PDF

`{ "page": 3, "rect": [0.1, 0.2, 0.6, 0.15] }`

`page` counts physical pages from 1, ignoring page labels. Without `rect` it
selects the whole page. `rect` is `[x, y, width, height]` as fractions of the
displayed page box: the CropBox, or the MediaBox when there is none, after the
page's `Rotate` entry is applied. The origin is the top-left corner and y grows
down. The values are in [0, 1], width and height are positive, and x + width and
y + height are at most 1.

### LaTeX

Use exactly one of `{ "label": "thm:lagrange" }` or `{ "lines": [12, 18] }`.

`label` is the literal argument of a `\label` command. It is looked up in the
document rooted at `source.uri`, including the files that document inputs;
macro expansion and generated labels are the application's concern. `lines` is
an inclusive range of positive integers, with end at least start. Lines count
from 1 in the file decoded as UTF-8, and CRLF, CR and LF each end a line.

### HTML

Use exactly one of these:

- `fragment` is the decoded value of an element's `id` attribute, with no
  leading `#`, whitespace or controls; `name` attributes do not count. It is
  not percent-decoded again, so `"a%20b"` is a literal ID.
- `css` is a nonempty CSS selector. The checker does not parse it.
- `quote` is `{ "exact": "...", "prefix": "...", "suffix": "..." }`. `exact` is
  nonempty. The optional `prefix` and `suffix` are the text just before and
  after the match. When given, a match must be immediately preceded and
  followed by them; they narrow the match and are not part of the selection.
  The checker keeps all three as written.

A quote matches this text layer. Take the `textContent` of the body, or of the
document element if there is no body, without `script`, `style` and `template`
elements. Replace each run of `White_Space` with one space and trim both ends.
Do not change case, normalize Unicode or add spaces between elements, so
`<b>natural</b><i>number</i>` gives `naturalnumber`. Hidden text counts. Shadow
DOM and iframes do not. `White_Space` means U+0009–000D, U+0020, U+0085,
U+00A0, U+1680, U+2000–200A, U+2028–2029, U+202F, U+205F and U+3000. Other text
conventions belong in `generic` mode.

### Generic

A generic location is any JSON object, such as `{ "table": "results", "row": "42" }`.
Its producer and consumer define it. A `profile` key names the convention, as in
every mode.
Text offsets need a unit defined by the application.

## Pins

`uri` is the local pin: where the companion keeps its copy of the resource,
usually a relative path. A `pin` is the global pin: a citation that identifies
the resource outside the companion, the way a bibliography entry does. A pin
has a `type`, which chooses its keys. Every other key is optional, and a pin
with only a `type` is valid.

| `type` | Keys |
|---|---|
| `website` | `title`, `owner`, `url`, `revision`, `date`, `retrieved`, `sha256`, `identifiers` |
| `book` | `title`, `author`, `publisher`, `edition`, `date`, `isbn`, `url`, `retrieved`, `sha256`, `identifiers` |
| `paper` | `title`, `author`, `venue`, `volume`, `number`, `pages`, `date`, `doi`, `arxiv`, `url`, `retrieved`, `sha256`, `identifiers` |
| `repository` | `url`, `commit`, `path`, `line`, `module`, `declaration`, `sha256`, `identifiers` |
| `generic` | Any keys the application defines |

Other keys are invalid in the built-in types; put them in `identifiers` or use
`generic`. Values are nonempty strings, except that `author` is a string or an
array of strings, `line` is a positive integer, `identifiers` maps names such
as `wikidata`, `zbl` or `oldid` to strings, and `sha256` is 64 lowercase hex
digits: the SHA-256 of the bytes that the `uri` next to the pin points at. A
status pin has no `uri` next to it, so there `sha256` is the SHA-256 of the file
the pin names. `date` and `retrieved` are
strings; ISO 8601 is recommended but not checked. `revision` is a site's own
revision identifier and `commit` a full Git object ID. `url` is a
[reference](#references).

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

## Facts

`status`, `kind`, `label` and `note` are optional facts about the link, given as
nonempty strings. `status` says how far the informal item is formalised;
`formalized`, `partial` and `not_formalized` are the recommended values. `kind`
names the informal item; `definition`, `theorem`, `lemma`, `proposition`,
`example`, `remark` and `exercise` are recommended. `label` is a short title and
`note` is free text. Any nonempty string is valid, and applications agree on
values among themselves.

`status` may also be an object with `value`, `pin` and `extensions`. `value` is
the string above, so `"partial"` and `{ "value": "partial" }` say the same thing.
`pin` cites what the status was judged against, such as the formal library at a
commit. Every key is optional, so `{}` is valid and says nothing.

```json
"status": { "value": "not_formalized",
            "pin": { "type": "repository", "url": "https://github.com/leanprover-community/mathlib4",
                     "commit": "<40 hex digits>" } }
```

A record with no `target` and a `not_formalized` status records a checked
absence, and the status `pin` says where it was checked. A record with neither
is merely unlinked. The format verifies none of these claims.

## Extensions

`extensions` maps nonempty keys without whitespace or controls to any JSON
values. Namespaced keys such as `org.example.tool` are recommended. Annotation,
source, target and status extensions never merge. Consumers keep unknown values
unchanged and never fetch or run them. An extension is not a trusted claim.

## References

`source.uri`, `target` or `target.uri`, a pin's `url`, a location's `profile`
and `$schema` are nonempty URI or IRI references without `White_Space` or C0/C1 controls (U+0000–001F,
U+007F–009F). Relative, absolute and opaque references are allowed. The check
is lexical.

A relative reference resolves against the URI of the document that carries
the annotation: the file, or the retrieval URI of the response that delivered
the record, as in [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986#section-5).
This holds inside arrays and JSONL files too. It never resolves against the
source, the `id`, the repository or the working directory. Code that holds an
annotation in memory must keep that base. Moving an annotation means keeping
the base or rewriting the references.

Extension strings are not references. A bare Lean name is a relative reference.
Percent-encode spaces, `#` and `?` in file names. A fragment in `source.uri` is
kept as part of the reference but selects nothing; in built-in modes `location`
is the selection.

A valid annotation grants no permission to open or run anything. `$schema` never
replaces the bundled schema. The schema's `$id` and a location's `profile` are
names, not downloads.

## Folder defaults

A file named `_defaults.json` holds one JSON object: members shared by every
annotation file in its folder and in the folders below it. It is not an
annotation. Each record read from those files is the defaults merged with the
record as written:

- A member the record leaves out is inherited.
- Where both hold an object, the two merge member by member, at any depth.
- Otherwise the record's value wins. Arrays are replaced, not merged.
- A `null` removes the inherited member. Where nothing is inherited, the
  record's value is kept as written.

This is [JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396) with the
record as the patch, except that a `null` with nothing to remove is kept, so a
record read without defaults is read exactly as written. The rules name no
member: any member can have a default, `extensions` included.

```json
{ "source": { "type": "pdf", "uri": "../notes.pdf" },
  "target": { "pin": { "type": "repository", "url": "https://example.org/formal",
                       "commit": "<40 hex digits>" } } }
```

With that file as `chapter-1/_defaults.json`, a record in `chapter-1/` or
below needs only what is its own, such as a `location` and a `target.uri`.

Defaults files nest. A reader applies the `_defaults.json` in the annotation
file's folder and in each folder above it, outermost first, so the nearest one
wins. For local files that goes up to the root of the file system. A reader
that fetches annotations over the web is given the collection's base URL and
never looks above it. Arrays and JSONL files take defaults like any annotation
file, one record at a time.

A relative reference in a defaults file resolves against the defaults file.
A reader that merges records rewrites the inherited references in
[References](#references) so that they resolve the same way from the
annotation's file; extension strings are copied unchanged.

Validation applies to the merged record, so a record may leave out `source`
when a defaults file supplies it. A defaults file that is not a JSON object,
or that a reader cannot read, is a problem, and the records below it are not
read.

## Validation

Validation is the JSON Schema plus two checks: a PDF `rect` has positive size
and fits the page, and LaTeX `lines` are in order. Neither applies to a location
with a `profile`. Validation never resolves locations,
fetches resources or judges mathematics. Where the schema asks for an integer, a
JSON number with no fractional part counts, so `2.0` is a valid `page`, as in
JSON Schema.

JSON input must have unique keys, finite numbers and no unpaired surrogates,
even inside opaque data. The Python reader keeps integers exact and reads other
numbers as floats. It rejects overflow and nonzero underflow. Very large or deep
input may be rejected. Consumers that use doubles keep integers exact only up to
2⁵³ − 1, so use strings for exact decimals and large identifiers.

`companion.check` returns a `Report` whose `problems` are
`Problem(code, path, message)` items with the codes `JSON`, `SCHEMA`,
`PDF_RECT` and `LATEX_LINES`. `companion.validate` returns them as
`path: message` strings. `companion.loads` only parses. Nothing checks
uniqueness across annotations. `companion.dumps` keeps key order and writes
two-space indentation and a final newline. `companion.merge` and
`companion.rebase` implement [folder defaults](#folder-defaults), and
`discovery.inherit` applies them to a record read from a file.

## Discovery

`literature-links scan` and `discovery.collect` read annotations
from local files. This is a reader convention, not part of the schema.

| File | Annotations | Origin |
|---|---|---|
| JSON object | One | Pointer `""` |
| JSON array | One per member | Pointer `/0`, `/1`, ... |
| JSONL or NDJSON | One per nonblank line | Line number, from 1 |

- Files are UTF-8. A JSONL line holds an object, not an array.
- In JSONL, CRLF, CR and LF each end a line. U+2028 and U+2029 do not. A line
  with only spaces and tabs is blank. Blank lines are skipped but still counted.
- Directories are walked recursively for `.json`, `.jsonl` and `.ndjson` files,
  ignoring case. A file named explicitly may have any suffix.
- `.jsonl` and `.ndjson` files are read by line. Other files are one JSON value.
- `--include` replaces the suffix filter, and `--exclude` always wins. Patterns
  are case-sensitive shell wildcards on the path relative to the root, or on
  the file name for a file named explicitly. `*` also matches `/`, and a
  leading `**/` also matches files in the root.
- Hidden directories are read. Symlinks are skipped while walking and are an
  error when named explicitly.
- A file named `_defaults.json` holds [folder defaults](#folder-defaults), not
  annotations. Every defaults file that covers a selected file applies,
  whatever `--include` and `--exclude` select, and a symlinked one is an error.
- Files are read in sorted path order, each resolved path once.
- Unrelated or malformed JSON in a selected file is reported, not skipped. Valid
  annotations from other files are still returned.
- Repeated `id` values and identical annotations are kept.

Scanning a repository root reads every JSON file under it, vendored and
generated ones included, and reports each one that is not an annotation as a
problem. Keep annotations in a directory of their own, or name them
`*.annotations.json` and select them with `--include '*.annotations.json'`.

`scan` exits 0 when it finds annotations and no problems. It exits 1 for an
invalid annotation, file shape or defaults file. It exits 2 for a read, JSON,
path or symlink failure, or when it finds no annotations. Status 2 wins over 1.
