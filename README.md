# Formal Companion Annotations

A small JSON format for connecting informal mathematics to formal mathematics.
**One annotation describes one link.** Collecting those annotations makes a
companion to a book, article, wiki, or other source.

```json
{
  "source": { "type": "latex", "uri": "../chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": "https://example.org/formal/Groups.html#lagrange"
}
```

This illustrative annotation connects a LaTeX passage to a formal result.
Only `source` and `target` are required. Omit `location` to refer to the whole
source; use separate annotations for multiple passages or formal destinations.

**Status:** unreleased working draft. The annotation has no version field.
The Python package has its own development version. The design is available for
review; the validation and interpretation boundaries are described below.

## Source formats

| Source type | Ways to select part of the source |
|---|---|
| `pdf` | A physical page, optionally with a rectangular region |
| `latex` | A label or an inclusive line range |
| `html` | An element ID, CSS selector, or quotation |
| `generic` | An application-defined JSON object |

Generic mode supports Markdown, wikitext, images, databases, and custom formats.
Optional `extensions` hold application metadata. There is no required manifest,
ID scheme, provenance registry, proof workflow, or directory layout.

The format is inspired by the
[W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/), but is
not its JSON-LD serialization. Here, `source` means the informal resource and
`target` means the formal resource. See the [specification](docs/companion.md)
for the exact semantics.

## Try it locally

Python 3.11 or newer is required for the included tools. The schema itself can
be used independently of Python. The package has no runtime dependencies.

From a checkout of this repository:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
formal-companion-annotations validate examples/companion/latex.json
formal-companion-annotations scan examples/companion
```

On Windows, activate the environment with `.venv\Scripts\activate` instead.

Store one annotation per JSON file, group records into JSON arrays, or use
JSONL/NDJSON. The included reader traverses the directories you select and
validates every record. These are reader conventions, not additional schemas.

```sh
formal-companion-annotations scan path/to/repository --include '*.annotations.json'
formal-companion-annotations validate annotation.json --format json
```

Relative references use the containing annotation file as their base. Keep that
base when moving records. The reader preserves duplicates and reports malformed
selected files. See [discovery](docs/companion.md#discovery) for selection rules.

## What validation means

The [JSON Schema](schema/companion.schema.json) checks the structure of **one
annotation**. The reference checker also checks rectangle bounds and line-range
ordering. Neither checks that a resource exists, a passage can be located, or
the mathematics agrees. An unknown location remains unresolved.

An association can be useful before a proof is complete. Review status, source
revisions, confidence, and proof completion belong to the applications that
produce and display annotations; they are not implied by a valid record.

## Read more

| Guide | Purpose |
|---|---|
| [Examples](examples/companion/) | See each source mode |
| [Specification](docs/companion.md) | Fields, locations, references, and validation rules |
| [Contributing](CONTRIBUTING.md) | Development setup and review expectations |

Licensed under [Apache 2.0](LICENSE). See the [changelog](CHANGELOG.md) for
development history.
