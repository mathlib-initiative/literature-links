# Contributing

- Open an issue before changing the format (a field, value or rule).
- A format change updates, in one pull request: `docs/companion.md`, `schema/companion.schema.json`, the checker in `src/literature_links/companion.py`, a test or example, and `CHANGELOG.md`.
- A change to the checker, its Python API or the command line updates `docs/tools.md`.
- A change that makes a valid annotation invalid waits for a major release.
- A name leaves `__all__` only in a major release. Keep public callables annotated.
- Examples may cite real resources, such as Mathlib declarations. No text from a real book may appear in this repository.
- `python3 -m pytest` must pass offline. Install `jsonschema` to run the agreement tests.
- Release: set `__version__` in `src/literature_links/__init__.py`, point the schema's `$id` at the tag, date the `CHANGELOG.md` heading, and tag `vX.Y.Z`.
