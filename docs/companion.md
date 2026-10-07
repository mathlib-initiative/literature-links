# Annotation reference

An annotation links one informal source, or a location in it, to one formal
destination. Only `source` and `target` are required. The format is an
unversioned working draft. The [JSON Schema](../schema/companion.schema.json)
gives its structure, and [validation](#validation) adds two checks.

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
not a serialization of it.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `source.type` | Yes | `pdf`, `latex`, `html` or `generic` |
| `source.uri` | Yes | A [reference](#references) to the informal resource |
| `target` | Yes | One reference to the formal destination |
| `location` | No | An object selecting part of the source |
| `id` | No | A nonempty string label, not necessarily unique |
| `extensions`, `source.extensions` | No | Objects of [application data](#extensions) |
| `$schema` | No | A reference used as a tooling hint |

Other fields are invalid at the top level, in `source` and in built-in
locations. Two targets or two passages need two annotations, and annotations
share nothing. An array is not an annotation.

## Location

Without `location`, the annotation links the whole source. A `null` location is
invalid. In `generic` mode any object is valid, including `{}`. In the other
modes `location` must take one of the forms below, so `{}` is invalid. An empty
generic location is not the same as an absent one.

A consumer must not treat an unresolved, ambiguous or unsupported location as
the whole source. It keeps the location and reports its status. It reports
missing or ambiguous matches, such as duplicate labels or IDs, and never picks
the first one.

### PDF

`{ "page": 3, "rect": [0.1, 0.2, 0.6, 0.15] }`

`page` counts physical pages from 1, ignoring page labels. Without `rect` it
selects the whole page. `rect` is `[x, y, width, height]` on the displayed
CropBox, or the default page box, after the page's own rotation. The origin is
the top-left corner and y grows down. The values are in [0, 1], width and height
are positive, and x + width and y + height are at most 1.

### LaTeX

Use exactly one of `{ "label": "thm:lagrange" }` or `{ "lines": [12, 18] }`.

`label` is a nonempty literal label in the file. The application handles macros,
included files and generated labels. `lines` is an inclusive range of positive
integers, with end at least start. Lines count from 1 in the decoded file, and
CRLF, CR and LF each end a line.

### HTML

Use exactly one of these:

- `fragment` is a decoded element ID with no leading `#`, whitespace or
  controls. It is not percent-decoded again, so `"a%20b"` is a literal ID.
- `css` is a nonempty CSS selector. The checker does not parse it.
- `quote` is `{ "exact": "...", "prefix": "...", "suffix": "..." }`. `exact` is
  nonempty. The optional `prefix` and `suffix` are the text just before and
  after the match. The checker keeps all three as written.

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
Its producer and consumer define it. A `profile` field is only a convention. A
consumer keeps unknown locations and reports them as unsupported. Text offsets
need a unit defined by the application.

## Extensions

`extensions` maps nonempty keys without whitespace or controls to any JSON
values. Namespaced keys such as `org.example.tool` are recommended. Annotation
and source extensions never merge. Consumers keep unknown values unchanged and
never fetch or run them. An extension is not a trusted claim.

## References

`source.uri`, `target` and `$schema` are nonempty URI or IRI references without
`White_Space` or C0/C1 controls (U+0000–001F, U+007F–009F). Relative, absolute
and opaque references are allowed. The check is lexical, and nothing is fetched.

A relative reference resolves against the URI of the file that holds the
annotation, as in [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986#section-5).
This holds inside arrays and JSONL files too. It never resolves against the
source, the `id`, the repository or the working directory. Code that holds an
annotation in memory must keep that base. Moving an annotation means keeping
the base or rewriting the references.

Extension strings are not references. A bare Lean name is a relative reference.
Percent-encode spaces, `#` and `?` in file names. In built-in modes, select with
`location`, not with a fragment of `source.uri`.

A valid annotation grants no permission to open or run anything. `$schema` never
replaces the bundled schema. The schema's `$id` is a name, not a download.

## Validation

Validation is the JSON Schema plus two checks: a PDF `rect` has positive size
and fits the page, and LaTeX `lines` are in order. It never resolves locations,
fetches resources or judges mathematics.

JSON input must have unique keys, finite numbers and no unpaired surrogates,
even inside opaque data. The Python reader keeps integers exact and reads other
numbers as floats. It rejects overflow and nonzero underflow. Very large or deep
input may be rejected. Consumers that use doubles keep integers exact only up to
2⁵³ − 1, so use strings for exact decimals and large identifiers.

`companion.check` returns `Problem(code, path, message)` items with the codes
`JSON`, `SCHEMA`, `PDF_RECT` and `LATEX_LINES`. `companion.validate` returns the
messages. `companion.loads` only parses. Nothing checks uniqueness across
annotations. `companion.dumps` keeps key order and writes two-space indentation
and a final newline.

## Discovery

`formal-companion-annotations scan` and `discovery.collect` read annotations
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
  are case-sensitive shell wildcards on the path relative to the root. `*` also
  matches `/`, and a leading `**/` also matches files in the root.
- Hidden directories are read. Symlinks are skipped while walking and are an
  error when named explicitly.
- Files are read in sorted path order, each file once.
- Unrelated or malformed JSON in a selected file is reported, not skipped. Valid
  annotations from other files are still returned.
- Repeated `id` values and identical annotations are kept.

`scan` exits 0 when it finds annotations and no problems. It exits 1 for an
invalid annotation or file shape. It exits 2 for a read, JSON, path or symlink
failure, or when it finds no annotations. Status 2 wins over 1.
