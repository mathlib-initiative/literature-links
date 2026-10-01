# formal-companion-annotations

**One JSON file per Lean companion that says which Lean declarations formalise
which items of which sources, and where those items sit in the sources.**

A *Lean companion* is a Lean 4 repository that formalises a book, lecture
notes or a paper. This repository maintains the annotation format that such
a companion publishes, so that a PDF overlay, a rendered site, an audit or a
dataset builder can join the source and the Lean without knowing either
repository's conventions. It holds:

- the JSON Schema, [`schema/annotations-v1.0.schema.json`](schema/annotations-v1.0.schema.json),
  whose descriptions say what every field and value means;
- the specification, [`docs/annotations.md`](docs/annotations.md): the rules
  no schema can state (the invariants, the id rules, the canonical form,
  versions);
- the checker, the Python package `formal_companion_annotations` (standard
  library only, Python 3.11+);
- a few synthetic examples in [`examples/annotations/`](examples/annotations/).

**Release candidate `1.0.0rc3`.** The format's version is `1.0`.

## A complete document

The smallest useful document: one source, one item, one declaration, one
link, one provenance record. It is [`examples/annotations/minimal.json`](examples/annotations/minimal.json).

```json
{
  "companion": {
    "commit": "ed00b5dc6b11040ed2f9baf475edc9b48e1c7f4a",
    "generated_at": "2026-09-26T12:00:00Z",
    "generator": "hand",
    "name": "notes-companion",
    "repo": "git.example.org/example/notes-companion"
  },
  "declarations": [
    {
      "anonymous": false,
      "file": "Notes/Basic.lean",
      "id": "Notes.Box.volume_nonneg",
      "id_source": "name",
      "kind": "theorem",
      "line": 41,
      "module": "Notes.Basic",
      "name": "Notes.Box.volume_nonneg",
      "private": false
    }
  ],
  "items": [
    {
      "form": "numbered",
      "id": "lemma-1.2",
      "id_source": "label",
      "kind": "Lemma",
      "number": "1.2",
      "pages": {
        "basis": "printed",
        "first": 5
      },
      "source": "notes-pdf"
    }
  ],
  "links": [
    {
      "declaration": "Notes.Box.volume_nonneg",
      "id": "lemma-1.2/key/Notes.Box.volume_nonneg",
      "item": "lemma-1.2",
      "provenance": "prov-curation",
      "role": "key"
    }
  ],
  "provenance": [
    {
      "actor": "human",
      "confirmed_by_human": true,
      "id": "prov-curation",
      "method": "curation"
    }
  ],
  "schema": "formal-companion/annotations",
  "schema_version": "1.0",
  "sources": [
    {
      "id": "notes-pdf",
      "kind": "pdf",
      "sha256": "e45a0b99dd11778aac792ecd226d150a9d28b82c9e2897510f441235956a3b07",
      "title": "Elementary Sets: Lecture Notes (synthetic)"
    }
  ]
}
```

The source is a PDF pinned by its sha256. The item is its Lemma 1.2, on
printed page 5. The link says the declaration states the whole item (`key`)
and names the provenance record that says who claims so. Four optional
profiles add a companion's dependency graph (`graph`), a rendered site
(`site`), audit verdicts (`audit`) and an id history (`history`).

## Install and validate

```sh
python3 -m pip install --pre formal-companion-annotations
formal-companion-annotations-validate my-companion.annotations.json
formal-companion-annotations-validate my.json --canonical --lint external-urls
formal-companion-annotations-validate my.json --print-canonical > fixed.json
```

The checker evaluates the schema of the minor the document declares, then
the invariants of the specification. `--canonical` also requires the
canonical bytes, `--print-canonical` sorts, validates and writes the
canonical form, `--lint external-urls` adds the opt-in URL lint, and
`--format json` prints one JSON object per document. Each problem is a line
`<file>: <path>: <message> [<code>]`. The exit status is 0 when every
document is valid, 1 when one is invalid, and 2 when one cannot be read.

From Python:

```python
from formal_companion_annotations import validate

data = open("doc.json", "rb").read()
report = validate.check(validate.loads(data), text=data, canonical=True)
for problem in report.problems:                  # Problem(code, path, message)
    print(problem.code, problem)
```

The stable API is each module's `__all__`: `validate` (the checker and the
canonical form), `ids` (the id rules), `vocab` (the enums) and
`schemacheck` (the schema evaluator).

## Layout

```
schema/annotations-v1.0.schema.json   the JSON Schema; the wheel ships it as the package's schema/
docs/annotations.md                   the specification
src/formal_companion_annotations/     the checker: validate, schemacheck, ids, vocab
examples/annotations/                 synthetic documents; invalid-*.json fail on purpose
tests/                                the test suite: python3 -m unittest discover -s tests
```

## Versions

The package follows semantic versioning tied to the format's version, as
section 7 of the specification says. Each release is in
[`CHANGELOG.md`](CHANGELOG.md); how to propose a change is in
[`CONTRIBUTING.md`](CONTRIBUTING.md). Apache License 2.0
([`LICENSE`](LICENSE)), copyright 2026 the formal-companion contributors.
