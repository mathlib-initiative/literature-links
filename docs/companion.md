# Annotation reference

One Formal Companion Annotation (FCA) associates **one informal source, or a
location in it, with one formal destination**. Only `source` and `target` are
required. The format is an unversioned working draft.

Start with the [local tutorial](../examples/tutorial/README.md), which includes
both endpoints, or browse the [examples](../examples/README.md). The
[JSON Schema](../schema/companion.schema.json) describes the record's structure;
the additional checks below complete its validation rules.

## One association

```json
{
  "source": { "type": "html", "uri": "informal.html" },
  "location": { "fragment": "reflexivity" },
  "target": "formal.html#reflexivity"
}
```

Here `source` is the informal endpoint and `target` the formal endpoint. The
names establish a consistent direction for storage; an application can browse
the association in either direction. The informal article remains its own
document. The annotation neither contains nor replaces it.

An association does not by itself assert equivalence, implication, proof
completion, correctness, or human review. It does not establish that the formal
destination exists or expresses the intended statement. Applications may record
such claims separately in extensions and decide how to verify them.

FCA is **inspired by, but is not a serialization of, the W3C Web Annotation Data
Model**. W3C annotations use a body/target model and a JSON-LD context; FCA's
`source` and `target` are its own field names, not a renaming of those roles.
Interchange needs an explicit adapter, including a choice of roles and selector
mapping. See the [W3C model](https://www.w3.org/TR/annotation-model/#annotations)
and the repository's [compatibility notes](compatibility.md).

## Fields

| Field | Required? | Meaning |
|---|---|---|
| `source` | Yes | An object identifying the informal resource. |
| `source.type` | Yes | `pdf`, `latex`, `html`, or `generic`; chooses the location convention. |
| `source.uri` | Yes | A nonempty resource reference; see [references and bases](#references-and-bases). |
| `target` | Yes | One nonempty reference to the formal destination, optionally with its own fragment. |
| `location` | No | An object selecting part of the informal source. Omission selects the whole source. |
| `id` | No | A nonempty, application-defined string label. It need not be a URI or globally unique. |
| `extensions` | No | An object of application metadata for this association. |
| `source.extensions` | No | An independent object of metadata for the source. |
| `$schema` | No | A nonempty reference used as a tooling hint; it does not override this validator. |

Unknown fields at the annotation or source level are invalid. Built-in locations
also reject unknown fields. Put application metadata in `extensions`, or use
`generic` for an application-defined location.

Two formal destinations or two informal occurrences require two records. Repeat
the source fields as needed; no shared defaults are inferred. An array or an
`annotations` wrapper is not an annotation. [Discovery](discovery.md) can read
arrays and JSONL as carriers of independently valid records, without requiring
a manifest, folder layout, or one file per record.

### Whole resource or location

| Value of `location` | Meaning |
|---|---|
| Absent | The whole informal resource, in every mode. |
| A valid built-in location | The selected PDF page/region, LaTeX label/lines, or HTML element/text. |
| An object in `generic` mode, including `{}` | An application-defined selection; the core assigns no further meaning. |
| `{}` in `pdf`, `latex`, or `html` mode | Invalid. |
| `null` | Invalid in every mode. |

A consumer must not silently turn an unresolved, ambiguous, or unsupported
location into a whole-resource association. Preserve it and show its resolution
status separately. An empty generic location is not interchangeable with an
absent location.

## PDF

```json
{ "page": 3, "rect": [0.1, 0.2, 0.6, 0.15] }
```

`page` counts physical pages from 1, independently of printed numbers or PDF
page labels. Without `rect`, the location selects the page. Optional `rect` is
exactly `[x, y, width, height]`, normalized to the **displayed CropBox after
intrinsic page rotation**. Use the effective default page box if no CropBox is
specified. The origin is top-left; x increases rightward and y downward.

All four values are in [0, 1]. Width and height must be positive; x + width and
y + height must not exceed 1. These are FCA display coordinates, not raw PDF
user-space coordinates or rectangle endpoints. A viewer converts them to its
own display coordinates. The convention also works for scanned pages without
a text layer. Validation cannot confirm that the page exists or that a rectangle
covers the intended passage.

## LaTeX

Use exactly one of these location forms:

```json
{ "label": "thm:lagrange" }
```

```json
{ "lines": [12, 18] }
```

`label` is a nonempty literal label name in the identified source file. Macro
expansion, included files, and generated labels are application responsibilities.
A consumer may use compiled structure to find it; the core does not prescribe
which surrounding environment to highlight. Report missing or duplicate matches.

`lines` contains positive integers `[start, end]`, inclusive, with end at least
start. Count from 1 in the decoded source file. CRLF, CR, and LF each count as
one line break; `[12, 12]` selects one line. This convention differs from
[RFC 5147's line boundaries](https://www.rfc-editor.org/rfc/rfc5147#section-2.1),
which count from zero and exclude the ending boundary.

## HTML

Use exactly one of `fragment`, `css`, or `quote`:

```json
{ "fragment": "reflexivity" }
```

```json
{ "css": "article #reflexivity" }
```

```json
{ "quote": { "exact": "Every natural number equals itself.", "prefix": "Claim. " } }
```

`fragment` is the literal decoded element ID, without a leading `#`, whitespace,
or controls. Do not percent-decode it again: `"a%20b"` names an ID containing
those literal characters. `css` is a nonempty selector evaluated against the
identified document; the checker does not parse or execute CSS.

For `quote`, construct this draft's text layer:

1. Take the body's `textContent` after removing `script`, `style`, and `template`
   subtrees. Use the document element if there is no body.
2. Collapse each run of Unicode `White_Space` to one ASCII space, then trim
   leading and trailing whitespace.
3. Do not case-fold, normalize Unicode, or insert spaces at element boundaries.
   Include hidden text outside the excluded subtrees. Exclude shadow DOM and
   iframe content.

Here `White_Space` means U+0009–000D, U+0020, U+0085, U+00A0, U+1680,
U+2000–200A, U+2028–2029, U+202F, U+205F, and U+3000, as listed in the
[Unicode property data](https://www.unicode.org/Public/UCD/latest/ucd/PropList.txt).
For example, `<b>natural</b><i>number</i>` contributes `naturalnumber`, without
an inserted space.

`exact` is nonempty. Optional `prefix` and `suffix` are literal context
immediately before and after the match, outside the selection. Choose these
strings from the text layer above; prefix/suffix may include a boundary space.
The checker preserves them without normalization and does not check whether
they match. Other text-extraction conventions belong in generic mode.

Report missing or ambiguous matches, including selectors matching multiple
elements and duplicate element IDs, rather than choosing the first. The core
does not pin a dynamic page's state. This quote convention does not claim
interchangeability with the
[W3C Text Quote Selector](https://www.w3.org/TR/annotation-model/#text-quote-selector).

## Generic and extensions

```json
{
  "source": { "type": "generic", "uri": "urn:example:dataset" },
  "location": { "table": "results", "row": "42" },
  "target": "urn:example:formal:result"
}
```

A generic location is an arbitrary JSON object. Its producer and consumer define
its meaning; no profile, namespace, registry, MIME type, or hosted schema is
required. A `profile` field is an application convention with no core behavior.
Preserve unknown locations and report them as unsupported. Markdown, wikitext,
images, and databases can use this mode without adding built-in formats.
An application defining text offsets should specify its own unit, such as
Unicode code points or UTF-16 code units; FCA supplies no default offset unit.

Each `extensions` object maps nonempty keys without whitespace or controls to
arbitrary JSON values. Namespaced keys such as `org.example.catalog` are
recommended for exchange; ordinary keys are valid. Annotation extensions and
source extensions do not inherit from or merge with each other. Preserve unknown
keys and values without fetching, executing, or reinterpreting them. Extensions
can carry grouping, source revision locks, descriptions, evidence, or review
state. Their presence does not make those claims trusted or mandatory.

## References and bases

`source.uri`, `target`, and `$schema` accept nonempty URI/IRI-reference strings
without Unicode `White_Space` or C0/C1 controls (U+0000–001F and U+007F–009F).
Relative references, Unicode, absolute URLs, and opaque identifiers such as
`urn:example:result:1` are allowed. This is a lexical check, **not full URI syntax
validation** or a list of supported schemes. The checker preserves reference
strings and fetches nothing. See the standards for
[URI references](https://www.rfc-editor.org/rfc/rfc3986#section-4.1) and
[internationalized references](https://www.rfc-editor.org/rfc/rfc3987).

Relative references use the **containing carrier's URI** as their base, following
[URI reference resolution](https://www.rfc-editor.org/rfc/rfc3986#section-5).
This also applies to records inside an array or JSONL file. They do not implicitly
use the informal source, annotation ID, repository root, or working directory
as a base. An in-memory caller must retain or supply that carrier context. See
[worked examples](discovery.md#origins-and-relative-references).

Moving a record requires preserving its original base or deliberately rebasing
its relative references. Formatting alone does neither. Do not treat arbitrary
extension strings as references to rewrite. A bare Lean name is only a relative
reference, not an implicit library lookup. Percent-encode literal filename
spaces and reserved delimiters such as `#` or `?`. In built-in modes, prefer a
complete source resource URI plus `location`, avoiding competing selectors in
both a source fragment and a location.

A viewer chooses which schemes it can navigate. Data acceptance grants no
permission to execute a URI or extension. `$schema` is a tooling hint, never a
remote override of the bundled validator; the schema's own `$id` is an identifier,
not a promise that this unpublished draft is available at that web address.

## Validation and serialization

Full validation combines the supplied
[JSON Schema draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-core)
schema with semantic checks for positive, in-bounds PDF rectangles and ordered
LaTeX line ranges. A generic JSON Schema validator alone does not check all
these cross-field rules. Neither kind of validation resolves selectors, checks
resources, runs Lean, or judges a mathematical relationship.

FCA's JSON reader requires unique object keys, finite numbers, and strings
without unpaired Unicode surrogates, including inside opaque data. These strict
interchange rules avoid cases for which general JSON implementations can disagree;
they are not all universal JSON grammar restrictions. See
[RFC 8259 on objects](https://www.rfc-editor.org/rfc/rfc8259#section-4) and
[Unicode](https://www.rfc-editor.org/rfc/rfc8259#section-8.2).

The Python implementation preserves integers within its interpreter's supported
limits, but fractional numbers use Python floats: decimal spellings and arbitrary
decimal precision are not preserved. Overflow and nonzero values that underflow
to zero are rejected as implementation range errors; true signed zero remains
valid, and ordinary nonzero rounding still occurs. Other consumers may have
narrower numeric limits. Ordinary IEEE 754 binary64 consumers guarantee exact
integer interchange within ±(2⁵³ − 1); see
[RFC 8259 on numbers](https://www.rfc-editor.org/rfc/rfc8259#section-6). This is
an interoperability consideration, not an FCA integer bound. Use application
strings when exact decimal values or identifiers must survive such consumers.
Resource limits may reject large or deeply nested inputs with a diagnostic.

`companion.check` returns structured `Problem(code, path, message)` findings:
`JSON` for unsupported values, `SCHEMA` for structural failures, `PDF_RECT` for
rectangle bounds/extents, and `LATEX_LINES` for reversed intervals.
`companion.validate` returns readable messages. `companion.loads` only parses
strict JSON; call `check` or `validate` afterward. No directory-wide identity or
uniqueness check belongs to this atomic validator.

There is no canonical byte representation or required property order. The
formatter preserves object/array order, uses two-space indentation and a trailing
newline, and does not preserve original whitespace or numeric spellings.
`version` and `schema_version` are unknown core fields and are rejected. Software
release numbers are separate; see [compatibility](compatibility.md) for earlier
formats and [design rationale](design/minimal-core.md) for the choices here.
