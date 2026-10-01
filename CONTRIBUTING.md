# Contributing

- Open an issue before changing the format (a key, value, rule, invariant, canonical form or id rule).
- A format change updates, in one pull request: `docs/annotations.md`, `docs/vocabulary.md` for a value, both schema copies, `src/formal_companion_annotations/vocab.py` for an enum, the checker, a test or example, and `CHANGELOG.md` under "Unreleased".
- Minor or major: spec section 9. A name leaves `__all__` only in a major release; keep public callables annotated.
- The two schema copies are byte-identical: `cp schema/annotations-v1.schema.json src/formal_companion_annotations/schema/`.
- Examples are synthetic: no text from a real book anywhere in this repository. An `invalid-*` example records its expected error in `x_expected_error`. Keep examples canonical.
- `python3 -m pytest` must pass (install `jsonschema` to run the agreement tests).
- Release: move "Unreleased" under the version, set it in `pyproject.toml` and `src/formal_companion_annotations/__init__.py`, set the schema `$id` to the new tag for a new format minor, and tag `vX.Y.Z`.
