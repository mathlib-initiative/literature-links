# Contributing to formal-companion-annotations

This repository maintains the annotation format: the schema, the
specification, the checker and a few examples. Producers and readers live
elsewhere and conform to it. A change here changes what every one of them
may write.

## Tests

```sh
python3 -m unittest discover -s tests      # nothing to install
python3 -m pytest                          # the same suite
```

Install `jsonschema` to also run the agreement tests; they skip without it.

## A change to the format

Open an issue first for any change to a key, a value, a rule, the canonical
form or an id rule. Say what a producer or reader needs and which kind of
change it is. A fix to the checker or the docs that changes no rule can go
straight to a pull request. One pull request then changes, together:

- the schema, `schema/annotations-v1.0.schema.json`, in the canonical form
  the checker writes, with a description for every new field and value;
- the specification, `docs/annotations.md`, for a rule the schema cannot
  state;
- `src/formal_companion_annotations/vocab.py` for an enum (a test fails when
  the schema and `vocab` disagree);
- the checker, for a new rule, with its stable code;
- a test for every rule it adds or changes;
- `CHANGELOG.md`, under the next version marked `(unreleased)`.

Every schema `pattern` must mean the same under ECMA-262 and Python: no
`\d`, `\w`, `\s`, `\b`, named groups or inline flags. A test refuses them.

A **minor** change only adds: an optional key, an enum value, a lint, a
public Python name. A new format minor is a new schema file beside the old
one. A **major** change is anything a reader of the previous major cannot
ignore. Section 7 of the specification has the rules.

## Synthetic examples only

Every example and test document is invented. Do not put text from a real
book, paper or project into this repository. Every non-Lean source title
says it is synthetic. An example is valid unless its name starts with
`invalid-`; an invalid one records the one problem line it must fail with
in its `x_expected_error` key. Keep the examples in canonical form. The
docs describe the format, not any producer or reader.

## Releases

A maintainer dates the first heading of `CHANGELOG.md`, sets the version in
`pyproject.toml` and `src/formal_companion_annotations/__init__.py` (a test
checks they agree), and pushes an annotated tag `vX.Y.Z` or `vX.Y.ZrcN`. The
`release` workflow builds, tests and publishes the tag to PyPI through
trusted publishing. A release candidate installs only with `pip --pre`.
