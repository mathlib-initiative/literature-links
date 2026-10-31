# Literature Links

[![tests](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml/badge.svg)](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

A small JSON format that records correspondences between mathematical documents,
such as a book passage and a Lean declaration.

Each record is an *annotation*. It names a passage of informal text like a page in a book, article,
wiki or LaTeX label, and its formal counterpart, such as a declaration in
[Mathlib](https://github.com/leanprover-community/mathlib4). The annotations about one source make a
*companion* to it. This format is for people to create these links, by hand or with AI, and for downstream projects to consume them. This repository holds [its specification](docs/companion.md) and [an offline checker](docs/tools.md).

## Try it

The checker needs Python 3.11 or newer and no other package.

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

## Minimal example

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

`subject` is the theorem labeled `thm:lagrange` in a LaTeX file, and `object` is
a declaration in Mathlib at one commit. `exactMatch` says that Mathlib states
the passage's theorem, up to [junk values](docs/companion.md#relation).

## How it differs from what exists

| Mechanism | Where the link is written | What it names on the informal side |
|---|---|---|
| Mathlib's [cross-reference attributes](https://github.com/leanprover-community/mathlib4/blob/db584cd6d46c92f209a44c0f1c829460d327499d/Mathlib/Tactic/CrossRefAttribute.lean), such as `@[stacks]` and `@[wikidata]` | On the declaration, inside Mathlib | An entry in an external database, such as the Stacks Project or Wikidata |
| Mathlib's [1000.yaml](https://github.com/leanprover-community/mathlib4/blob/db584cd6d46c92f209a44c0f1c829460d327499d/docs/1000.yaml) | In a file inside Mathlib | A theorem on the 1000+ theorems list, by its Wikidata ID |
| A [blueprint](https://github.com/PatrickMassot/leanblueprint)'s `\lean{}` | In LaTeX that the project writes | The surrounding LaTeX environment |
| A Literature Links annotation | In JSON files kept outside the source | A passage, by where it sits in the source |

An annotation is kept outside the source and records where in that source the
passage is, so the source can be one the project does not control. An attribute
is written on its declaration and moves with it. An annotation names a
declaration at a commit, and the checker never opens that commit, so keeping
annotations current falls to whoever writes them.

## Concepts at a glance

An annotation relates two sides, each a list of ends. In
[`examples/companion/page-split.json`](examples/companion/page-split.json), a
definition runs over a page break:

```text
subject: two ends, taken jointly              object: one end
  pdf, page 4 --+
                +-- relation: exactMatch -->  lean, Subgroup.index at a commit
  pdf, page 5 --+
```

| Concept | Meaning |
|---|---|
| `subject`, `object` | The two sides, both required: usually the passage and its formal counterpart. The ends on one side are taken jointly, as in the diagram |
| End | A document, named by a `type` and a `uri`, which may be relative to the file that holds the annotation; a `lean` end's `uri` is the project. A `location` selects part of the document; without one, the end is the whole document |
| [`version`, `sha256`, `citation`](docs/companion.md#ends) | Optional: `version` names the revision of a document, such as a Git commit, a Wikipedia `oldid` or an arXiv version; `sha256` hashes the file, and `citation` describes the work as a CSL-JSON item. A tool that finds another revision at `uri` resolves the `location` in the revision the end names or reports it unresolved, never in what `uri` serves now |
| [`relation`](docs/companion.md#relation) | How the sides relate. The recommended values are the five [SKOS mapping relations](https://www.w3.org/TR/skos-reference/#mapping), `exactMatch`, `closeMatch`, `broadMatch`, `narrowMatch` and `relatedMatch`, with `hasPart` and `noMatch`. Without a `relation`, an annotation claims only that its sides correspond |
| Empty `object`, `noMatch` | An empty `object` records a passage that nobody has linked, while `noMatch` over a project at a commit records that someone searched the project and found no counterpart |
| `status`, `kind` | Optional: how far the subject is formalized, and what it is |
| [Folder defaults](docs/companion.md#folder-defaults) | A `_defaults.json` file holds the fields shared by every annotation in its folder and the folders below it, such as the document that each subject end is in |

What a `location` selects depends on the end's `type`:

| `type` | `location` selects |
|---|---|
| `pdf` | A page, optionally with a rectangle or a quotation |
| `latex` | A label, or lines: the item that starts on a line, or an inclusive range |
| `html` | An element ID, a CSS selector or a quotation |
| `lean` | A declaration or a module; `lines`, which need the `module`, narrow either |
| `generic` | Any JSON object the application defines |
| Any, with a `profile` field | What the convention that `profile` names defines; use it when no form above fits |

Validation checks structure, PDF rectangles and line order. It does not resolve
locations, fetch resources or check mathematics, so a valid annotation records
its producer's claim, nothing more: it does not show that the relation holds,
that anyone reviewed it, or that its ends exist.

## Install and use

The package is not on PyPI. Install it from a clone, as in [Try it](#try-it), or
at a release tag, such as v2.0.0. With a virtual environment active, as in Try
it, that is
`python -m pip install "git+https://github.com/mathlib-initiative/literature-links@v2.0.0"`.
Installing fetches setuptools to build it. The checker itself uses only the
standard library and runs offline.

`literature-links validate FILE...` checks the files it is given, and
`literature-links scan PATH...` also walks folders. A `.json` file holds one
annotation, and a `.jsonl` or `.ndjson` file one per line. Below a folder,
`scan` skips symlinks and reads every other such file, hidden folders such as
`.lake` included, so point it at the annotation folder, not a project root.

Both commands apply folder defaults and exit 0 only when they find no problem,
so either can gate a CI job. The `literature_links` Python package offers the
same checks. [`docs/tools.md`](docs/tools.md) documents it, the options and the
exit statuses.

## Status

| Part | State |
|---|---|
| Specification, JSON Schema, examples and checker | Released, in the 2.x series |
| A reader that fetches annotations over the web | Not built: the specification has the rules for one, and the checker reads local files |
| Tools that write annotations, viewers and the companions built from annotations | Not here: this repository holds only the format and its checker |

## Documentation

| Path | Contents |
|---|---|
| [`docs/companion.md`](docs/companion.md) | The specification |
| [`docs/tools.md`](docs/tools.md) | The checker, its Python API and the command line, with its options and exit statuses |
| [`schema/companion.schema.json`](schema/companion.schema.json) | The JSON Schema |
| [`examples/companion/`](examples/companion/) | Valid examples of each location form and field |
| [`src/literature_links/`](src/literature_links/) | The checker's source |
| [`CHANGELOG.md`](CHANGELOG.md) | The changes in each release |

## Versioning and compatibility

| Area | What holds |
|---|---|
| Annotations | The format is versioned by release, and no field in an annotation names the format's version; an end's `version` names its document's revision. Annotations valid under 2.x stay valid in later 2.x; a breaking change bumps the major version |
| Python API | Only a major release may remove a name from `__all__` |
| JSON Schema | Its `$id` names the release tag, `vX.Y.Z` |
| Platforms | CI runs the test suite on Linux with Python 3.11 through 3.14, and the command-line, discovery and folder defaults tests on macOS and Windows with Python 3.14 |

## Contributing

Open an issue before changing the format: a field, a value or a rule.
[`CONTRIBUTING.md`](CONTRIBUTING.md) has the rules for changes and for releases.

## License

Licensed under [Apache 2.0](LICENSE).
