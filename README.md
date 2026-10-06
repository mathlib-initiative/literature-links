# Formal Companion Annotations

**One JSON object describes one informal–formal association.** A companion is
assembled from these independent annotations, wherever its author stores them.

```json
{
  "source": { "type": "latex", "uri": "../chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": "https://example.org/formal/Groups.html#lagrange"
}
```

Only `source` and `target` are required; the unreleased annotation format has
no version field. It needs no companion manifest, declaration index,
generated ID, provenance table, or proof workflow. The association alone does
not assert equivalence, proof completion, or human review.

This private repository contains an **unpublished draft, package 2.0.0a2**.
The software package version is separate from the unversioned annotation data.
The single-record design supersedes the earlier a1 source-plus-annotations
wrapper. PR #2's release-candidate format and published legacy v1 are distinct
formats; see the [comparison and synthesis](docs/design/pr-2-synthesis.md).

## Four source modes

| Source type | Optional location |
|---|---|
| `pdf` | Physical page, optionally a normalized rectangle |
| `latex` | Label or inclusive line range |
| `html` | Element ID, CSS selector, or quotation |
| `generic` | Any application-defined JSON object |

Omit `location` to associate the whole resource. Use two records for two formal
destinations or two informal occurrences. Root `id`, `$schema`, and
`extensions` are optional; the source can also have `extensions`.
Generic mode accommodates images, database records, Markdown, wikitext, and
custom formats without registering a new mode or profile.

Read the [annotation specification](docs/companion.md),
[design rationale](docs/design/minimal-core.md), and
[nine synthetic annotations](examples/companion).

## Build a companion by discovery

The schema validates **one annotation**, never a directory or collection.
A separate reader can traverse any directory layout. The included reader
supports one JSON object per file, JSON arrays of complete annotation objects,
and JSONL/NDJSON with one annotation per nonblank line. These are storage choices,
not extra schema modes. Other applications may choose other carriers.

```sh
python3 -m pip install .
formal-companion-annotations validate examples/companion/*.json
formal-companion-annotations scan examples/companion
formal-companion-annotations scan path/to/repository --include '*.annotations.json' --include '*.jsonl'
formal-companion-annotations scan path/to/shards --format json
```

Python 3.11+; no runtime dependencies. Selected files are checked strictly;
unrelated JSON in a whole repository should be excluded or left outside the
selected roots. The reader does not hunt inside arbitrary nested objects.
There is no required folder name, filename, manifest, chapter structure, or
globally unique ID. It preserves repeated associations and IDs.

Each discovered record retains its file, pointer/line, and URI base. Relative
source and target references resolve against the **containing shard**, not the
scan root. See [discovery and shards](docs/discovery.md).

## Validate, format, and use the API

```sh
formal-companion-annotations validate annotation.json --format json
formal-companion-annotations format annotation.json --output formatted.json
```

Machine-readable validation emits one report per input, with stable diagnostic
codes, paths, and messages. All inputs are processed. Exit 0 means valid, 1
invalid, 2 a reading/usage/installation error; 2 takes precedence over 1.
Formatting preserves decoded data and order; it defines no canonical bytes.
It leaves relative reference strings unchanged, so relocating its output
requires preserving the base or deliberately rewriting references.

```python
from formal_companion_annotations import companion, discovery

annotation = companion.loads(text)
report = companion.check(annotation)
for problem in report.problems:
    print(problem.code, problem.path, problem.message)

collection = discovery.collect(["path/to/annotations"])
if not collection.problems:
    for record in collection.records:
        use(record.annotation, base_uri=record.base_uri)
```

`loads`/`dumps` are strict JSON codecs; `validate` returns a list of problem
strings. No validator fetches resources, resolves selectors, or verifies
mathematics. Unknown extension data and generic locations remain intact.

## Compatibility and scope

Legacy v1 validation, canonicalization, vocabulary, and ID APIs remain available.
`formal-companion-annotations-validate` and `python3 -m formal_companion_annotations`
also accept single annotations. Canonical operations apply only to legacy v1.

[Migration](docs/migration.md) emits one independent annotation per projected
association, a diagnostic report, and the exact original input. Its supported
input is released v1 (`lean-companion/annotations`), **not PR #2's rc3 dialect**.
It does not invent formal URLs. The [PR comparison](docs/design/pr-2-synthesis.md)
explains the explicit adapter still needed for that dialect.

WikiLean's catalog, Autoform's proof graph, and companion viewer indexes remain
application data. This package supplies the annotation contract and discovery;
it does not deploy their exporters or renderers. It borrows resource-selection
ideas from [W3C Web Annotation](https://www.w3.org/TR/annotation-model/) without
claiming W3C/JSON-LD serialization compatibility.

## Development

```sh
python3 -m pip install '.[test,jsonschema]'
python3 -m pytest -q
python3 -m unittest discover -s tests
```

Each schema has one source file in `schema/`; packaging ships it inside the
wheel. Tests cover the core, independent JSON Schema agreement, discovery,
migration, CLI behavior, and installed distributions. See
[contributing](CONTRIBUTING.md), [changelog](CHANGELOG.md), and
[Apache 2.0 license](LICENSE).
