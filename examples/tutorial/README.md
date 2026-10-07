# A single link, with both endpoints

This tutorial connects a short informal statement to a page displaying a Lean
example. All three files are included, so you can inspect the link locally:

| File | Role |
|---|---|
| [informal.html](informal.html) | The informal source: “Every natural number equals itself.” |
| [formal.html](formal.html) | An illustrative formal destination displaying `example (n : Nat) : n = n := rfl`. |
| [annotation.json](annotation.json) | One FCA record associating the two passages. |

These pages were written for this tutorial. The formal page is a synthetic
documentation fixture, not generated Mathlib documentation or a report of a Lean
build. You do not need Lean, a running viewer, or a network connection to inspect
the files or validate the annotation after installing the package.

## Read the annotation

```json
{
  "source": {
    "type": "html",
    "uri": "informal.html"
  },
  "location": {
    "fragment": "reflexivity"
  },
  "target": "formal.html#reflexivity"
}
```

`source.uri` identifies the informal document; `location.fragment` selects the
element whose ID is `reflexivity`. The formal destination is one reference,
including its own fragment. Open each HTML file in a browser to inspect these
passages. The pages link to each other for convenience; they contain no FCA
viewer or executable selector logic.

Neither page is the annotation. They remain independent resources. The
annotation has no ID, version, collection header, or extensions because this
example does not need them. Removing `location` would associate the **whole
informal page** with the same formal destination. Replacing it with `{}` would
be invalid for HTML.

## Validate and discover

Follow the repository's [installation instructions](../../README.md), then run
these commands from the repository root in that Python environment:

```sh
formal-companion-annotations validate examples/tutorial/annotation.json
formal-companion-annotations scan examples/tutorial/ --format json
```

Validation should report `ok (1 annotation, html)`. The scan should contain one
record, `valid: true`, no problems, an empty origin pointer, a `null` line, and
the file URI of `annotation.json` as `origin.base_uri`. The HTML and Markdown
files are not selected by the reader's default suffix filter.

A successful check establishes structure and local invariants. It does not load
the pages, resolve the element IDs, compile the Lean example, or verify the
association. In this tutorial you can inspect the two included passages yourself.

## Keep the carrier context

Both references resolve relative to **annotation.json**, not the current working
directory or the informal page. To inspect their resolved references without
fetching anything, run from the repository root:

```python
from pathlib import Path
from urllib.parse import urljoin
from formal_companion_annotations import companion

carrier = Path("examples/tutorial/annotation.json").resolve()
annotation = companion.loads(carrier.read_text(encoding="utf-8"))
assert not companion.check(annotation).problems
base = carrier.as_uri()
print(urljoin(base, annotation["source"]["uri"]))
print(urljoin(base, annotation["target"]))
```

The results end in `/examples/tutorial/informal.html` and
`/examples/tutorial/formal.html#reflexivity`. Moving the entire tutorial folder
preserves this relationship. Moving only the annotation into a different folder
does not: retain its original carrier base in application metadata, or deliberately
rebase its relative references.

For another formal destination, create a second complete record. For many links,
choose any directory layout and use the [shard reader](../../docs/discovery.md).
For PDF, LaTeX, and application-defined inputs, see the
[annotation reference](../../docs/companion.md) and the
[syntax examples](../README.md).
