# Literature Links

A small JSON format that links informal mathematics to formal mathematics, such
as a passage of a book to a Lean declaration in Mathlib. One annotation relates
a subject, usually the passage, to an object, usually its formal counterpart.
The annotations about one book, article, wiki or other source make a companion
to it: a guide from the text to its formalization.

Status: 2.0.0. Records valid under 2.x stay valid in later 2.x; a breaking
change bumps the major version.

This repository holds the format and its offline checker, nothing else. Viewers,
overlays and the companions built from annotations live in their own repositories.

Mathlib's `@[stacks]` and `@[wikidata]` attributes and its
[1000.yaml](https://github.com/leanprover-community/mathlib4/blob/db584cd6d46c92f209a44c0f1c829460d327499d/docs/1000.yaml)
link a declaration to a reference from inside Mathlib, and a blueprint's
`\lean{}` links from LaTeX the project writes. An annotation is kept outside the
source and records where in that source the passage is, so the source can be one
the project does not control.

```json
{
  "subject": [ { "type": "latex", "uri": "chapters/groups.tex", "location": { "label": "thm:lagrange" } } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "db584cd6d46c92f209a44c0f1c829460d327499d",
                "location": { "declaration": "Subgroup.card_subgroup_dvd_card",
                              "module": "Mathlib.GroupTheory.Coset.Card" } } ],
  "relation": "broadMatch"
}
```

`subject` and `object` are lists of ends, and both are required. An end names
a document with a `type` and a `uri`, and its `location` selects part of it;
without one, the end is the whole document. An empty `object` records a passage
that nobody has linked. `relation` says how the sides relate. Here
`broadMatch` says that Mathlib's statement is more general than the passage,
which is about finite groups. Without a `relation`, a record claims only that
its sides correspond. Optional `status`, `kind`, `id` and `note` describe the
record, and an end may carry a `version`, a `sha256`, a CSL-JSON `citation`,
`identifiers`, a `title` and a `role`. `extensions` holds application data.

| `type` | `location` selects |
|---|---|
| `pdf` | A page, optionally with a rectangle or a quotation |
| `latex` | A label, a line or an inclusive line range |
| `html` | An element ID, a CSS selector or a quotation |
| `lean` | A declaration or a module, optionally narrowed to lines |
| `generic` | Any JSON object the application defines |

Relative references resolve against the file that holds the annotation. A
`_defaults.json` file gives every annotation in its folder and below the members
they share, such as the document that each subject end is in; see
[folder defaults](docs/companion.md#folder-defaults). An annotation records its
producer's claim, nothing more: it does not show that the relation holds, that
anyone reviewed it, or that its ends exist. Validation checks structure, PDF
rectangles and line order. It does not fetch resources or check mathematics.

## Use

The tools need Python 3.11 or newer and nothing else.

```sh
git clone https://github.com/mathlib-initiative/literature-links
cd literature-links
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
literature-links validate examples/companion/latex.json
literature-links scan examples/companion
```

A `.json` file holds one annotation, and a `.jsonl` file one per line.
`validate` checks the files it is given, and `scan` also walks directories.
Point `scan` at the annotation folder, not a project root: it reads every JSON
file below, hidden folders such as `.lake` included.
[`docs/tools.md`](docs/tools.md) documents both commands, their exit codes and
the Python API.

## Repository

- [`docs/companion.md`](docs/companion.md): the specification.
- [`docs/tools.md`](docs/tools.md): the checker, its Python API and the command line.
- [`schema/companion.schema.json`](schema/companion.schema.json): the JSON Schema.
- [`examples/companion/`](examples/companion/): valid examples.
- [`src/literature_links/`](src/literature_links/): the checker. `companion`
  checks one annotation, `discovery` reads files and applies folder defaults,
  and `cli` runs `validate` and `scan`.

[CONTRIBUTING.md](CONTRIBUTING.md) has the rules for changes. Licensed under
[Apache 2.0](LICENSE).
