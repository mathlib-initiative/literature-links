# Literature Links

A small JSON format that links informal mathematics to formal mathematics. One
annotation is one link. A set of annotations makes a companion to a book,
article, wiki or other source.

This repository holds the format and its offline checker, nothing else. Viewers,
overlays and the companions built from annotations live in their own repositories.

```json
{
  "source": { "type": "latex", "uri": "chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": "https://example.org/formal/Groups.html#lagrange"
}
```

Only `source` is required. Without `location`, the annotation links the whole
source; without `target`, it records a passage with no formal counterpart. A
typed `pin` on either end cites the resource outside the companion, like a
bibliography entry. Optional `status`, `kind`, `label` and `note` describe the
link, and `id` and `extensions` hold application data. Records valid under 1.x
stay valid in later 1.x; a breaking change bumps the major version.

| `source.type` | `location` selects |
|---|---|
| `pdf` | A page, optionally with a rectangle |
| `latex` | A label or an inclusive line range |
| `html` | An element ID, a CSS selector or a quotation |
| `generic` | Any JSON object the application defines |

Relative references resolve against the file that holds the annotation.
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
and reads JSON files, JSON arrays and JSONL files. Add `--format json` for
machine-readable output. Both exit 0 when everything is valid, 1 for invalid
annotations and 2 for errors such as unreadable files.

```python
from literature_links import companion, discovery
problems = companion.validate({"source": {"type": "generic", "uri": "a"}, "target": "b"})
collection = discovery.collect(["examples/companion"])  # check .problems before .records
```

See the [specification](docs/companion.md), the
[JSON Schema](schema/companion.schema.json) and the
[examples](examples/companion/). [CONTRIBUTING.md](CONTRIBUTING.md) has the rules
for changes. Licensed under [Apache 2.0](LICENSE).
