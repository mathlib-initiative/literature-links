# Literature Links

A small JSON format that links informal mathematics to formal declarations, such
as Lean declarations in Mathlib. One annotation is one link. A set of annotations
makes a companion to a book, article, wiki or other source.

Status: 1.0.0. Records valid under 1.x stay valid in later 1.x; a breaking
change bumps the major version.

Used by [formal-companion](https://github.com/mathlib-initiative/formal-companion),
whose PDF overlay reads these annotations.

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
  "source": { "type": "latex", "uri": "chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": {
    "uri": "https://github.com/leanprover-community/mathlib4/blob/db584cd6d46c92f209a44c0f1c829460d327499d/Mathlib/GroupTheory/Coset/Card.lean#L69",
    "pin": {
      "type": "repository",
      "url": "https://github.com/leanprover-community/mathlib4",
      "commit": "db584cd6d46c92f209a44c0f1c829460d327499d",
      "path": "Mathlib/GroupTheory/Coset/Card.lean",
      "line": 69,
      "module": "Mathlib.GroupTheory.Coset.Card",
      "declaration": "Subgroup.card_subgroup_dvd_card"
    }
  }
}
```

Only `source` is required. Without `location`, the annotation links the whole
source; without `target`, it records the passage alone. A typed `pin` on either
end cites the resource outside the companion, like a bibliography entry.
Optional `status`, `kind`, `label` and `note` describe the link, and `id` and
`extensions` hold application data.

| `source.type` | `location` selects |
|---|---|
| `pdf` | A page, optionally with a rectangle |
| `latex` | A label or an inclusive line range |
| `html` | An element ID, a CSS selector or a quotation |
| `generic` | Any JSON object the application defines |

Relative references resolve against the file that holds the annotation. A
`_defaults.json` file gives every annotation in its folder and below the members
they share, such as `source`; see [folder defaults](docs/companion.md#folder-defaults).
Validation checks structure, PDF rectangles and LaTeX line order. It does not
fetch resources or check mathematics.

## Use

The tools need Python 3.11 or newer and nothing else.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
literature-links validate examples/companion/latex.json
literature-links scan examples/companion
```

`validate` checks files that each hold one annotation. `scan` walks directories
and reads `.json` files, one annotation each, and `.jsonl` files, one per line.
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
