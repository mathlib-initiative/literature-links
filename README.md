# formal-companion-annotations

A **Lean companion** is a Lean repository that formalises a book, lecture
notes or a paper. The **formal-companion annotation format** is one JSON
document per companion that says which Lean declarations formalise which
items of which sources, and where those items sit in the sources: a PDF
region, a quote on a web page, a page of a rendered site, a line range in a
`.tex` or `.lean` file. With it, a PDF overlay, a web viewer or an audit can
join the book and the Lean without reading either repository's own
conventions.

This repository holds the format and nothing else: its JSON Schema, its prose
specification, a checker that validates what a JSON Schema cannot, the
mechanical id rules, and synthetic examples, as the Python package
`formal_companion_annotations`. It is standard library only (Python 3.11+)
and has no runtime dependencies.

## Who writes and reads it

The format was designed in, and is used today by,
[formal-companion](https://github.com/mathlib-initiative/formal-companion)
(formerly named companion-faithfulness), the Claude Code skill that audits
Lean companions against their sources. Its tools are the format's producers
and readers:

- **exporters**: `cf export attribution-table` and `cf export docstring-tags`
  turn a companion's own attribution data into a document;
- **the PDF-to-companion pipeline**: `cf ingest` and `cf inventory` write
  its checkpoints (`doc.v0.json`, `doc.v1.json`) as documents;
- **readers**: `cf review-tags` checks a document's key links, and the
  pipeline reads its checkpoints back.

Each of them validates what it writes with this package's checker. The skill
consumes the package by vendoring each release (see
[`SWITCHOVER.md`](SWITCHOVER.md)); section 11 of the spec lists the tools.
Anyone else can write or read documents too: the schema is plain JSON Schema,
and the spec says everything a document must satisfy.

## The format in brief

A document has a fixed header (`schema`, `schema_version`, `companion`) and
arrays of records, each with a string `id` and each array sorted by it:

- `sources`: the editions annotated (a PDF, a web page, a whole rendered site,
  a `.tex` or `.lean` file, or any other medium named by its media type), each
  pinned by a hash or an immutable revision;
- `items`: numbered items (`Definition 1.1`) and unnumbered passages;
- `declarations`: the Lean declarations anything mentions, with mechanical
  ids for anonymous ones (`example:<12 hex>` from a hash of the statement);
- `links`: item to declaration attributions, with a role (`key`,
  `attributed`, `support`, `example`, `helper`);
- `provenance`: how links and locations were produced;
- optional `locations` (W3C Web Annotation targets: PDF regions and pages,
  quotes, text offsets, line ranges, pages of a site), `destinations`,
  `snippets`, `verdicts`, `unattributed`, `clusters`, `memberships`,
  `artifacts` and an id `changelog`.

`verdicts` is specific to faithfulness audits (the adjudicated outcome of
checking an item's Lean against its source). It is part of the core format
in 1.0 and optional: a producer that does not audit omits it, and no other
record depends on it.

- [`docs/annotations.md`](docs/annotations.md) is the specification;
- [`docs/vocabulary.md`](docs/vocabulary.md) defines every enum value and
  what it means, including the sets the format shares with formal-companion
  (the format owns them; producers conform);
- [`schema/annotations-v1.schema.json`](schema/annotations-v1.schema.json)
  is the JSON Schema (draft 2020-12) for `schema_version` `"1.0"`;
- [`examples/annotations/`](examples/annotations/) has one synthetic document
  per kind of source, and two that are invalid on purpose.

The canonical serialisation follows RFC 8785 (JCS) for key order and numbers,
with a fixed two-space layout (spec section 7).

## Install

The repository is private for now, so installing needs read access to it
(an SSH key or a token git can use). There is no package-index release.

```sh
python3 -m pip install "formal-companion-annotations @ git+https://github.com/mathlib-initiative/formal-companion-annotations@v1.0.0"
# or, with an SSH key:
python3 -m pip install "formal-companion-annotations @ git+ssh://git@github.com/mathlib-initiative/formal-companion-annotations@v1.0.0"
# or from a checkout:
python3 -m pip install .
```

Pin a tag. The package is standard library only, so nothing else is
installed.

## Usage

### The command line

```sh
formal-companion-annotations-validate my-companion.annotations.json
formal-companion-annotations-validate my-companion.annotations.json --canonical
formal-companion-annotations-validate my-companion.annotations.json --print-canonical > fixed.json
```

`python3 -m formal_companion_annotations` (or
`python3 -m formal_companion_annotations.validate`) runs the same checker.

The checker reads the document's `schema_version`, evaluates the JSON Schema
for that major version with its own small draft 2020-12 evaluator, and then,
on a document the schema accepts, checks the invariants no JSON Schema can
state ([spec section 6](docs/annotations.md#6-invariants-and-warnings)):
unique and sorted ids, references that resolve, anchoring and coverage rules,
the id rules, selector grammars against their `conformsTo`, the changelog's
rules and the URL rule. `--canonical` also requires the file's bytes to be
the canonical form; `--print-canonical` writes that form (it does not
validate first; see "Known issues").

Output, one line each:

- `<file>: <path>: <message>` for each problem;
- `<file>: warning: <message>` for each warning (an unknown `conformsTo` IRI,
  a link `relation` outside the documented core, a newer minor version),
  which does not fail the document;
- `<file>: ok (<counts>)` for a valid document.

Exit status: **0** valid, **1** invalid, **2** unreadable (not JSON, a
duplicate key, `NaN`), a usage error, or a broken install (the packaged
schema file is missing: "schema file not found"). `--version` prints the
package's version.

### From Python

```python
from formal_companion_annotations import validate

text = open("doc.json", encoding="utf-8").read()
doc = validate.loads(text)                     # strict: no duplicate keys, no NaN
report = validate.check(doc, text=text, canonical=True)
report.problems, report.warnings               # lists of "path: message"
canonical = validate.canonical_dumps(validate.canonicalize(doc))
```

[`ids`](src/formal_companion_annotations/ids.py) has the mechanical id rules
(statement-hash ids for `example` and anonymous `instance`, scanning Lean
source, private ids, and the passage ids), and
[`vocab`](src/formal_companion_annotations/vocab.py) the enums and the id
grammar. Any JSON Schema 2020-12 validator can check the schema alone
(`validate.SCHEMA_PATH` is the packaged copy); only this checker also checks
the invariants.

### Public API

The stable Python API is exactly each module's `__all__`:

| module | exports |
|---|---|
| `formal_companion_annotations` | `__version__` and the four modules below |
| `validate` | `loads`, `LoadError`, `check`, `Report`, `validate`, `main`, `canonicalize`, `canonical_dumps`, `order_key`, `site_sha256`, `RECORD_ARRAYS`, `SCHEMA_DIR`, `SCHEMA_PATH`, `schema_path` |
| `ids` | `AnonymousDecl`, `scan_file`, `assign_ids`, `ordinal_ids`, `statement_sha256`, `normalize_statement`, `anonymous_id`, `private_id`, `named_signature`, `comment_tags`, `item_label_id`, `passage_quote_id`, `passage_page_id`, `normalize_text`, `strip_comments`, `blank_literals`, `token_at`, `HASH_ID`, `DECLARED_ID` |
| `schemacheck` | `Validator`, `SchemaError` |
| `vocab` | every constant (the enums, the id grammar, the `conformsTo` IRIs, `ANNOTATION_SCHEMA` and its version) |

Any other name, underscored or not, is internal and may change in any
release. The public API is fully annotated, and the package ships a
`py.typed` marker. [`tests/test_public_api.py`](tests/test_public_api.py)
checks that every name formal-companion imports is exported.

## Versions and compatibility

The package follows semantic versioning, tied to the format's version
(`schema_version`, `"<major>.<minor>"`):

- **MAJOR** is the format's major version. Package 1.x reads documents whose
  `schema_version` is `"1.*"`, and only those. A change a reader of the
  previous major cannot ignore (a key removed or made required, a value
  removed or given another meaning) is a new major, of both.
- **MINOR** is for backward-compatible additions: new optional fields or new
  enum values (a new format minor, `"1.1"`), or new public Python names. A
  document valid under X.Y stays valid under X.(Y+1).
- **PATCH** is for checker and documentation fixes that do not change which
  documents the spec admits. Fixing a checker that wrongly accepted a
  document the spec forbids is a patch, since the spec never admitted that
  document; the CHANGELOG calls out every such fix, because a document that
  passed before can fail after it.

Also under semver: the CLI's exit statuses (0, 1, 2) and its line formats
above, and the Python API (`__all__`). The wording of a message is not: match
on the exit status and the path, not the words.

**The checker picks the schema by the major version alone.** A 1.1 checker
checks every `"1.*"` document against its 1.1 schema, so a document that says
`"1.0"` but uses a key added in 1.1 passes. The checker cannot tell that the
declared minor is wrong, so **writers must declare the minor they wrote
against**. A reader then knows which keys to expect; an older checker that
meets a newer minor warns, and refuses the keys it does not know (every
object is closed) rather than dropping them.

The full rules are in
[spec section 9](docs/annotations.md#9-versions-and-the-changelog), and each
release is in [`CHANGELOG.md`](CHANGELOG.md).

## The format identifier is still `lean-companion/annotations`

The project is named formal-companion-annotations, but the identifier every
document carries is unchanged: the root `schema` key is still
`"lean-companion/annotations"` (the schema's `schema` const and
`vocab.ANNOTATION_SCHEMA`), and so is the `lean-companion id:` docstring line
(spec section 5.1). That is deliberate. The identifier is data inside every
document and docstring producers have already written, formal-companion's
exporters and pipeline among them; renaming it would make every one of those
invalid, for no change in what they mean. It names the format, not the
repository that hosts it, so it does not follow a rename.

## The schema's `$id`

The schema's `$id` is the raw URL of the schema file at the tag of the
release that introduced this minor version of the format. For 1.0 that is
`https://raw.githubusercontent.com/mathlib-initiative/formal-companion-annotations/v1.0.0/schema/annotations-v1.schema.json`.
It resolves only for clients that can read the repository, which is private
for now. Validators never fetch it (this checker makes no network request),
and documents need not carry `$schema`; one that does should give this `$id`.

## Repository layout

```
schema/annotations-v1.schema.json        the JSON Schema (the package ships the same bytes)
docs/annotations.md                      the specification
docs/vocabulary.md                       every enum value and its meaning, the shared sets included
src/formal_companion_annotations/        the package: validate, schemacheck, ids, vocab, schema/
examples/annotations/                    synthetic documents; the two invalid-*.json fail on purpose
tests/                                   stdlib unittest, run with pytest or unittest
MANIFEST.in                              what the sdist carries beyond the package, so it runs its tests
```

The examples are synthetic: every non-Lean source title says so, and no
document here quotes a real book.

## Tests

```sh
python3 -m pytest
python3 -m unittest discover -s tests
```

The suite tests the copy of the package Python imports: an installed one when
there is one (a regular or an editable install), and otherwise `src/`, which
it then adds to the path itself, so neither command needs the package
installed. The sdist carries everything the suite reads (`MANIFEST.in`), so
an unpacked sdist runs both commands too. When the `jsonschema` package is
importable, the suite also checks that it agrees with the package's own
evaluator on every example and on random mutations of them; otherwise those
tests skip. CI (`.github/workflows/tests.yml`) runs Python 3.11 to 3.14,
installs `jsonschema` in the 3.13 job, checks an installed wheel's console
script against the examples, runs the suite against a regular install (and
checks that it imported the installed copy, not `src/`), and builds the sdist
and wheel, runs `twine check` on them and runs the unpacked sdist's tests.

## Known issues

Both are present, identically, in the copy of the checker formal-companion
still carries (`scripts/annotations/validate.py` there). They are
deliberately not fixed in 1.0.0: until the skill vendors this package
(`SWITCHOVER.md`), the two checkers must accept and reject the same
documents with the same messages and canonical bytes. Each fix will be a
patch release, called out in the CHANGELOG.

- **A number too large for a float passes plain validation, then crashes the
  canonical form.** `loads()` refuses the `NaN` and `Infinity` literals, but a
  number such as `1e400` parses, overflows to `inf`, and gets past it. The
  schema accepts it where any number is allowed (in an `x_` key, say), so the
  document passes plain validation (exit 0), while `--canonical` and
  `--print-canonical` crash with a traceback ("ValueError: NaN and Infinity
  are not JSON") instead of reporting a problem.
- **`--print-canonical` never validates first.** It canonicalises whatever
  JSON object it reads, so a malformed document can crash it with a traceback
  instead of an error message: a `TypeError` (an unhashable value in a list
  that is sorted as a set, such as `"clusters": [[1]]`, or numbers and strings
  mixed in a keyed list) or a `UnicodeEncodeError` (a lone surrogate such as
  `"\ud800"` in a string). Run the checker without the flag first.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md): how a change to the format is
proposed, when it is a minor or a major version, and the rules for the
schema and the examples. The history of the format before it was extracted,
and what each release changed, is in [`CHANGELOG.md`](CHANGELOG.md).

## License

Apache License 2.0 ([`LICENSE`](LICENSE)). Copyright 2026 the
formal-companion contributors, who wrote this code in the formal-companion
skill before it moved here.
