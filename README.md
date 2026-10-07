# Formal Companion Annotations

A small JSON format that links informal mathematics to formal mathematics. One
annotation is one link. A set of annotations makes a companion to a book,
article, wiki or other source.

```json
{
  "source": { "type": "latex", "uri": "chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": "https://example.org/formal/Groups.html#lagrange"
}
```

Only `source` and `target` are required. Without `location`, the annotation
links the whole source. Optional `id` and `extensions` hold application data.
The format is an unreleased draft with no version field.

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
formal-companion-annotations validate examples/companion/latex.json
formal-companion-annotations scan examples/companion
```

`validate` checks files that each hold one annotation. `scan` walks directories
and reads JSON files, JSON arrays and JSONL files. Add `--format json` for
machine-readable output. Both exit 0 when everything is valid, 1 for invalid
annotations and 2 for errors such as unreadable files.

```python
from formal_companion_annotations import companion, discovery
problems = companion.validate({"source": {"type": "generic", "uri": "a"}, "target": "b"})
collection = discovery.collect(["examples/companion"])  # check .problems before .records
```

See the [specification](docs/companion.md), the
[JSON Schema](schema/companion.schema.json) and the
[examples](examples/companion/). [CONTRIBUTING.md](CONTRIBUTING.md) has the rules
for changes. Licensed under [Apache 2.0](LICENSE).
