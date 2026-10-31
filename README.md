# Literature Links

[![tests](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml/badge.svg)](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

A small JSON format that records correspondences between mathematical documents,
such as a book passage and a Lean declaration.

Each record is an *annotation*. It names a passage of informal text like a page in a book, article,
wiki or LaTeX label, and its formal counterpart, such as a declaration in
[Mathlib](https://github.com/leanprover-community/mathlib4). The annotations about one source make a
*companion* to it. This format is for people to create these links, by hand or with AI, and for downstream projects to consume them. This repository holds [its specification](docs/companion.md) and [an offline checker](docs/tools.md),
and the [Annotation Format Map](https://mathlib-initiative.github.io/literature-links/)
shows every field on one page.

## Try it

The checker needs Python 3.11 or newer.

```sh
git clone https://github.com/mathlib-initiative/literature-links &&
cd literature-links &&
python3 -m venv .venv &&
. .venv/bin/activate &&
python -m pip install . &&
literature-links validate examples/companion/latex.json &&
literature-links scan examples/companion/folder-defaults
```

After pip's output, the last two commands print:

```text
examples/companion/latex.json: ok (1 annotation, latex, lean)
3 annotations from 3 files; 0 problems
```

## Example

```json
{
  "subject": [ { "type": "latex", "uri": "chapters/groups.tex",
                 "location": { "label": "thm:lagrange" } } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d",
                "location": { "declaration": "Subgroup.card_subgroup_dvd_card" } } ],
  "relation": "exactMatch"
}
```

`exactMatch` says that Mathlib states the theorem labeled `thm:lagrange`, up to
[junk values](docs/companion.md#relation).

## Concepts

| Concept | Meaning |
|---|---|
| `subject`, `object` | The two sides, both required: the passage and its formal counterpart. Each is a list of ends, taken jointly, as when [a definition runs over a page break](examples/companion/page-split.json) |
| End | A document, named by a `type` and a `uri`. A `location` selects part of it, such as a page of a PDF, a label in LaTeX, an element in HTML or a declaration in Lean |
| [`relation`](docs/companion.md#relation) | Optional: how the sides relate. The recommended values are `exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch`, `relatedMatch`, `hasPart` and `noMatch` |
| Empty `object`, `noMatch` | An empty `object` records a passage nobody has linked. `noMatch` records that someone searched a project and found no counterpart |
| [`version`, `sha256`, `citation`](docs/companion.md#ends) | Optional: the document's revision, such as a Git commit; a hash of the file; and a description of the work |
| `status`, `kind` | Optional: how far the subject is formalized, and what it is |
| [Folder defaults](docs/companion.md#folder-defaults) | A `_defaults.json` file holds the fields shared by every annotation in its folder and the folders below it |

Validation checks structure, PDF rectangles and line order. It does not resolve
locations, fetch resources or check mathematics.

## Install and use

The package is not on PyPI. Install it from a clone, as in [Try it](#try-it), or
at a release tag:

```sh
python -m pip install "git+https://github.com/mathlib-initiative/literature-links@v2.0.0"
```

`literature-links validate FILE...` checks the files it is given, and
`literature-links scan PATH...` also walks folders. A `.json` file holds one
annotation, and a `.jsonl` or `.ndjson` file one per line. `scan` skips symlinks
and reads every other such file below a folder, `.lake` included, so point it at
the annotation folder, not a project root.

Both commands exit 0 only when they find no problem, so either can gate a CI job.
[`docs/tools.md`](docs/tools.md) documents the options, the exit statuses and the
Python API.

## Documentation

| Path | Contents |
|---|---|
| [`docs/companion.md`](docs/companion.md) | The specification |
| [`docs/tools.md`](docs/tools.md) | The checker, its Python API and the command line |
| [`schema/companion.schema.json`](schema/companion.schema.json) | The JSON Schema |
| [`examples/companion/`](examples/companion/) | Valid examples of each location form and field |
| [`site/`](site/) | The source of the [Annotation Format Map](https://mathlib-initiative.github.io/literature-links/) |
| [`CHANGELOG.md`](CHANGELOG.md) | The changes in each release |

## Versioning

Annotations valid under 2.x stay valid in later 2.x, and only a major release may
remove a name from the Python API's `__all__`.

## Contributing

Open an issue before changing the format: a field, a value or a rule.
[`CONTRIBUTING.md`](CONTRIBUTING.md) has the rules for changes and for releases.

## License

Licensed under [Apache 2.0](LICENSE).
