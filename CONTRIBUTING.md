# Contributing to formal-companion-annotations

This repository is the annotation format: its specification, its schema, the
checker, the id rules, the examples and the conformance suite. Producers and
readers live elsewhere and conform to it. A change here changes what every
one of them may write, so it goes through the steps below.

## Getting set up

```sh
git clone https://github.com/mathlib-initiative/formal-companion-annotations
cd formal-companion-annotations
python3 -m pytest              # or: python3 -m unittest discover -s tests
```

Nothing but `pytest` needs installing, and the `unittest` command needs
nothing at all: the package is standard library only, and the suite finds
`src/` on its own. Install `jsonschema` to run the agreement tests too (they
skip without it). The Node job of CI (`ajv` against the conformance suite)
can be run locally with `node conformance/js/run.mjs` after `npm ci` in
`conformance/js/` (`conformance/README.md` has the details).

## How a change is proposed

1. **Open an issue first** for any change to the format: a key, a value, a
   rule, an invariant, the canonical form, an id rule, a profile. Use the
   "Format change proposal" issue template. Say what a producer or reader
   needs, show a document that needs it, and say which kind of change it is
   (below). A fix to the checker or the docs that changes no rule can go
   straight to a pull request. A checker bug (a wrong accept or refuse, a
   crash, a disagreement with the schema or the conformance suite) is
   reported with the "Checker bug" template. Both templates are in
   `.github/ISSUE_TEMPLATE/`; questions go to Discussions.
2. **One pull request** then changes, together:
   - the specification (`docs/annotations.md`; `docs/id-algorithm.md` for an
     id rule) and `docs/vocabulary.md` for a value;
   - both copies of the schema (below);
   - `src/formal_companion_annotations/vocab.py` for an enum (a test fails
     when the schema's enums and `vocab` disagree);
   - the checker, for a new invariant or rule, with its stable code;
   - a conformance vector under `conformance/` for every rule the change
     adds or alters, and an example or test that exercises it;
   - `CHANGELOG.md`, under the heading of the next version, which is marked
     `(unreleased)` until it ships (add that heading when it is absent),
     saying which kind of change it is.
3. **Green** on `python3 -m pytest`, `python3 -m unittest discover -s tests`
   and the Node job before review.

### Minor or major

The rules are in section 12 of the specification. In short:

- **Minor** (format `1.0` to `1.1`, or a profile `1.0` to `1.1`; package
  `1.x` to `1.(x+1)`): the change only adds. A new optional key, a new enum
  value, a new lint, a new public Python name. Every document valid before
  stays valid, and its meaning does not change. A new format minor is a new
  schema file (for example `annotations-v1.1`), beside the old one, with
  its own `$id`. The old file stays, because the checker validates a
  document against the minor it declares.
- **Major** (`1.x` to `2.0`, of the format or of one profile): anything a
  reader of the previous major cannot ignore. A key removed, renamed or made
  required; a value removed or given another meaning; a rule tightened so
  that a document valid under the spec becomes invalid; a change to the
  canonical form or to an id rule (which re-keys documents).
- **Patch**: a fix to the checker or the docs that does not change which
  documents the spec admits. That includes a checker that accepted a document
  the spec forbids: the CHANGELOG entry must say so, under its own heading,
  since documents that passed can fail after it.

Also under these rules: problem and warning codes, the CLI's exit statuses
and output line shapes, and each module's `__all__`. A name or a code leaves
only in a major release. Keep every public function and method fully
annotated (the package ships `py.typed`, and `tests/test_public_api.py`
checks the annotations).

## Both schema copies change together

The schema exists twice, byte for byte:

- `schema/annotations-v1.0.schema.json`, for readers in any language;
- `src/formal_companion_annotations/schema/annotations-v1.0.schema.json`, the
  package data the checker loads.

Edit one and copy it over the other. A test fails when they differ, and
another when the schema is not in the canonical form the checker writes.
Every `pattern` in the schema must mean the same under ECMA-262 and Python:
no `\d`, `\w`, `\s`, `\S`, `\b`, named groups or inline flags. A test
walks every pattern and refuses them, and the Node job checks the
conformance documents with `ajv`.

## Examples and vectors are synthetic

Every document under `examples/annotations/` and `conformance/` is invented.
Do not put source text into this repository: no quote, passage, statement or
title from a real book, paper or project, in an example, a vector, a test, a
doc or a commit message. A `quote` or a `TextQuoteSelector` holds made-up
anchor text, and every non-Lean source's title says it is synthetic. Real
documents live in a companion's own repository, never here.

An example is valid unless its name starts with `invalid-`; an invalid one
records the one problem line it must fail with in its own `x_expected_error`
key. Keep every example in canonical form.

This repository is upstream of every companion and tool that uses it. Its
docs describe the format, not any particular producer or reader; keep
project names out of them.

## Releases

A maintainer:

1. replaces `(unreleased)` in the first heading of `CHANGELOG.md` with the
   release date;
2. sets the version in `pyproject.toml` and
   `src/formal_companion_annotations/__init__.py` (a test checks they agree
   with the CHANGELOG);
3. for a new format minor, adds the new schema file (both copies) with its
   own `$id` and bumps `ANNOTATION_SCHEMA_VERSION` in `vocab.py`;
4. tags the release commit `vX.Y.Z` (or `vX.Y.ZrcN`) with an annotated tag
   and pushes the tag. The `release` workflow builds the sdist and wheel from
   the tag, runs the suite against them, and publishes to PyPI through
   trusted publishing (no token is stored in the repository). A release
   candidate is a pre-release on PyPI: `pip` installs it only with `--pre`.
