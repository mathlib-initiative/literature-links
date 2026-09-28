# Changelog

Releases of formal-companion-annotations. The package follows semantic
versioning tied to the format's version (README.md, "Versions and
compatibility"; `docs/annotations.md` section 9). The format's own version is
the document's `schema_version`.

## 1.0.0 (2026-09-28)

The first release: the formal-companion annotation format, `schema_version`
`"1.0"`, as a standalone, standard-library-only Python package, extracted
from the formal-companion skill (`github.com/mathlib-initiative/formal-companion`)
at `master` `d4deedb`.

### Where it comes from

This repository keeps the skill's history of the format. `git filter-repo`
cut the skill's `master` at `d4deedb` down to the format's files (the schema,
`docs/annotations.md`, `examples/annotations/`, the checker, the id rules and
`tests/test_annotations_schema.py`) and moved `scripts/annotations/` to
`src/formal_companion_annotations/`, keeping every author, date and message.
Each skill commit and its commit here:

| skill | here | what it brought |
|---|---|---|
| `155292b` | `cc001f0` | "Annotation format v1.0: schema, spec, validator, examples and tests": the schema, the spec, the checker (`validate.py`, `schemacheck.py`), the id rules (`ids.py`), the nine examples and their tests. The annotation block of the skill's `scripts/cflib/vocab.py` and section 1.10 of its `references/vocabulary.md` were written here too; they became `vocab.py` and `docs/vocabulary.md` in the extraction commit |
| `3efbe95` | `5f408b1` | "Apply the pre-merge review of the annotation format": the reviewed checker, schema, spec, `mixed.json` and tests |
| `2f48341` | `168f935` | the PDF-to-companion proposal: the spec's list of what v1 leaves out names the proposed producer (merged as `8122f86`, here `b6ad0a0`) |
| `5b93174` | `bfb4283` | the skill's exporters: `ids.py` gained the public `token_at` and `AnonymousDecl.comment_tags` / `comment_tags()` |
| `2e79a91` | `5a52f80` | the exporters' docs: the spec's sections 10 and 11 name the two exporters and where their reference documents are kept (merged as `0991892`, here `503bbb0`) |

The skill's last merge, `d4deedb`, touched none of these files, so the
filtered history ends at `503bbb0`. On top of it:

- `576553d` "Extract the format as the standalone formal-companion-annotations
  package" brings the tree to the package, as first cut and checked in a
  preliminary, unpublished repository (lean-companion-annotations, `764c4d8`),
  under this project's names;
- the release commit adds what 1.0.0 lists below as the release polish.

### Unchanged from the skill's copy

- What the checker accepts and rejects, and every message, warning, exit
  status and the canonical bytes it writes. Checked against the skill's copy
  on all nine examples, 6000 random mutations of them, 44 CLI invocations
  (stdout, stderr and status) and the Lean id scanner over the two worked
  companions' `.lean` files.
- The format's identifier: the root `schema` is still
  `"lean-companion/annotations"`, and the docstring line still
  `lean-companion id:`, so every document already written validates
  unedited. The project's name does not change them (README.md says why).
- Every validation keyword of the schema. Only its `$id` and its root
  `description` differ from the skill's.

### Changed from the skill's copy

- **Names.** The distribution is `formal-companion-annotations`, the package
  `formal_companion_annotations`, with a console script,
  `formal-companion-annotations-validate`, and `python3 -m` entry points.
- **The command line.** Its `prog` is the console script's name, where the
  skill's is `validate.py`, so usage lines and argument errors name the
  command a user ran; its `--help` description says "formal-companion".
  `--version` is new. A missing packaged schema (a broken install) exits 2
  with "formal-companion-annotations-validate: schema file not found:
  <path>" on stderr, where the skill's exited 1 with "$.schema_version: no
  schema for major version 1", which blamed the document; `--print-canonical`
  reads no schema, so it still works there.
- **The schema's `$id`** is
  `https://raw.githubusercontent.com/mathlib-initiative/formal-companion-annotations/v1.0.0/schema/annotations-v1.schema.json`:
  the raw URL of the schema at the tag of the release that introduced this
  minor version (spec section 9.3). It resolves only for clients that can
  read the repository; validators never fetch it, and documents need not
  carry `$schema`. The root `description` names this project's checker (the
  skill's names its `scripts/annotations/validate.py`) and states that rule.
  The two copies of the schema stay byte-identical.
- **The package.** The schema ships as package data
  (`src/formal_companion_annotations/schema/`, the same bytes as `schema/`),
  and `validate.SCHEMA_DIR` points there. `vocab.py` holds only what the
  format needs: the skill's annotation block, verbatim but for the paths its
  comments cite, and the sets the format shares with the skill
  (`VIEWER_VERDICTS`, `VIEWER_SEVERITIES`, `VIEWER_STATUS`,
  `LEDGER_VERDICTS`, `FINDING_KINDS`, `SOURCE_ROLES`, `SORRY_CLASSES`,
  `STATIC_RESOLUTIONS`, `RESOLUTION_PREFIXES`) written out as literals; all
  58 constants equal the skill's. Imports are relative; nothing imports the
  skill's `cflib`, which the skill's checker imported (and with it PyYAML,
  when installed) only for those constants.
- **The format owns every value it uses.** `docs/vocabulary.md` (the skill's
  section 1.10 plus the shared sets) defines each value and its meaning, the
  shared sets included (its section 2), and producers, the skill among them,
  conform.
- **The spec.** It cites this repository's paths, and the skill's files as
  `formal-companion/...`. It marks section 10 and the section 5.1 survey
  figures as informative, names the two worked companions' repositories
  (`github.com/mathlib-initiative/measure_theory` and
  `github.com/mathlib-initiative/tao-measure-lean`), and rewrites section 11,
  which said no producer existed: the skill's `cf export attribution-table`,
  `cf export docstring-tags`, `cf ingest` and `cf inventory` write documents,
  and `cf review-tags` reads them. It says the `verdicts` record is specific
  to faithfulness audits and stays in the core format for 1.0. Section 9
  gains the versioning and compatibility policy: the package's MAJOR is the
  format's major, MINOR is backward-compatible additions, PATCH changes no
  admitted document; the exit statuses, the output line formats and `__all__`
  fall under it; the checker picks the schema by the major alone, so writers
  must declare the minor they use; and the `$id` rule.

### Added

- **A public API**: each module's `__all__` is exactly its stable API
  (README.md, "Public API"); every name formal-companion imports is in it,
  and a test says so. The public functions are fully annotated (the `spans`
  parameter of three functions in `ids`, and the return of two `__init__`
  methods, gained the annotations they lacked; no code changed), and the
  package ships `py.typed`.
- **Tests** beyond the skill's, which moved with their imports and paths
  adapted (the `tests/_hermetic.py` HOME pin dropped, since nothing here
  reads HOME): `tests/test_packaging.py` (standard-library-only imports, the
  entry points, the usage, `--version`, the broken-install exit, the version
  stated once, the docs cite only paths that exist) and
  `tests/test_public_api.py` (`__all__`, the skill's imports, the
  annotations); the packaged schema equals `schema/` byte for byte, the
  `$id` follows its rule, the checker imports no network library, the format
  identifier is unchanged, and every value of a shared set is documented.
  The suite tests the copy of the package Python imports (an installed one
  when there is one) and adds `src/` to the path only when none is.
- **Packaging**: `pyproject.toml` (with `[project.urls]` and classifiers),
  and `MANIFEST.in`, so an unpacked sdist carries the examples, docs,
  top-level schema, changelog and workflow and runs its own tests. The wheel
  holds the package, its schema and `py.typed` only.
- **CI** (`.github/workflows/tests.yml`): Python 3.11 to 3.14, `jsonschema`
  in one job, `unittest discover` with nothing installed, the installed
  console script against the examples, the suite against a regular install
  (checking it tested the installed copy), and the sdist and wheel
  (`python -m build`, `twine check`, the unpacked sdist's tests).
- **Documents**: `README.md`, `CONTRIBUTING.md` (how a change is proposed,
  when it is minor or major, the two schema copies, synthetic examples only),
  `SWITCHOVER.md` (how formal-companion vendors this package), and the
  skill's `LICENSE` (Apache-2.0), copyright the formal-companion
  contributors.

### Known issues

Present identically in the skill's copy of the checker, and deliberately not
fixed in 1.0.0, so the two checkers do not disagree before the skill vendors
this package (`README.md`, "Known issues"). Each fix will be a patch release.

- A number such as `1e400` overflows to `inf` past `loads()`, so a
  schema-valid document passes plain validation, but `--canonical` and
  `--print-canonical` crash with a traceback ("ValueError: NaN and Infinity
  are not JSON") instead of reporting a problem.
- `--print-canonical` never validates first, so malformed input can crash it
  with a `TypeError` or `UnicodeEncodeError` traceback. Run the checker
  without the flag first.
