# Why the companion core is small

The companion format connects informal material to a formal resource. A writer
can describe one association without first building a declaration index, a proof
workflow, or an audit database. The [version 2 specification](../companion-v2.md)
defines the format; this document explains the choices and their costs.

## A complete starting point

```json
{
  "version": 2,
  "source": { "type": "latex", "uri": "chapters/groups.tex" },
  "annotations": [
    {
      "location": { "label": "thm:lagrange" },
      "target": "https://example.org/formal/Groups.html#lagrange"
    }
  ]
}
```

This says that a labeled passage is associated with a formal resource. It does
not claim that the resource proves the passage, that the statements are
equivalent, or that someone has checked the association. Those are valuable
claims, but they need their own evidence and meaning.

The required vocabulary stays small: a version, one source, and annotations
with destinations. PDF, LaTeX, and HTML provide familiar location conventions.
Generic input provides room for applications with different conventions.

## Decisions and costs

| Decision | Benefit | Cost and response |
|---|---|---|
| One concrete source resource per document | No cross-reference tables or site manifests are needed to interpret an annotation. | A book's PDF, LaTeX files, and HTML pages need separate documents. A companion application can collect them. |
| A destination is a URI/IRI reference | Works with different formal libraries, local files, hosted pages, and unpublished identifiers. | A bare identifier may not open in a browser. Library-specific resolution belongs to the consuming application. |
| One destination per annotation | A record has one clear association and can stand alone. | Several destinations repeat a location. A tool can group those records through extensions. |
| Location can be omitted | Associating a whole resource requires no artificial anchor. | Consumers must distinguish an absent location from an unresolved or malformed location. |
| Built-in locations have a closed shape | Misspelled fields fail early rather than quietly changing the selection. | New anchor conventions use generic mode until there is reason to standardize them. |
| Generic locations are opaque objects | A database, image tool, or wiki can participate without registering a new core mode. | Core validation cannot tell whether its locator selects the intended content. The application owns that interpretation. |
| Metadata lives in explicit extension objects | The shared core stays readable and tools can preserve their own information. | Two tools do not automatically understand each other's metadata. Shared extension conventions can be agreed separately. |
| No required source hash, formal revision, or provenance | Handwritten annotations and local unpublished work remain easy. | Moving sources and destinations can make links stale. Applications needing reproducibility should pin resources and record evidence. |
| No required identifiers or canonical ordering | A small document can be written directly without an ID generator. | Synchronization and stable references require a tool to supply optional annotation IDs and define its own update policy. |

Keep an association even when its locator cannot be resolved, but do not display
it as a successfully anchored highlight. Structural validity, successful
resource resolution, correct location, and faithful mathematical correspondence
are separate claims. The core checker establishes only the first.

## Examples to adapt

All eight examples use synthetic references and application conventions. They
are not endorsements of particular libraries, actual database records, or
registered extension standards. Their referenced resources need not exist for
the JSON to validate.

| Example | What it shows |
|---|---|
| [PDF](../../examples/companion-v2/pdf.json) | Associate a physical PDF page with a formal destination. |
| [LaTeX](../../examples/companion-v2/latex.json) | Select a label in one source file. |
| [HTML](../../examples/companion-v2/html.json) | Select an element by its fragment identifier. |
| [Generic](../../examples/companion-v2/generic.json) | Associate an entire resource identified by a URN; no location or metadata is required. |
| [PDF region and multiple links](../../examples/companion-v2/pdf-region-and-links.json) | Repeat a location for different formal destinations; add optional grouping, review information, and accessible display text. |
| [Custom image](../../examples/companion-v2/generic-image.json) | Use a tool's own pixel-region convention and descriptions for an image. |
| [Database record](../../examples/companion-v2/generic-database.json) | Select a table cell using a tool-owned locator, without requiring a profile identifier or namespace for every field. |
| [Markdown block](../../examples/companion-v2/generic-markdown.json) | Add a custom block locator and roadmap metadata without introducing a Markdown mode. |

Namespaces are recommended for extension keys that will be exchanged between
tools; the database example deliberately uses an ordinary `catalog` key to show
that namespaces are not a requirement. The `profile` fields in the image and
Markdown locations are also application choices, not special core fields. A
consumer must not treat their presence as permission to fetch or execute them.

The PDF location convention works without a text layer, including scanned
pages. An image region can also be represented through generic mode. A viewer
should offer useful text alongside a purely visual highlight; the examples
show descriptions in application metadata without making one particular viewer
vocabulary mandatory.

## Whole projects stay in applications

A LaTeX project with `main.tex` and several included chapters can publish one
annotation document for each relevant file. An HTML site can do the same for
each page. A PDF rendering is another resource, with its own annotations. The
core does not infer that a label, HTML fragment, and PDF rectangle are the same
passage merely because their text resembles one another.

An application may carry a common identity in extensions or maintain a separate
catalog of related resources. Relative source and destination references must
retain their base when a document is moved or exported; a tool must not silently
reinterpret a relative destination as relative to the informal source.

This leaves several useful systems possible:

- WikiLean can publish simple associations while retaining matching scores,
  revisions, extraction records, and editorial decisions in its database.
- A formal companion viewer can render standard locations and offer richer
  controls when it understands an extension.
- An Autoform blueprint or another local wiki can express its own anchors in
  generic mode and preserve its dependency graph and work state separately.

These are design boundaries, not claims that integration or rendering support
has already been implemented in those projects.

## Relationship to W3C annotations

The [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
provides the useful distinction between resources and selectors. Its broader
model also supports metadata and structured relationships. The companion core
borrows the idea of selecting part of a resource without requiring JSON-LD,
remote contexts, a graph store, or an annotation transport protocol.

An interchange adapter must be explicit about naming: in a usual W3C mapping,
the informal resource being annotated is the W3C **target**, and the associated
formal resource is a **body**. The companion field named `target` means the
formal destination. Similar field names do not make the two formats identical.

The core format is not a claim of W3C conformance, and a small subset need not
promise lossless interchange for arbitrary W3C annotations. Preserve unfamiliar
information or report conversion loss; do not reinterpret it as a stronger
mathematical claim.

## Cases to verify before relying on a consumer

This checklist describes acceptance cases for format implementations and
applications. It does not imply that the core checker fetches resources or
performs these rendering checks.

- A one-page PDF, a scanned PDF, and a page whose CropBox and rotation differ
  from the original page coordinates. Page numbers are physical, independent
  of printed Roman numerals or page labels.
- A rectangle at a page boundary; an out-of-bounds rectangle; zero-width and
  zero-height regions; non-finite numeric input.
- A LaTeX label with punctuation, a missing label, duplicate labels, and an
  inclusive line range containing exactly one line. A valid label string does
  not prove a unique label exists in the source.
- An HTML element with a non-ASCII identifier, a missing element, an invalid
  CSS selector, a CSS selector matching several elements, a quotation with no
  match, and a quotation repeated in several places. Rendering must handle
  ambiguity explicitly.
- A source resource with no location, plus a malformed built-in location. These
  must never be silently treated as the same case.
- Two formal destinations associated with one passage and one formal
  destination associated with several different passages.
- A custom image or database locator that another consumer does not understand.
  The consumer can preserve the object without pretending to render it.
- A document using relative references moved with its resource bundle, and one
  moved alone. A consumer needs the document's base to resolve references.
- Extension data with nesting, Unicode, false values, zero, and null. Loading
  and writing must preserve their JSON values rather than dropping them as
  empty metadata.
- A source or formal destination changed since annotation. Structural
  validation must not be presented as proof that an anchor is still correct.
- A legacy annotation with no destination URL and one with several candidate
  destinations. Migration needs explicit diagnostics instead of guessed URLs.
- Legacy verdicts, provenance, roles, and dependency records with no core
  counterpart. Migration must report omissions or preserve that data in a
  clearly documented extension, rather than silently declaring the conversion
  lossless.

## Boundaries for later work

Add another built-in mode only after several applications need the same
location semantics. Markdown and wikitext can start in generic mode. Standard
extension conventions for declaration identity, revision pinning, confidence,
accessible text, or provenance can be useful without becoming mandatory core
fields. A storage schema, renderer, search service, or proof workflow should
remain free to evolve independently of a document that expresses one link.
