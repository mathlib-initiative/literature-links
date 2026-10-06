# Companion v2 working draft

This experimental, unpublished format describes associations from one informal
source to formal resources. `version: 2` identifies the format; `2.0.0a1` is the
package prerelease. Its [JSON Schema](../schema/companion-v2.schema.json) ships
with the checker.

## Core document

```json
{
  "version": 2,
  "source": { "type": "pdf", "uri": "notes.pdf" },
  "annotations": [
    { "location": { "page": 4 }, "target": "https://example.org/formal/Result.html#result" }
  ]
}
```

| Object | Required fields | Optional fields |
|---|---|---|
| Document | `version` (number 2), `source`, `annotations` (array) | `$schema`, `extensions` |
| Source | `type` (`pdf`, `latex`, `html`, `generic`), `uri` (string) | `extensions` |
| Annotation | `target` (string) | `location` (object), `id` (nonempty string), `extensions` |

One source identifies one concrete resource. A multi-file project uses several
documents; collecting them is an application concern. An empty annotations
array is valid. Multiple formal destinations or several occurrences use separate
annotations. Optional IDs must be unique within the document; they have no
global identity semantics. Unknown core fields are invalid.

An annotation asserts **an association only**. Neither validation nor a link
asserts equivalence, proof completion, correctness, human review, or that the
formal resource contains the intended statement.

An absent location selects the **entire source**. A missing or unsupported
anchor must not be silently replaced with absence. Built-in locations cannot
be empty. `null` is invalid. Generic locations may be empty objects, whose
meaning still belongs to the application.

## References and bases

`source.uri`, `target`, and optional `$schema` are nonempty URI/IRI-reference
strings without literal whitespace or control characters. Relative references,
Unicode, absolute URLs, and opaque URIs such as `urn:example:result:1` are
allowed. The checker enforces this lexical rule, not full URI grammar or scheme
support. It preserves these strings and fetches nothing.

Relative source and target references resolve against the **companion document's
location** using ordinary URI resolution. They do not implicitly resolve against
the source or a repository root. An in-memory caller supplies the base. Moving a
document requires preserving its base or deliberately rewriting its references.
A bare Lean name is merely a relative reference, not an implicit library lookup.
Use URI escaping for literal filename spaces, `#`, `?`, and other delimiters.
For built-in modes, identify the complete source file/page and use `location`
to select a portion; avoid combining a source fragment with another locator.

A viewer handles scheme support and navigation under its own rules. Accepting
data is not permission to execute it. `$schema` is a tooling hint, not a remote
override of the built-in validator. The schema's `$id` is an identifier, not a
promise of a hosted public endpoint.

## PDF

```json
{ "page": 3, "rect": [0.1, 0.2, 0.6, 0.15] }
```

`page` is a positive integer counting physical pages from 1, independent of
printed numbers and PDF page labels. Without `rect`, it selects the page.
Optional `rect` is exactly `[x, y, width, height]`, normalized to the **displayed
CropBox after intrinsic page rotation**. Use the effective default page box if
no CropBox is specified. The origin is top-left; x increases rightward, y
downward. All values lie in [0, 1]; width and height are positive, and x + width
and y + height must not exceed 1.

This works for scanned PDFs without a text layer. It is this draft's convention,
not raw PDF user-space coordinates or a W3C percentage fragment. Viewers
transform it into their display coordinates. The offline checker cannot verify
page existence or that a rectangle covers the intended passage.

## LaTeX

Exactly one location form is permitted:

```json
{ "label": "thm:lagrange" }
```

```json
{ "lines": [12, 18] }
```

`label` is a nonempty literal label name in the identified source file. A
consumer may use compiled structure to locate it; macro expansion, included
files, and generated labels are application responsibilities. Missing and
duplicate matches must be reported. The core does not prescribe which
surrounding environment a viewer highlights.

`lines` contains two positive integers, inclusive start and end, with end at
least start. Count lines from 1 in the decoded source file. CRLF, CR, and LF
each count as a single line break. `[12, 12]` selects one line. These are not
RFC 5147's zero-based, half-open boundaries.

## HTML

Exactly one of `fragment`, `css`, or `quote` is permitted:

```json
{ "fragment": "theorem-2" }
```

```json
{ "css": "article #theorem-2" }
```

```json
{ "quote": { "exact": "Every sample group is finite.", "prefix": "Claim. ", "suffix": " Proof." } }
```

`fragment` is the literal decoded element ID, with no leading `#`, whitespace,
or controls. Do not percent-decode it again. `css` is a nonempty selector string
evaluated against the identified HTML document. The checker does not parse CSS.

This draft's quote convention takes the body's textContent after removing
`script`, `style`, and `template` subtrees, or the document element if there is
no body. Collapse runs of Unicode White_Space characters to one ASCII space
and trim leading/trailing whitespace. Do not case-fold, normalize Unicode, or
insert spaces at element boundaries. Include hidden text outside the excluded
subtrees; exclude shadow DOM and iframe content. Different text extraction
conventions belong in generic mode.

`exact` is nonempty. Optional `prefix` and `suffix` are literal context
immediately preceding and following a match in that text layer; they are not
part of the selection. These supplied strings already use that convention and
are not rewritten. Prefix/suffix may contain a single boundary space. A checker
pass does not prove a quote can match. A consumer reports absent or ambiguous
matches, including CSS matching multiple elements or duplicate IDs, rather than
quietly choosing the first. Dynamic page state is not pinned by the core.
This convention does not claim W3C TextQuoteSelector interchange.

## Generic and extensions

```json
{
  "version": 2,
  "source": { "type": "generic", "uri": "urn:example:dataset" },
  "annotations": [
    { "location": { "table": "results", "row": "42" }, "target": "urn:example:formal:result" }
  ]
}
```

A generic location is an arbitrary JSON object. Its producer and consumer own
its semantics. No profile, namespace, registry, MIME type, or hosted schema is
required. A tool may add a `profile` identifier, but it has no core behavior.
Viewers preserve unknown locations and report them as unsupported rather than
pretending to resolve them. This accommodates Markdown, wikitext, images,
databases, and future formats without adding built-in modes now.

An `extensions` object maps nonempty keys without whitespace/control characters
to arbitrary JSON values. Namespaced keys such as `org.example.catalog` are
recommended for exchange; ordinary keys are allowed. Root, source, and
annotation extensions are independent, with no implied inheritance or merging.
Consumers preserve unfamiliar keys and values and do not fetch or execute them.
Extensions may hold confidence, evidence, grouping, source locks, accessible
descriptions, or review state without making these mandatory core fields.

## Validation and serialization

JSON has unique object keys, finite numbers, and valid Unicode strings. Full
validation checks the schema plus unique annotation IDs, positive PDF extents
contained in the page, and ordered LaTeX ranges. These cross-field rules are not
all expressible in the supplied schema; schema validation alone is insufficient.

The standard-library Python implementation rejects duplicate keys, nonfinite
numbers including overflowing exponents, unsupported Python values, cycles,
and unpaired surrogates. It preserves decoded values, integer precision within
the interpreter's supported limits, and object/array order. Fractions use normal
Python float decoding; decimal lexemes and original whitespace are not preserved.
Use strings for exact decimal application values. Resource and interpreter
limits can reject otherwise representable input with a diagnostic.

There is **no canonical byte representation** or required ordering. Formatting
uses two-space indentation and a trailing newline without sorting. Unknown
versions fail. V1 remains a separate legacy format using `schema_version`;
mixed v1/v2 core shapes fail. See [migration](migration-v2.md) and the
[design rationale](design/minimal-core.md), including the relationship to the
[W3C Web Annotation model](https://www.w3.org/TR/annotation-model/).
