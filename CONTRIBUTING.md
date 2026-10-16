# Contributing

- Open an issue before changing the format: a field, a value or a rule.
- A format change updates, in one pull request, `docs/companion.md`, `schema/companion.schema.json`, the checker in `src/literature_links/companion.py`, a test or example, and `CHANGELOG.md`.
- A change to the checker, its Python API or the command line updates `docs/tools.md`.
- Only a major release may make a valid annotation invalid or remove a name from `__all__`.
- Keep public callables annotated.
- Examples may cite real resources, such as Mathlib declarations. No text from a real book may appear in this repository.
- `python3 -m pytest` must pass offline. Install `jsonschema` to run the agreement tests.
- Changes since the last release go under `## Unreleased` at the top of `CHANGELOG.md`.

## Release

To release version X.Y.Z, change three things in one commit:

1. Set `__version__` in `src/literature_links/__init__.py` to `X.Y.Z`.
2. Give the release its dated `CHANGELOG.md` heading, `## X.Y.Z (YYYY-MM-DD)`, in place of `## Unreleased` or of `(unreleased)` after the version.
3. Point the `$id` of `schema/companion.schema.json` at the release tag: `https://raw.githubusercontent.com/mathlib-initiative/literature-links/vX.Y.Z/schema/companion.schema.json`.

`tests/test_packaging.py` checks that the version, the heading and `$id` agree. Tag that commit `vX.Y.Z`.
