# Formal Companion Annotations

A small JSON format connecting informal material to formal resources. The
**v2 working draft** supports **PDF, LaTeX, HTML**, and a flexible **generic**
mode for applications with their own locators.

```json
{
  "version": 2,
  "source": { "type": "latex", "uri": "chapters/groups.tex" },
  "annotations": [
    {
      "location": { "label": "thm:lagrange" },
      "target": "https://example.org/formal/Groups.html#lagrange"
    }
  ]
}
```

That is a complete companion. It needs no declaration inventory, repository
manifest, generated IDs, review ledger, or proof workflow. An association does
not itself assert that a formal result proves the informal statement.

This is an unpublished refactor draft, package `2.0.0a1`. The repository is
private; access is required. The existing v1 format remains supported. This
checkout does not announce a public release or hosted schema.

## Four input modes

One document describes one concrete source resource. Each annotation needs a
formal `target`; omit `location` to associate the whole source. Multiple formal
destinations use multiple annotations.

| Source type | Location examples |
|---|---|
| `pdf` | `{ "page": 3 }`; optionally `"rect": [0.1, 0.2, 0.6, 0.15]` |
| `latex` | `{ "label": "thm:lagrange" }` or `{ "lines": [12, 18] }` |
| `html` | `{ "fragment": "theorem-2" }`, `{ "css": "#theorem-2" }`, or a text `quote` |
| `generic` | Any application-defined JSON object, or omit the location |

Generic input can describe an image region, database record, Markdown block,
wikitext section, or private format. It needs no registry or mandatory profile.
Optional `extensions` objects hold custom metadata on the document, source, and
annotations. Readers preserve unfamiliar extension data.

Read the [specification](docs/companion-v2.md),
[design choices](docs/design/minimal-core.md), and
[eight synthetic examples](examples/companion-v2).
The specification defines coordinates, line ranges, quoting, and URI bases.

## Use locally

Python 3.11 or later; no runtime dependencies. From an authorized local checkout:

```sh
python3 -m pip install .
formal-companion-annotations validate examples/companion-v2/*.json
formal-companion-annotations format examples/companion-v2/latex.json
```

`format` validates v2 and writes readable JSON. It preserves annotation order,
object key order, and decoded extension values; it does not define canonical
bytes. With `--output path.json`, it replaces that explicitly named file only
after successful validation and serialization.
Relative reference strings are unchanged: when writing to another directory,
preserve the document's base or deliberately update those references yourself.

```python
from formal_companion_annotations import companion

document = companion.loads(text)
problems = companion.validate(document)
if not problems:
    formatted = companion.dumps(document)
```

`loads` and `dumps` are strict JSON codecs, not implicit schema validation.
`check` returns `problems` and `warnings`. Validation is offline: it checks shape
and local invariants, not whether links resolve, selectors match, or mathematics
is faithfully formalized. Public APIs are listed in each module's `__all__`;
the new v2 APIs and format remain experimental during this prerelease.

## Existing v1 users

The v1 checker, vocabulary, ID helpers, schema, and examples are retained. Both
validation commands recognize v2 and v1. Existing entry points still work:

```sh
formal-companion-annotations-validate examples/annotations/mixed.json --canonical
python3 -m formal_companion_annotations examples/companion-v2/pdf.json
```

Canonical sorting and `--print-canonical` apply only to v1. The public v1
`canonicalize` / `canonical_dumps` APIs reject v2 to prevent unwanted sorting or
rounding of extension data. Use `companion.loads` / `companion.dumps` for v2.
The v1 `--print-canonical` option does not validate first; validate before use.
Validation exits 0 for valid input, 1 for invalid input, and 2 for usage,
reading, or installation errors.

[Migration](docs/migration-v2.md) is explicit. Its command creates a new directory
with projected companions, a diagnostic report, and a byte-for-byte archive of
the v1 input. It never guesses formal URLs from declaration names. Some inputs
legitimately produce no companions. The [v1 specification](docs/annotations.md)
and [vocabulary](docs/vocabulary.md) remain the reference for legacy documents.

## Interoperability boundary

WikiLean can retain its catalog and matching evidence in its database and export
small associations. Autoform can retain its roadmap and proof graph while
exchanging blueprint locations through generic mode. Viewers can support the
built-in modes and their own generic adapters. These are design boundaries;
this refactor does not install adapters or renderers in those applications.

The format borrows resource-selection ideas from the
[W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/).
It is a standalone JSON format, not a W3C or JSON-LD serialization.

## Development

```sh
python3 -m pip install '.[test,jsonschema]'
python3 -m pytest -q
python3 -m unittest discover -s tests
```

Tests compare the standard-library checker with `jsonschema` when available,
and cover semantic constraints, extension preservation, legacy compatibility,
migration, CLI behavior, and packaging. Both schema files ship in the package;
copies in `schema/` must match. See [contributing](CONTRIBUTING.md) and the
[changelog](CHANGELOG.md). Licensed under [Apache 2.0](LICENSE).
