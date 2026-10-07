# Contributing

Contributions to the specification, examples, documentation, and tools are
welcome. A useful report can be as small as an annotation that is difficult to
express, a confusing error, or two readers that interpret the same record
differently. Include the smallest example that demonstrates the problem.

The current format is an unreleased draft. Changes should make individual
annotations easier to write, exchange, and interpret without requiring a
particular companion application.

## Development setup

Use Python 3.11 or newer. From the repository root:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,jsonschema]'
python -m pytest -q
```

On Windows, use `.venv\Scripts\activate` to activate the environment.
The `jsonschema` extra enables agreement checks against an independent JSON
Schema implementation. It is a test dependency, not a runtime requirement.

To check the standard-library-only path in a fresh environment without optional
dependencies:

```sh
python3 -m unittest discover -s tests
```

CI also tests supported Python versions, ordinary installed packages, both
bundled schemas, and the wheel and source distribution. Tests must work offline;
the referenced mathematical resources need not be reachable.

## Proposing a format change

Explain the use case with a small before-and-after example. State whether it
changes the meaning of existing records, and why the existing built-in modes or
generic mode do not express it adequately. A design discussion is useful for
changes to fields or semantics; ordinary fixes do not need a separate proposal.

Keep these sources in agreement:

- [Specification](docs/companion.md): the intended meaning and consumer obligations.
- [Schema](schema/companion.schema.json): the structural rules.
- [Reference checker](src/formal_companion_annotations/companion.py): JSON checks
  and rules that JSON Schema cannot express.
- Examples and tests: accepted cases, rejected cases, and meaningful boundaries.

Each schema has one maintained source in `schema/`. Packaging places that same
file in the installed package; do not add a second maintained copy under `src/`.
Record substantive changes in [the changelog](CHANGELOG.md).

## Review expectations

- Keep one annotation as the unit. Collections, indexes, workflows, and directory
  layout belong outside its schema.
- Preserve unknown extension values and generic locations. Never silently turn
  an unsupported selection into a whole-resource association.
- Preserve relative-reference context and repeated occurrences. Do not infer
  identity or mathematical equivalence from matching labels or URLs.
- Keep validation offline. Test diagnostics and exit statuses as well as success.
- Use original or clearly licensed example content. Identify illustrative URLs
  and claims; do not present invented formalizations as verified mathematics.
- Cover changed behavior with focused tests. Check independent schema agreement
  and installed behavior when a change touches those boundaries.

Changes must not silently reinterpret legacy records. Public callables remain annotated, and each module declares its public names
in `__all__`.

## Preparing a release

The annotation is currently unversioned; Python package versions are separate.
Before a release, maintainers must agree on the public format and schema
identifier, resolve competing prerelease work, update package metadata and the
changelog, and test built distributions in a clean environment. A schema `$id`
does not by itself mean that an endpoint has been published. Tagging, uploading
packages, and publishing schema files are separate release actions.
