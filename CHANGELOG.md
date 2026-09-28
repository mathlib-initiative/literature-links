# Changelog

Versions of this package. The format's own version is the document's
`schema_version` (section 9 of `docs/annotations.md`), which this release
leaves at `"1.0"`.

## Unreleased

### Changed

- The project is named formal-companion-annotations: the distribution
  `formal-companion-annotations`, the package `formal_companion_annotations`,
  the console script `formal-companion-annotations-validate`, and the
  schema's `$id` and root description to match. The skill it came from is
  cited by its repository's new name, formal-companion. The format
  identifier is not renamed: the root `schema` is still
  `"lean-companion/annotations"` and the docstring line still
  `lean-companion id:`, so every document already written stays valid.
- The history came along: the repository is the skill's history filtered to
  the format's files with `git filter-repo`, plus one commit that brings the
  tree to this package.
- The CLI's `prog` is now `formal-companion-annotations-validate`, the console
  script's name, where 1.0.0 kept the skill's `validate.py`: usage lines and
  argument errors name the command a user actually ran. Nothing else it prints
  changed.
- A missing packaged schema (a broken install) exits 2 with
  "formal-companion-annotations-validate: schema file not found: <path>" on
  stderr. It exited 1 with "$.schema_version: no schema for major version 1
  (this checker has 1)", which blamed the document. `--print-canonical` reads
  no schema, so it still works on such an install.
- The schema's root description names this project's checker, the
  `formal-companion-annotations-validate` command
  (`src/formal_companion_annotations/validate.py`), where it still named the
  skill's `scripts/annotations/validate.py`, which is not in this repository.
  Only that sentence changed, in both copies (which stay byte-identical to
  each other); no validation keyword did. The schema is no longer
  byte-identical to the skill's except for the `$id`.
- The format owns every value it uses. `docs/vocabulary.md` said a change to
  a shared set in the skill was a change to the format; it now says the
  reverse: the values, and a one-line meaning for each, are defined here
  (section 2: the viewer verdicts, severities and statuses, the ledger
  verdicts, the finding kinds, the source roles, the sorry classes and the
  resolution states), and producers, the skill included, conform. The spec
  says the `verdicts` record is specific to faithfulness audits.
- The spec marks section 10 and the section 5.1 survey figures as
  informative, names the two worked companions' repositories
  (`github.com/mathlib-initiative/measure_theory` and
  `github.com/mathlib-initiative/tao-measure-lean`), and rewrites section 11,
  which said no producer existed: the skill's `cf export attribution-table`,
  `cf export docstring-tags`, `cf ingest` and `cf inventory` write documents
  in this format, and `cf review-tags` reads them.
- The tests test the copy of the package Python imports (an installed one
  when there is one) and add `src/` to the path only when none is importable;
  they tested `src/` even when the package was installed.
- `pyproject.toml`: the `requires-python` comment said `datetime.fromisoformat`
  accepts more before 3.11; it accepts less (3.10 rejects
  `2026-09-05T10:20:30.5Z`, which the schema allows).
- `SWITCHOVER.md` gained what it missed: `scripts/pipeline/derive_truth.py`
  and `pipeline/source_gates.py` reach the format too, the skill's documented
  test gate needs the package installed first, and more prose names the old
  `validate.py`.

### Added

- `--version`, which prints the package's version.
- `MANIFEST.in`: the sdist carries the examples, docs, top-level schema,
  `CHANGELOG.md`, `SWITCHOVER.md` and the workflow, so an unpacked sdist runs
  its own tests (it failed 135 of them). The wheel is unchanged: the package
  and its packaged schema only.
- CI jobs that run the suite against a regular (non-editable) install and
  check that the installed copy is the one tested, and that build the sdist
  and wheel with `python -m build`, run `twine check` on them and run the
  unpacked sdist's tests.
- Tests: the usage names the console script, `--version`, the broken-install
  exit, the schema description, a meaning for every shared value.

### Known issues

Present identically in the skill's checker, and deliberately not fixed yet, so
the two checkers do not drift before the switchover (`README.md`, "Known
issues"):

- A number such as `1e400` overflows to `inf` past `loads()`, so a
  schema-valid document passes plain validation, but `--canonical` and
  `--print-canonical` crash with a traceback.
- `--print-canonical` never validates first, so malformed input can crash it
  with a `TypeError` or `UnicodeEncodeError` traceback.

## 1.0.0 (2026-09-28)

First release as a standalone project, extracted from the
formal-companion skill (`github.com/mathlib-initiative/formal-companion`)
at `master` `d4deedb`. It was first cut from one commit that cites these,
without history (see Unreleased).

Where each part comes from in the skill:

- `155292b` "Annotation format v1.0: schema, spec, validator, examples and
  tests": the schema, `docs/annotations.md`, the checker (`validate.py`,
  `schemacheck.py`), the id rules (`ids.py`), the annotation block of
  `scripts/cflib/vocab.py`, section 1.10 of `references/vocabulary.md`, the
  nine examples and `tests/test_annotations_schema.py`.
- `3efbe95` "Apply the pre-merge review of the annotation format": the
  reviewed checker, schema, spec, vocabulary, `mixed.json` and tests.
- `5b93174` (the skill's exporters): `ids.py` gained the public `token_at`
  and `AnonymousDecl.comment_tags` / `comment_tags()`, which the exporters
  use; taken as of that commit.
- `2f48341` and `2e79a91`: the spec's sections 10 and 11 as they stand at
  `d4deedb` (the exporters exist; a producer is proposed).

### Unchanged

- What the checker accepts and rejects, and every message, warning, exit
  status and the canonical bytes it writes. Checked against the skill's copy
  on all nine examples, 6000 random mutations of them, 44 CLI invocations
  (stdout, stderr and status) and the Lean id scanner over the two worked
  companions' `.lean` files.
- The format's identifier: the root `schema` is still
  `"lean-companion/annotations"`, so existing documents validate unedited.
- The schema, byte for byte, except the two changes below.
- The CLI's `prog` is still `validate.py`, so usage and argument errors read
  exactly as the skill's did.

### Changed

- The schema's `$id` is now
  `https://github.com/mathlib-initiative/formal-companion-annotations/schema/annotations-v1.schema.json`
  (a working name, see `README.md`), and the description's last sentence no
  longer says a rename of the skill is pending. The rest of that description
  still names the checker by its path in the skill; it was left as it was to
  keep the schema otherwise byte-identical.
- The checker is a package, `formal_companion_annotations`, with a console
  script, `formal-companion-annotations-validate`, and `python3 -m` entry points.
  The schema ships inside it as package data
  (`src/formal_companion_annotations/schema/`, the same bytes as `schema/`), and
  `validate.SCHEMA_DIR` points there.
- `vocab.py` holds only what the format needs: the skill's annotation block,
  verbatim but for the paths its comments cite, and the skill sets the format
  reuses (`VIEWER_VERDICTS`, `VIEWER_SEVERITIES`, `VIEWER_STATUS`,
  `LEDGER_VERDICTS`, `FINDING_KINDS`, `SOURCE_ROLES`, `SORRY_CLASSES`,
  `STATIC_RESOLUTIONS`, `RESOLUTION_PREFIXES`) written out as literals. All 58
  constants equal the skill's.
- Imports are relative within the package; nothing imports the skill's
  `cflib`. The skill's checker imported `cflib` (and with it the whole of
  `cflib`, which imports PyYAML when it is installed) only for those
  constants.
- `docs/annotations.md` cites this repository's paths, and the skill's files
  as `formal-companion/...`. `docs/vocabulary.md` is the skill's section
  1.10 plus the values of the reused sets.
- Tests: imports and paths adapted, and the `tests/_hermetic.py` HOME pin
  dropped (nothing here reads HOME). The `$id` test now asserts the exact new
  `$id` and that the description no longer mentions the rename, where it
  asserted `/lean-companion/` and `rename`. `schema_path()` is compared with
  the packaged copy. Added: the packaged schema equals `schema/` byte for
  byte, the format identifier is unchanged, every value of a reused set is
  documented, and `tests/test_packaging.py` (standard-library-only imports,
  entry points, version, doc citations).

### Added

- `README.md`, `SWITCHOVER.md` (what the skill would change to consume this
  package), `pyproject.toml`, `.github/workflows/tests.yml`, and the skill's
  `LICENSE` (Apache-2.0).
