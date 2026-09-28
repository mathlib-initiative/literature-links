# formal-companion-annotations

The **formal-companion annotation format**: one JSON document per Lean
"companion" (a Lean repository that formalises a book, lecture notes or a
paper) saying which Lean declarations formalise which items of which sources,
and where those items sit in the sources. This repository holds the format
and nothing else: its JSON Schema, its prose specification, a validator that
checks what a JSON Schema cannot, the mechanical id rules, and synthetic
examples.

The package is standard library only (Python 3.11+) and has no runtime
dependencies.

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

The full specification is `docs/annotations.md`; every enum value, and what it
means, is defined in `docs/vocabulary.md`. The format owns every value it
uses, including the sets it shares with the formal-companion skill:
producers, the skill among them, conform to this repository. The schema is
`schema/annotations-v1.schema.json` (JSON Schema draft 2020-12), for
`schema_version` `"1.0"`. The canonical
serialisation follows RFC 8785 (JCS) for key order and numbers, with a fixed
two-space layout.

## Validating a document

Install from a checkout (there is no package-index release yet):

```sh
python3 -m pip install .
```

Then:

```sh
formal-companion-annotations-validate my-companion.annotations.json
formal-companion-annotations-validate my-companion.annotations.json --canonical
formal-companion-annotations-validate my-companion.annotations.json --print-canonical > fixed.json
```

Without the script, `python3 -m formal_companion_annotations.validate` or
`python3 -m formal_companion_annotations` runs the same checker.

The checker reads the document's `schema_version`, evaluates the JSON Schema
for that major version with its own small draft 2020-12 evaluator, and then,
on a document the schema accepts, checks the invariants no JSON Schema can
state (section 6 of the spec): unique and sorted ids, references that resolve,
anchoring and coverage rules, the id rules, selector grammars against their
`conformsTo`, the changelog's rules and the URL rule. `--canonical` also
requires the file's bytes to be the canonical form; `--print-canonical` writes
that form. Output is one `<file>: <path>: <message>` line per problem, and
warnings (an unknown `conformsTo` IRI, a link `relation` outside the documented
core, a newer minor version) are printed as `<file>: warning: ...` and do not
fail the document.

Exit status: 0 valid, 1 invalid, 2 unreadable (not JSON, a duplicate key,
`NaN`) or a broken install (the packaged schema file is missing: "schema file
not found"). `--version` prints the package's version. See also "Known
issues" below.

From Python:

```python
from formal_companion_annotations import validate

text = open("doc.json", encoding="utf-8").read()
doc = validate.loads(text)                     # strict: no duplicate keys, no NaN
report = validate.check(doc, text=text, canonical=True)
report.problems, report.warnings               # lists of "path: message"
canonical = validate.canonical_dumps(validate.canonicalize(doc))
```

`formal_companion_annotations.ids` has the mechanical id rules (statement-hash
ids for `example` and anonymous `instance`, scanning Lean source, and the
passage ids), and `formal_companion_annotations.vocab` the enums and the id
grammar.

Any JSON Schema 2020-12 validator can check the schema alone; only this
checker also checks the invariants.

## The format identifier is still `lean-companion/annotations`

The project is named formal-companion-annotations, but the identifier every
document carries is unchanged: the root `schema` key is still
`"lean-companion/annotations"` (the schema's `schema` const and
`vocab.ANNOTATION_SCHEMA`), and so is the `lean-companion id:` docstring line
(section 5.1 of the spec). That is deliberate. The identifier is data inside
every document producers have already written, the formal-companion skill's
exporters and pipeline among them; renaming it would make every one of those
documents invalid, for no change in what they mean. The identifier names the
format, not the repository that hosts it, so it does not follow a rename.

The schema's `$id` is
`https://github.com/mathlib-initiative/formal-companion-annotations/schema/annotations-v1.schema.json`.
The `$id` is an identifier that is never fetched, so nothing breaks if it does
not resolve. The schema differs from the skill's schema file only in its root
`description` and its `$id`: the description names this project's checker
(the skill's names its own `scripts/annotations/validate.py`) and no longer
says a rename is pending. Every validation keyword is the same, so both accept
exactly the same documents.

## How this relates to formal-companion

The format was designed inside the **formal-companion** Claude Code skill
(`github.com/mathlib-initiative/formal-companion`, formerly named
companion-faithfulness), which audits Lean companions against their sources,
in its commits
`155292b` (the format, schema, validator, examples and tests) and `3efbe95`
(the pre-merge review), with `ids.py` as later extended in `5b93174`. This
repository was extracted from the skill's `master` at `d4deedb`, with its
history: `git filter-repo` kept the skill's commits that touched the format's
files, with their authors, dates and messages, and one commit on top brought
the tree to the standalone package.

What moved here is the format: the schema, the spec, the checker
(`validate.py`, `schemacheck.py`), the id rules (`ids.py`), the annotation
block of the skill's vocabulary and the few sets the format shares with the
skill, which it now owns (`vocab.py`), the examples and their tests. The
checker accepts and rejects exactly what the skill's copy does, with the same
messages, warnings, exit statuses and canonical bytes; only the command line
differs: its usage and argument errors name
`formal-companion-annotations-validate` (the skill's say `validate.py`), it has
`--version`, and a missing packaged schema exits 2 (see `CHANGELOG.md`).

What stayed in the skill is the tooling that produces and reads documents:
its exporters (`cf export attribution-table`, `cf export docstring-tags`), the
tag review (`cf review-tags`) and the pipeline code that writes documents
(`cf ingest` and `cf inventory`, which write `doc.v0.json` and `doc.v1.json`);
section 11 of `docs/annotations.md` lists them.
Until the skill is switched over it keeps its own copy of the format;
`SWITCHOVER.md` lists the exact changes that would make it consume this
package instead.

## Repository layout

```
schema/annotations-v1.schema.json        the JSON Schema (the package ships the same bytes)
docs/annotations.md                      the specification
docs/vocabulary.md                       every enum value and its meaning, the shared sets included
src/formal_companion_annotations/          the package: validate, schemacheck, ids, vocab, schema/
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

Both are present, identically, in the formal-companion skill's copy of
the checker (`scripts/annotations/validate.py` there). They are deliberately
not fixed here yet: until the skill is switched over to this package
(`SWITCHOVER.md`), the two checkers must accept and reject the same
documents with the same messages and canonical bytes, so a fix lands in both
at the switchover rather than making them drift before it.

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

## License

Apache License 2.0 (`LICENSE`), copied from formal-companion, whose
contributors wrote this code.
