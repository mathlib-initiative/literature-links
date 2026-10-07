# Contributing

- Open an issue before changing the format (a key, value or rule).
- A format change updates, in one pull request: `docs/companion.md`, `schema/companion.schema.json`, the checker in `src/formal_companion_annotations/companion.py`, a test or example, and `CHANGELOG.md`.
- A name leaves `__all__` only in a major release. Keep public callables annotated.
- Examples are synthetic: no text from a real book anywhere in this repository.
- `python3 -m pytest` must pass offline. Install `jsonschema` to run the agreement tests.
- Release: set the version in `pyproject.toml` and `src/formal_companion_annotations/__init__.py`, date its `CHANGELOG.md` heading, and tag `vX.Y.Z`.
