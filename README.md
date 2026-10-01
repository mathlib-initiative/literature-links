# formal-companion-annotations

The formal-companion annotation format: one JSON document per Lean companion
saying which Lean declarations formalise which items of which sources, and
where those items sit in the sources. This repository holds its JSON Schema
([`schema/annotations-v1.schema.json`](schema/annotations-v1.schema.json)),
its specification ([`docs/annotations.md`](docs/annotations.md)), its
vocabulary ([`docs/vocabulary.md`](docs/vocabulary.md)), synthetic
[`examples/annotations/`](examples/annotations/), and the Python package
`formal_companion_annotations` (checker, id rules), standard library only,
Python 3.11+. The root `schema` value stays `"lean-companion/annotations"`
(spec section 5.1 and the intro say why).

## Install

The repository is private; installing needs read access.

```sh
python3 -m pip install "formal-companion-annotations @ git+https://github.com/mathlib-initiative/formal-companion-annotations@v1.0.0"
python3 -m pip install .        # from a checkout
```

## Validate

```sh
formal-companion-annotations-validate doc.json                # or: python3 -m formal_companion_annotations
formal-companion-annotations-validate doc.json --canonical    # also require canonical bytes
formal-companion-annotations-validate doc.json --print-canonical > fixed.json
```

Exit status: 0 valid, 1 invalid, 2 unreadable, a usage error or a broken
install. `--print-canonical` does not validate first: validate before using it.

```python
from formal_companion_annotations import validate
report = validate.check(validate.loads(text), text=text, canonical=True)
```

The stable Python API is each module's `__all__`.

## Versions

- MAJOR is the format's major: package 1.x reads `schema_version` `"1.*"` only.
- MINOR adds only (optional keys, enum values, public names); PATCH changes no admitted document.
- The checker picks the schema by the major alone, so writers must declare the minor they wrote against.

Details: spec section 9; releases: [`CHANGELOG.md`](CHANGELOG.md).

## Tests

```sh
python3 -m pytest
```

## License

Apache License 2.0 ([`LICENSE`](LICENSE)).
