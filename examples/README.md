# Examples

Start with the [local tutorial](tutorial/README.md). It includes an informal HTML
page, an illustrative formal page, and the single annotation between them. Both
endpoints can be inspected without a network connection.

## Syntax examples

The nine files in [`companion/`](companion/) illustrate valid annotation shapes.
They are **synthetic examples**, not verified mathematical correspondences.
`example.org` URLs, `urn:example:` identifiers, relative paths, and profile names
are illustrative. The referenced resources are not supplied in this directory,
and the checker does not download them or confirm that their anchors exist.

| File | What it demonstrates |
|---|---|
| [generic.json](companion/generic.json) | Minimal record: a whole generic resource and one formal destination. |
| [pdf.json](companion/pdf.json) | A physical PDF page. |
| [latex.json](companion/latex.json) | A literal LaTeX label. |
| [html.json](companion/html.json) | An HTML element ID. |
| [pdf-region-first.json](companion/pdf-region-first.json) | A PDF rectangle associated with one formal destination. |
| [pdf-region-second.json](companion/pdf-region-second.json) | The same rectangle associated with a second destination, in a separate record. |
| [generic-markdown.json](companion/generic-markdown.json) | An application-defined Markdown block location and optional workflow metadata. |
| [generic-image.json](companion/generic-image.json) | An application-defined image region and descriptive metadata. |
| [generic-database.json](companion/generic-database.json) | An application-defined database record and column. |

The two PDF-region records share a grouping label in an extension. Neither that
label nor the repeated source fields create a collection wrapper. The generic
profiles and extension keys demonstrate how an application can add its own
meaning; none is a required or registered FCA vocabulary. In particular, a
workflow status is metadata, not evidence that a formal proof is complete.

After [installing the package](../README.md), run from this checkout:

```sh
formal-companion-annotations scan examples/companion/
formal-companion-annotations validate examples/companion/generic-markdown.json
```

The scan should report `9 annotations from 9 shards; 0 problems`. To inspect each
record's carrier context, add `--format json`. Save that report outside the shard
directory, since it is operational output, not another annotation.

See the [annotation reference](../docs/companion.md) for every location form,
including LaTeX line ranges and HTML CSS/quote selectors, and
[discovery](../docs/discovery.md) for array and JSONL carriers. The tutorial is
separate from `companion/` so its source documents are easy to distinguish from
the syntax-only examples.
