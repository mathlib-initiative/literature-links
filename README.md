# Literature Links

[![tests](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml/badge.svg)](https://github.com/mathlib-initiative/literature-links/actions/workflows/tests.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)

Literature Links is a JSON format for linking passages in mathematical documents
to counterparts such as Lean declarations. Each annotation records the
`subject` and `object`, including the document and location on each side.

## Example

```json
{
  "subject": [ { "type": "html", "uri": "https://en.wikipedia.org/wiki/Lagrange's_theorem_(group_theory)",
                 "version": "1382438659",
                 "location": { "quote": { "exact": "every subgroup divides the order of the whole group" } } } ],
  "object": [ { "type": "lean", "uri": "https://github.com/leanprover-community/mathlib4",
                "version": "v4.33.0",
                "location": { "declaration": "Subgroup.card_subgroup_dvd_card" } } ],
  "relation": "exactMatch"
}
```

`exactMatch` says that [Mathlib's theorem](https://github.com/leanprover-community/mathlib4/blob/v4.33.0/Mathlib/GroupTheory/Coset/Card.lean#L69)
states the passage quoted from [that revision of the article](https://en.wikipedia.org/w/index.php?oldid=1382438659),
up to [junk values](docs/companion.md#relation).

For a worked example, explore the statements and proof steps in the
[annotated Seifert–van Kampen PDF](https://mathlib-initiative.github.io/seifert-van-kampen-tauceti/)
or browse its [annotation files](https://github.com/mathlib-initiative/seifert-van-kampen-tauceti/tree/main/annotations).

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

`validate` checks the named files. `scan` also walks directories, so point it at
your annotation folder. Both check the format offline. See the
[checker guide](docs/tools.md) for the CLI and Python API.

To install just the checker at a release tag:

```sh
python -m pip install "git+https://github.com/mathlib-initiative/literature-links@v1.0.2"
```

## Documentation

- [Annotation Format Map](https://mathlib-initiative.github.io/literature-links/) and [sample files](examples/companion/)
- [Format specification](docs/companion.md) and [JSON Schema](schema/companion.schema.json)
- [Adopting Literature Links](docs/adopting.md): turning a library's existing references into annotations
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

Within 1.x, valid annotations stay valid and the public Python API keeps its
exported names. The project is licensed under [Apache 2.0](LICENSE).
