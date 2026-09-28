# Contributing to formal-companion-annotations

This repository is the annotation format: its specification, its schema, the
checker, the id rules and the examples. Producers and readers, such as
formal-companion's exporters and pipeline, live elsewhere and conform to it.
A change here changes what every one of them may write, so it goes through
these steps.

## Getting set up

```sh
git clone https://github.com/mathlib-initiative/formal-companion-annotations
cd formal-companion-annotations
python3 -m pytest              # or: python3 -m unittest discover -s tests
```

Nothing needs installing: the package is standard library only, and the
suite finds `src/` on its own. Install `jsonschema` to run the agreement tests
too (they skip without it).

## How a change is proposed

1. **Open an issue first** for any change to the format (a key, a value, a
   rule, an invariant, the canonical form, an id rule). Say what a producer
   or reader needs, show a document that needs it, and say which kind of
   change it is (below). A fix to the checker or the docs that changes no
   rule can go straight to a pull request.
2. **One pull request** then changes, together:
   - the spec, `docs/annotations.md`, and `docs/vocabulary.md` for a value;
   - both copies of the schema (below);
   - `src/formal_companion_annotations/vocab.py` for an enum (a test fails
     when the schema's enums and `vocab` disagree);
   - the checker, for a new invariant or rule;
   - an example or a test that exercises the change, and a test for each
     problem message the change adds;
   - `CHANGELOG.md`, under "Unreleased", saying which kind of change it is.
3. **Green** on `python3 -m pytest` and `python3 -m unittest discover -s
   tests` before review.

### Minor or major

The rules are in section 9 of the spec and in the README's "Versions and
compatibility". In short:

- **Minor** (1.0 to 1.1, package 1.x to 1.(x+1)): the change only adds. A new
  optional key, a new enum value, a new public Python name. Every document
  valid before stays valid, and its meaning does not change. Bump
  `schema_version`'s minor (the schema's `schema_version` pattern already
  admits it), `ANNOTATION_SCHEMA_VERSION` in `vocab`, the minor in the
  schema's `title`, and the schema's `$id` to the new release's tag.
- **Major** (1.x to 2.0): anything a reader of the previous major cannot
  ignore. A key removed, renamed or made required; a value removed or given
  another meaning; a rule tightened so that a document valid under the spec
  becomes invalid; a change to the canonical form or to an id rule (which
  re-keys documents). A new major is a new schema file,
  `annotations-v2.schema.json`, beside the old one.
- **Patch**: a fix to the checker or the docs that does not change which
  documents the spec admits. That includes a checker that accepted a document
  the spec forbids: the CHANGELOG entry must say so, under its own heading,
  since documents that passed can fail after it.

Also under these rules: the CLI's exit statuses and its output line formats,
and each module's `__all__`. A name leaves `__all__` only in a major release.
Keep every public function and method fully annotated (the package ships
`py.typed`, and `tests/test_public_api.py` checks the annotations).

The format identifier, `"lean-companion/annotations"`, and the
`lean-companion id:` docstring line are not renamed, in any release: they are
data inside documents already written (README.md says why).

## Both schema copies change together

The schema exists twice, byte for byte:

- `schema/annotations-v1.schema.json`, for readers and non-Python consumers;
- `src/formal_companion_annotations/schema/annotations-v1.schema.json`, the
  package data the checker loads.

Edit one and copy it over the other (`cp schema/annotations-v1.schema.json
src/formal_companion_annotations/schema/`). A test fails when they differ,
and another when the schema is not in the canonical form the checker writes
(`validate.canonical_dumps` of the parsed file).

## Examples are synthetic

Every document under `examples/annotations/` is invented. Do not put book
text into this repository: no quote, passage, statement or title from a real
source, in an example, a test, a doc or a commit message. A `quote` or a
`TextQuoteSelector` holds made-up anchor text, and every non-Lean source's
title says it is synthetic. Real documents live in the companion's
repository or a workspace, never here.

An example is valid unless its name starts with `invalid-`; an invalid one
records the one problem line it must fail with in its own `x_expected_error`
key. Keep every example in canonical form.

## Releases

A maintainer:

1. moves the "Unreleased" entries of `CHANGELOG.md` under the new version and
   date;
2. sets the version in `pyproject.toml` and
   `src/formal_companion_annotations/__init__.py` (a test checks they agree
   with the CHANGELOG);
3. for a new format minor, sets the schema's `$id` to the new tag in both
   copies;
4. tags the release commit `vX.Y.Z` with an annotated tag.

formal-companion then vendors the tagged release (`SWITCHOVER.md`).
