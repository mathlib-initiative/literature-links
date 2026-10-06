# Contributing

- Open an issue before changing the format (a key, value, rule, invariant, canonical form or id rule).
- Current annotation format changes update `docs/companion.md`, `schema/companion.schema.json`, `src/formal_companion_annotations/companion.py`, relevant tests/examples, and `CHANGELOG.md` together. Explain tradeoffs in `docs/design/minimal-core.md` when useful. The schema describes exactly one link; packing and discovery belong outside it.
- V1 changes still update `docs/annotations.md`, `docs/vocabulary.md` for values, the v1 schema, `src/formal_companion_annotations/vocab.py` for enums, the legacy checker, and tests. Do not reinterpret existing v1 data or PR #2's rc3 dialect as the atomic draft.
- Package 2 retains a v1 reader and adds the unversioned annotation draft. V1 version rules remain in its spec section 9; the current prerelease is experimental. The software version is separate from annotation data. Keep public callables annotated and existing v1 exports available.
- Each schema has one source file in `schema/`; setuptools maps it into the installed package. Do not restore a second maintained copy under `src/`. Check wheel bytes and source-checkout fallback behavior.
- Examples are synthetic: no text from a real book anywhere in this repository. Legacy `invalid-*` examples record `x_expected_error` and legacy examples stay canonical. The current format has no canonical order; preserve unknown JSON and annotation order.
- `python3 -m pytest` must pass (install `jsonschema` to run the agreement tests).
- Add changes to "Unreleased" or the current explicitly unpublished prerelease entry. Before an authorized release, update the changelog and versions in `pyproject.toml` and `src/formal_companion_annotations/__init__.py`, decide the final schema identifier, and build/test both wheel and sdist. A draft schema identifier does not imply that URL is hosted. Tagging and publication are separate release actions.
