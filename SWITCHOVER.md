# Switching formal-companion over to this package

The exact changes the formal-companion skill would need to consume
`formal-companion-annotations` in place of its own copy of the format. **None of
them has been applied.** Line numbers are the skill's at `master` `d4deedb`.

Below, `<URL>` is this repository's address once it has one; the working name
is `https://github.com/mathlib-initiative/formal-companion-annotations`. `v1.0.0`
is the tag to create on this repository's first published commit (none exists
yet). Until both exist, a developer can try the switchover against a local
checkout with `python3 -m pip install -e /path/to/formal-companion-annotations`.

**Contents**: 1 what changes and what does not · 2 declare the dependency · 3 delete · 4 change imports · 5 vocabulary · 6
citations the skill's doc tests will catch · 7 prose, the test gate and the
old `validate.py` · 8 a new skill test · 9 CI · 10 checking the result

## 1. What changes and what does not

The package's checker accepts and rejects exactly what the skill's copy does,
with the same messages, warnings, exit statuses and canonical bytes (see this
repository's `CHANGELOG.md`). Only its command line differs: usage lines and
argument errors name `formal-companion-annotations-validate` where the skill's
say `validate.py`, it has `--version`, and a missing packaged schema (a broken
install) exits 2 with "schema file not found". Nothing in the skill reads
those: its producers call the checker in-process, and the one test that runs
it as a command (`validate_cli` in `tests/test_m1_source_side.py`, section 4)
asserts only the exit status and the absence of warnings. The module-level
API the skill uses is unchanged: `ids.*`, `validate.loads`,
`validate.check`, `validate.validate`, `validate.canonical_dumps`,
`validate.canonicalize`, `validate.order_key`, `validate.site_sha256`,
`validate.RECORD_ARRAYS`, `validate.LoadError`. So the switchover is imports,
deletions and prose; no call site changes shape.

What does change for the skill:

- **It gains a dependency.** CLAUDE.md section 3 says "standard library only
  ... Do not add a dependency without changing this paragraph", README.md
  says "Nothing is installed into Python", and pyproject.toml says
  `dependencies = []`. The package is itself standard library only, so the
  skill's transitive closure stays standard library, but a clone no longer
  runs every command with nothing installed. Section 2 changes all three.
- **Four commands and one maintainer script need the package; the rest do
  not.** `scripts/cf.py`
  imports every `cfcmd` module and registers a stand-in for one that fails to
  import (`discover_commands`), so without the package every other command
  works as before, and the four fail as that mechanism already makes them
  fail (seen in the dry run of section 10): `cf export`, `cf ingest` and
  `cf inventory` are listed as "(unavailable: ModuleNotFoundError)" and, run
  bare, say "command 'export' failed to import: No module named
  'formal_companion_annotations'"; with arguments (`cf export
  attribution-table ...`) argparse reports "unrecognized arguments" instead;
  and `cf review-tags` is "invalid choice", because the stand-in is
  registered under the module's name, `review_tags`. The `cf doctor` row of
  section 2 is what names the missing package. For all this to stay true,
  `scripts/cflib/vocab.py` must **not** import the package: `cflib` is
  imported by everything, including `cf.py` itself (section 5).
- **The pipeline reaches the package through `pipeline/document.py`.**
  `scripts/pipeline/document.py` imports it directly (section 4), and three
  modules reach it only through that one or through `pipeline/recall.py`, so
  a `git grep` for the old import misses them:
  `scripts/pipeline/source_gates.py` (line 37, `from pipeline import
  document`; the S1 gates, used by `cf inventory`), `scripts/pipeline/ingest.py`
  (line 49; `cf ingest`) and `scripts/pipeline/derive_truth.py`, which imports
  `pipeline.recall` (line 46), which imports `annotations.ids` (line 28,
  section 4) and `pipeline.document` (line 30). `derive_truth.py` is not a
  `cf` command: the maintainer runs it by path (`docs/pipeline.md` line 167,
  `tests/data/m1/README.md` lines 32-33), so there is no stand-in for it, and
  without the package it stops with a `ModuleNotFoundError` traceback. It
  needs no import change (its own imports name no deleted module), only the
  package installed, which section 2's prose must say.
- **The documented test gate needs the package installed first.** A bare
  `python3 -m unittest discover -s tests` in a clone without it fails to
  import six test modules (`tests/test_export.py`,
  `tests/test_review_tags.py`, `tests/test_m1_source_side.py`,
  `tests/test_m1_calibration.py`, `tests/test_m1_derive_truth.py` and
  section 8's new `tests/test_annotation_format_dependency.py`), which
  unittest reports as errors, so the gate goes red. Section 7 changes the
  docs that call that command the gate, and section 9 the CI jobs.

If "a clone runs with nothing installed" must stay literally true, the
alternative is to vendor this repository (a `git subtree` of `src/` at
`scripts/formal_companion_annotations/`, which `cf.py`'s `scripts/` path entry
already makes importable) and pin it with a test that compares its
`__version__` and bytes to a release. The rest of this document assumes the
dependency route; the deletions, imports and prose are the same either way,
and only sections 2 and 9 differ.

## 2. Declare the dependency

**`pyproject.toml`** (the skill's, which is deliberately not an installable
distribution; the declaration is for `uv` and other tools, and for readers):

```toml
# was: dependencies = []
dependencies = [
  "formal-companion-annotations @ git+<URL>@v1.0.0",
]
```

Use `"formal-companion-annotations>=1.0,<2"` instead once it is on a package
index. The major version is the format's major version: a `2.x` would read
`schema_version` `"2.*"` documents, which the skill's exporters do not write.
Rewrite the comment above it ("Standard library only (CLAUDE.md S3) ...") to
say the skill depends on one standard-library-only package, the annotation
format.

**`tests/test_rf_core.py`** line 345
(`TestRepositoryFurniture.test_pyproject_declares_the_runtime_contract`)
asserts `self.assertIn("dependencies = []", text)`, so it fails on that edit.
Change it to assert the one declared dependency, for example
`self.assertIn('dependencies = [\n  "formal-companion-annotations', text)`, and
keep its `yaml = [` assertion (PyYAML stays an extra).

**`uv.lock`**: run `uv lock` after the edit (it needs `<URL>` to exist).

**`CLAUDE.md` section 3**, first bullet (line 70): "3.11+, standard library
only" becomes "3.11+, standard library plus `formal-companion-annotations` (the
annotation format, itself standard library only; `cf export`, `cf
review-tags`, `cf ingest`, `cf inventory`, the maintainer's
`scripts/pipeline/derive_truth.py` and the test suite need it, and nothing
else imports it)". Keep the PyYAML sentence.

**`README.md` "Install"**: after the `git clone`, add

```sh
python3 -m pip install "formal-companion-annotations @ git+<URL>@v1.0.0"
```

and change "Nothing is installed into Python." (line 91) to say that this one
package is, and which four commands, which script and the test suite need it.
Change "Requirements: Python 3.11+ (stdlib only; ..." (line 84) to match
CLAUDE.md.

**`scripts/cfcmd/doctor.py`**, in `check()`, after the PyYAML row (around line
127), add one optional row:

```python
    try:
        import formal_companion_annotations
        fmt_version = formal_companion_annotations.__version__
    except ImportError:
        fmt_version = None
    rows.append({
        "name": "formal-companion-annotations",
        "required": False,
        "ok": fmt_version is not None,
        "detail": fmt_version or "cf export, cf review-tags, cf ingest, cf inventory and the tests need it",
        "fix": 'pip install "formal-companion-annotations @ git+<URL>@v1.0.0"',
    })
```

and mention it in the module docstring's list of what is checked (lines
13-15).

## 3. Delete

| path | why |
|---|---|
| `schema/annotations-v1.schema.json` (and `schema/`) | the package ships it as package data |
| `examples/annotations/*.json` (and `examples/`) | they live here now, with their tests |
| `scripts/annotations/ids.py` | `formal_companion_annotations.ids` |
| `scripts/annotations/schemacheck.py` | `formal_companion_annotations.schemacheck` |
| `scripts/annotations/validate.py` | `formal_companion_annotations.validate` |
| `tests/test_annotations_schema.py` | this repository's `tests/test_annotations_schema.py` |
| `scripts/cflib/vocab.py` lines 200-330 | the "annotation documents" block, from `# --- annotation documents` through `PASSAGE_PAGE_ID_PATTERN`; section 5 |

Keep `scripts/annotations/__init__.py`, `scripts/annotations/review_tags.py`
and `scripts/annotations/export/`: they are the skill's tooling that produces
and reads documents. Replace the `__init__.py` docstring (it names the three
deleted modules and the schema path) with one saying the package holds the
exporters and the tag review, and that the format itself is
`formal_companion_annotations`.

**`docs/annotations.md`: replace, do not delete.** Once the files above are
gone, 47 lines in 20 files of the skill still cite it, mostly by section
number, from docs, code docstrings and exporter error messages
(`scripts/annotations/export/attribution_table.py` lines 359 and 372). Replace
its body with a stub that says the specification now lives in
formal-companion-annotations, as `docs/annotations.md` there, and that every
section number this repository cites is that document's (they are unchanged).
The stub must not cite any path from the table above, or section 6's tests
fail on it.

## 4. Change imports

Every site, exactly:

| file | line(s) | from | to |
|---|---|---|---|
| `scripts/annotations/export/common.py` | 42 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `scripts/annotations/export/common.py` | 43 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `scripts/annotations/export/docstring_tags.py` | 46 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `scripts/annotations/export/docstring_tags.py` | 47 | `from annotations.validate import site_sha256` | `from formal_companion_annotations.validate import site_sha256` |
| `scripts/annotations/export/docstring_tags.py` | 49 | `from cflib import vocab, yamlio` | `from cflib import yamlio` and `from formal_companion_annotations import vocab` |
| `scripts/annotations/export/attribution_table.py` | 38 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `scripts/annotations/export/attribution_table.py` | 40 | `from cflib import vocab` | `from formal_companion_annotations import vocab` |
| `scripts/cfcmd/export.py` | 27 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `scripts/cfcmd/review_tags.py` | 23 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `scripts/pipeline/document.py` | 19 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `scripts/pipeline/document.py` | 20 | `from annotations import validate as annotations_validate` | `from formal_companion_annotations import validate as annotations_validate` |
| `scripts/pipeline/document.py` | 21 | `from cflib import vocab` | `from formal_companion_annotations import vocab` |
| `scripts/pipeline/inventory.py` | 47 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `scripts/pipeline/inventory.py` | 48 | `from annotations.validate import loads` | `from formal_companion_annotations.validate import loads` |
| `scripts/pipeline/recall.py` | 28 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `tests/test_export.py` | 62 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `tests/test_export.py` | 63 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `tests/test_review_tags.py` | 38 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `tests/test_m1_source_side.py` | 49 | `from annotations import ids` | `from formal_companion_annotations import ids` |
| `tests/test_m1_source_side.py` | 116 | `[sys.executable, str(SCRIPTS / "annotations" / "validate.py"),` | `[sys.executable, "-m", "formal_companion_annotations.validate",` (the one place the skill runs the checker by path, in `validate_cli`; a `git grep` for the path misses it, since it is built with `/`) |

The three `vocab` rows are safe because those modules use only annotation
constants from it (`ANNOTATION_SCHEMA`, `ANNOTATION_SCHEMA_VERSION`,
`CONFORMS_TO_PDF`, `CONFORMS_TO_HTML`), which the package defines with the
same values. No other skill module uses a constant from the deleted block
(`git grep -E "vocab\.(ANNOTATION_|CONFORMS_TO_|HASH_ID|DECLARED_|PASSAGE_|ANONYMOUS_)"`
finds only these three files and the deleted ones).

Unchanged and still needed: `from annotations import review_tags`,
`from annotations.export import ...`, `from annotations.export.common import
read_bytes`, and the `sys.path` insert of `scripts/` in
`scripts/annotations/export/common.py` (for `cflib`). The skill's own
`annotations` package and the new `formal_companion_annotations` do not collide.

Docstrings that name the old modules, to rename in the same pass (nothing
fails on them, since they carry no file extension): ``annotations.ids`` in
`scripts/annotations/export/common.py` (lines 22 and 340),
`scripts/annotations/export/attribution_table.py` (line 19) and
`scripts/annotations/export/docstring_tags.py` (lines 13-14, with
``annotations.validate``), and `(annotations.ids)` in `docs/exporters.md`
line 42.

## 5. Vocabulary

CLAUDE.md section 4's first rule ("`scripts/cflib/vocab.py` is the only
definition of the enums") gains an exception: the annotation format's enums,
and the nine sets below that the format shares with the skill, are defined by
`formal_companion_annotations.vocab`; `cflib.vocab` keeps copies of the nine for
the skill's own stages, and they must equal the package's. Say so in that
bullet, and name the test of section 8.

The format **owns** every value it uses, including nine sets it shares with
the skill, where they were first written: `VIEWER_VERDICTS`,
`VIEWER_SEVERITIES`, `VIEWER_STATUS`, `LEDGER_VERDICTS`, `FINDING_KINDS`,
`SOURCE_ROLES`, `SORRY_CLASSES`, `STATIC_RESOLUTIONS` and
`RESOLUTION_PREFIXES` (`ANNOTATION_RESOLUTION_STATES` is derived from the last
two). The package defines their values, and
`formal-companion-annotations/docs/vocabulary.md` section 2 a meaning for each;
the skill, like any producer, conforms. It keeps its own literal copies in
`cflib.vocab`, because its stages (findings, the ledger, the viewer, sources)
use them and `cflib.vocab` must keep importing nothing from the package
(section 1), and those copies must equal the package's. A change to one of
them starts in the format: a package release (a new minor version for a new
value, a new major version for a value removed or given another meaning),
then the skill's pin, then its copy. Section 8's test fails until the skill's
copies agree with the release it pins.

**`references/vocabulary.md` section 1.10** (lines 178-226, up to the `---`
before section 2): keep the heading, so "section 1.10" citations stay true,
and replace the body with: the annotation enums are defined in
`formal_companion_annotations.vocab` and documented in
`formal-companion-annotations/docs/vocabulary.md` (with the prefix: a bare
`docs/vocabulary.md` in backticks is read as the skill's own path and fails
section 6's tests); the nine sets above, which sections 1.2, 1.4, 1.5, 1.6
and 1.7 and `SORRY_CLASSES` document for the skill's stages, are the format's,
defined with their meanings in that file's section 2, and those sections of
the skill must agree with it; `tests/test_annotation_format_dependency.py`
checks that the values do. Update
the contents paragraph (lines 12-15) if its wording changes.

## 6. Citations the skill's doc tests will catch

`tests/test_rf_scrub.py` (`TestNoCitationOfAFileThatIsNotHere`) scans every
tracked file for a token that starts with one of its `REPO_ROOTS` and ends in
a file extension, and fails when the file is missing;
`tests/test_rf_docs.py` does the same for backticked paths in the docs. After
section 3, each of these fails until it is rewritten. Name the file in its new
home with a `formal-companion-annotations/` prefix (the prefix is not a repo
root, so it is not checked as a path here), or name the command:

| file | line | now | becomes |
|---|---|---|---|
| `.github/workflows/tests.yml` | 14 | `scripts/annotations/schemacheck.py` | drop the bullet (lines 14-16): the agreement tests moved out with the evaluator |
| `.github/workflows/tests.yml` | 57 | `tests/test_annotations_schema.py` | drop, with the jsonschema step (section 9) |
| `CHANGELOG.md` | 154 | `schema/annotations-v1.schema.json` | `formal-companion-annotations/schema/annotations-v1.schema.json` |
| `CHANGELOG.md` | 168 | `scripts/annotations/validate.py` | `formal-companion-annotations/src/formal_companion_annotations/validate.py` |
| `docs/pipeline.md` | 25 | `scripts/annotations/validate.py --canonical` | `formal-companion-annotations-validate --canonical` |
| `docs/proposals/pdf-to-companion.md` | 72 | `schema/annotations-v1.schema.json`, `scripts/annotations/validate.py` | the `formal-companion-annotations/` forms above |
| `docs/proposals/pdf-to-companion.md` | 204 | `schema/annotations-v1.schema.json` | `formal-companion-annotations/schema/annotations-v1.schema.json` |
| `docs/proposals/pdf-to-companion.md` | 878 | `scripts/annotations/validate.py` | `formal-companion-annotations-validate` |
| `references/vocabulary.md` | 180-181 | `schema/annotations-v1.schema.json`, `tests/test_annotations_schema.py` | rewritten with section 1.10 (section 5) |
| `scripts/pipeline/document.py` | 5 | ``scripts/annotations/validate.py --canonical`` | ``formal-companion-annotations-validate --canonical`` (or ``formal_companion_annotations.validate``) |
| `scripts/annotations/__init__.py` | 4 | `schema/annotations-v1.schema.json` | rewritten (section 3) |
| `scripts/cflib/vocab.py` | 200, 316-317 | the block's own comments | deleted with the block |

The CHANGELOG lines are history; rewriting the path, not the entry, keeps the
record and passes the test. `REPO_ROOTS` in both tests can keep `"schema/"`
and `"examples/"`: with the directories gone, any later citation of them
fails, which is the point.

Then this prints nothing (the leading class skips the prefixed forms, which
contain the old paths; it printed nothing on the dry run of section 10):

```sh
git grep -nE "(^|[^-/a-z])(schema/annotations-v1\.schema\.json|scripts/annotations/(validate|ids|schemacheck)\.py|tests/test_annotations_schema\.py|examples/annotations/)"
```

## 7. Prose

- `CLAUDE.md` section 2, the layout block: drop the `schema/` and `examples/`
  lines (40-42) and rewrite the `scripts/annotations/` entry (52-55): it now
  holds `export/` (`cf export`) and `review_tags.py` (`cf review-tags`), and
  the format's checker and ids are the formal-companion-annotations package.
- `README.md`, the layout block: the same for its `schema/` and `examples/`
  lines (41-44) and its `scripts/annotations/` entry (55-58).
- `CHANGELOG.md`: a new entry saying the format moved to
  formal-companion-annotations 1.0.0 (schema, spec, checker, id rules, examples
  and their tests), that the skill depends on it, which four commands, which
  script (`scripts/pipeline/derive_truth.py`) and which tests need it,
  that the checker's behaviour is unchanged, and that the schema's `$id` is
  now the package's. Bump `scripts/cflib/__init__.py` `__version__` and
  `pyproject.toml` `version` together if this is released.
- `SKILL.md` line 210 cites `docs/annotations.md`, which the stub keeps; no
  change needed.

**The test gate.** These call a bare `python3 -m unittest discover -s tests`
the gate, which fails without the package (section 1). Put the section 2
`pip install` line before it, or say it runs with the package installed:

- `CONTRIBUTING.md` "Getting set up": the install line after the clone (the
  block is lines 10-14), before line 13's "the documented gate"; and rewrite
  lines 16-18 ("There is nothing to install. ...") to say that one package is
  installed, while the skill itself is still used from a checkout.
- `CONTRIBUTING.md` "Tests": line 73 ("the gate CI runs", and the `pytest`
  line beside it, 74) and "Pull requests", line 110 ("Green on `python3 -m
  unittest discover -s tests` before you open it"): with the package
  installed.
- `README.md` "Tests" (from line 364): the install line before line 367's
  "the documented gate", which also covers the baseline block's command at
  line 379; say so beside it.
- `CLAUDE.md` section 7, line 221: the install line, then the command. Keep
  "Stdlib `unittest` only": the package is not a test framework.
- `docs/adding-an-adapter.md` line 110, the "Checks" block: the same.
- `.github/workflows/tests.yml`: section 9.

**Prose that names the old `validate.py`.** No test fails on these, since
none cites a path under one of the doc tests' repository roots, but each
names a command that no longer exists once section 3's deletions land:

| file | line | now | becomes |
|---|---|---|---|
| `scripts/pipeline/document.py` | 150 | docstring: a checkpoint that ``validate.py --canonical`` would reject | ``formal-companion-annotations-validate --canonical`` |
| `scripts/pipeline/document.py` | 157 | the `CfError` message a user sees when a stage builds a bad checkpoint: "the document does not pass validate.py --canonical: ..." | "... does not pass formal-companion-annotations-validate --canonical: ..." (keep the rest of the message) |
| `scripts/pipeline/inventory.py` | 36 | docstring: the gates of ``pipeline/source_gates.py``, ``validate.py --canonical``, ... | ``formal-companion-annotations-validate --canonical`` |
| `docs/proposals/pdf-to-companion.md` | 240 | "The document passes `validate.py --canonical`." | `formal-companion-annotations-validate --canonical` |
| `docs/proposals/pdf-to-companion.md` | 778 | "CI gate: `validate.py --canonical`; ..." | the same |
| `docs/proposals/pdf-to-companion.md` | 878 | the first column, `validate.py --canonical` (the third is in section 6's table) | the same |
| `docs/proposals/pdf-to-companion.md` | 999 | "1. `validate.py --canonical`." | the same |
| `docs/proposals/pdf-to-companion.md` | 1182 | "passes `validate.py --canonical` with no warnings" | the same |

One more line goes stale with this package's `docs/annotations.md` section 11,
which now lists the skill's producers and readers:
`docs/proposals/pdf-to-companion.md` lines 94-95, "No producer or consumer
reads or writes the annotation format yet; only the checker does
(`docs/annotations.md` section 11)". Rewrite it to say which of the skill's
commands write and read documents (`cf export`, `cf ingest`, `cf inventory`,
`cf review-tags`), citing that section.

## 8. A new skill test

`tests/test_annotation_format_dependency.py`, so the skill's half of the
shared vocabulary cannot drift from the format's:

```python
"""The annotation format is a dependency, and it owns the sets it shares with us.

New code, for the switchover to formal-companion-annotations (CLAUDE.md
section 4).  The format defines nine sets that cflib.vocab also holds, for
the skill's own stages; our copies must equal the package's.  A change to one
starts in the package (a release), then our pin, then our copy: this fails
until our copy agrees with the release we pin.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cflib import vocab                                        # noqa: E402
from formal_companion_annotations import vocab as fmt            # noqa: E402

SHARED = ("VIEWER_VERDICTS", "VIEWER_SEVERITIES", "VIEWER_STATUS", "LEDGER_VERDICTS",
          "FINDING_KINDS", "SOURCE_ROLES", "SORRY_CLASSES", "STATIC_RESOLUTIONS",
          "RESOLUTION_PREFIXES")


class TestTheFormatAgrees(unittest.TestCase):

    def test_our_copy_of_every_shared_set_is_the_formats(self):
        for name in SHARED:
            with self.subTest(set=name):
                self.assertEqual(getattr(vocab, name), getattr(fmt, name))

    def test_the_formats_resolution_states_are_ours_plus_open(self):
        self.assertEqual({"open"} | vocab.STATIC_RESOLUTIONS
                         | {p.rstrip(":") for p in vocab.RESOLUTION_PREFIXES},
                         fmt.ANNOTATION_RESOLUTION_STATES)

    def test_the_exporters_write_the_major_version_the_package_reads(self):
        self.assertEqual(fmt.ANNOTATION_SCHEMA, "lean-companion/annotations")
        self.assertEqual(fmt.ANNOTATION_SCHEMA_MAJOR, 1)


if __name__ == "__main__":
    unittest.main()
```

It builds no workspace, so it needs no `_hermetic` import
(`tests/test_rf_final_tests.py` only requires that of modules that do).

## 9. CI, once `<URL>` exists

In `.github/workflows/tests.yml`:

- **`pytest` (the 3.11/3.12/3.13 matrix)**: line 55 becomes
  `python -m pip install pytest pyyaml "formal-companion-annotations @ git+<URL>@v1.0.0"`.
  Delete the jsonschema step (lines 56-60): the only tests that used it,
  `TestAgreementWithJsonschema`, moved to this repository, whose own CI runs
  them.
- **`pytest-no-pyyaml`**: line 74 becomes
  `python -m pip install pytest "formal-companion-annotations @ git+<URL>@v1.0.0"`.
  The package has no dependencies, so the "PyYAML really is absent" step
  still holds.
- **`unittest`**: line 98 becomes
  `python -m pip install pyyaml "formal-companion-annotations @ git+<URL>@v1.0.0"`.
  The job is named for the gate CLAUDE.md documents (line 90), and its
  comment (lines 99-101) calls it "CLAUDE.md S7's gate": once section 7 puts
  the install into that gate, the job runs exactly what the docs say. Say in
  the comment that without the install six test modules fail to import
  (section 1), which is why the job installs the package rather than proving
  the suite runs with nothing installed.
- **`registry`** and **`synthetic-e2e`**: no change. `cf sources
  validate-registry` and `tests/e2e/synthetic.sh` never reach the four
  commands that import the package, and `cf.py` registers a stand-in for them
  when it is missing, so these jobs keep proving the stdlib-only path.
- The header comment's third bullet (lines 14-16) goes, and a new one says
  which jobs install the package and why the registry job does not.

Keep the pin in the workflow and in `pyproject.toml` the same string; a
`requirements-ci.txt` with that one line, installed with `-r`, keeps them from
drifting. When the package is on an index, the pin becomes
`formal-companion-annotations>=1.0,<2` in both.

## 10. Checking the result

**Dry run.** Sections 3, 4, 5, 6 and 8, the pyproject edit and the
`tests/test_rf_core.py` change of section 2 were applied to a scratch clone
of the skill at `d4deedb` (never to the skill itself), with this package on
`PYTHONPATH` in place of an install. The skill's full suite:

| | passed | skipped | failed |
|---|---|---|---|
| before, at `d4deedb` | 2230 | 201 | 0 |
| after | 2100 | 201 | 0 |

2100 is 2230, less the 133 tests of `tests/test_annotations_schema.py`, which
moved here, plus the 3 of section 8. The first run after the switchover
failed 5 tests, which is how the `tests/test_m1_source_side.py` line 116 row
of section 4 (3 tests) and the citation prefix of section 5 (2 tests) got
into this document; the `tests/test_rf_core.py` paragraph of section 2 was
found by reading the tests before that run. The prose of sections 2 and 7
(CLAUDE.md, README.md, the CHANGELOG entry, the `cf doctor` row) was not
applied, since no test depends on it; the CI edits of section 9 were made but
not run, and `uv.lock` was not regenerated, since both need `<URL>`.

In the skill, once `<URL>` exists:

```sh
python3 -m pip install "formal-companion-annotations @ git+<URL>@v1.0.0"
python3 -m pytest -q tests/                      # 2100 passed, 201 skipped at d4deedb
python3 -m unittest discover -s tests
python3 scripts/cf.py --help                     # export, ingest, inventory, review-tags listed
python3 -m pip uninstall -y formal-companion-annotations
python3 scripts/cf.py sources validate-registry  # still works without it
python3 scripts/cf.py export                     # "failed to import: No module named ..."
```

The exporter reference tests (`tests/test_export.py`, with
`CF_M3_REFERENCE_DIR` and the pinned checkouts) should reproduce the
reference documents byte for byte, since the canonical writer and the id
rules are unchanged; the dry run could not run them (they skip without the
maintainer's references).
