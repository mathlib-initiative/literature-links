# Switching formal-companion over to this package

The exact changes the formal-companion skill
(`github.com/mathlib-initiative/formal-companion`) needs to consume
formal-companion-annotations in place of its own copy of the format. **None
of them has been applied to the skill.** Every line number below is the
skill's at `master` `d4deedb`, checked for this release, and is a line number
before any edit this document makes: the bootstrap line of section 4 moves
the later lines of the same file down by one.

The skill **vendors** each release: it carries a byte-for-byte copy of one
tagged release's package under `vendor/formal_companion_annotations/`, sealed
by a manifest. Both repositories are private, so installing the package with
`pip` from git would need a CI secret in the skill; a vendored copy needs
nothing installed, keeps "a clone runs with nothing installed" true, and pins
the format by the skill's own tree.

**Contents**: 1 what changes and what does not · 2 vendor the release · 3
delete · 4 change imports · 5 vocabulary · 6 citations the skill's doc tests
will catch · 7 prose · 8 the skill's test of the vendored copy · 9 CI · 10
checking the result · 11 the next release

## 1. What changes and what does not

The package's checker accepts and rejects exactly what the skill's copy does,
with the same messages, warnings, exit statuses and canonical bytes (see this
repository's `CHANGELOG.md`). Only its command line differs: usage lines and
argument errors name `formal-companion-annotations-validate` where the
skill's say `validate.py`, it has `--version`, and a missing packaged schema
(a broken install) exits 2 with "schema file not found". Nothing in the skill
reads those: its producers call the checker in-process, and the one test that
runs it as a command (`validate_cli` in `tests/test_m1_source_side.py`,
section 4) asserts only the exit status and the absence of warnings. Every
name the skill uses is in the package's public API (each module's `__all__`,
which this repository's `tests/test_public_api.py` checks against the
skill's imports): `ids.*`, `validate.loads`, `validate.check`,
`validate.validate`, `validate.canonical_dumps`, `validate.canonicalize`,
`validate.order_key`, `validate.site_sha256`, `validate.RECORD_ARRAYS`,
`validate.LoadError`. So the switchover is a vendored tree, imports,
deletions and prose; no call site changes shape.

What vendoring keeps as it is:

- **No dependency.** CLAUDE.md section 3 ("standard library only ... Do not
  add a dependency without changing this paragraph"), README.md ("Nothing is
  installed into Python", line 91) and `pyproject.toml`'s
  `dependencies = []` all stay true: the vendored package is itself standard
  library only and lives in the tree. `tests/test_rf_core.py` line 345
  (`assertIn("dependencies = []", text)`) needs no change, `cf doctor` needs
  no new row, and the documented test gate (`python3 -m unittest discover -s
  tests`) still runs with nothing installed, so none of the docs that call it
  the gate change.
- **Every command works.** `cf export`, `cf ingest`, `cf inventory` and `cf
  review-tags` import the vendored copy; nothing depends on what is installed.
  An installed copy of the package does not win either: the bootstrap puts
  `vendor/` first on `sys.path`.
- **The pipeline reaches the format through two modules.**
  `scripts/pipeline/document.py` and `scripts/pipeline/recall.py` import it
  (section 4) and take the bootstrap with them, so the modules that reach the
  format only through those, `scripts/pipeline/source_gates.py` (line 37,
  `from pipeline import document`), `scripts/pipeline/ingest.py` (line 49)
  and the maintainer's `scripts/pipeline/derive_truth.py` (line 46, `from
  pipeline import recall`; run by path, `docs/pipeline.md` line 167,
  `tests/data/m1/README.md` lines 32-33), need no change.

What does change: the skill gains `vendor/`, two small modules
(`scripts/cflib/vendored.py`, the path bootstrap, and
`scripts/annotations/sync_format.py`, the sync script) and one test
(`tests/test_vendored_format.py`), and loses its copy of the format.

## 2. Vendor the release

### 2.1 The tree

```
vendor/
  formal_companion_annotations/                src/formal_companion_annotations/ at the tag, byte for byte
  formal_companion_annotations.manifest.json   the seal: upstream, tag, commit, version, sha256 per file
```

At `v1.0.0` the package is eight files: `__init__.py`, `__main__.py`,
`ids.py`, `py.typed`, `schema/annotations-v1.schema.json`, `schemacheck.py`,
`validate.py` and `vocab.py`. Nothing else goes under `vendor/`, and nothing
in it is edited by hand: section 8's test fails on any byte that differs from
the manifest, and section 11 is how it changes. The package is Apache-2.0 by
the same contributors as the skill, under the same `LICENSE`; the manifest's
`license` key records it. Python writes `__pycache__/` beside the vendored
modules when they are imported; the skill's `.gitignore` already ignores
`__pycache__/` and `*.pyc`, and the manifest and the test leave them out.

### 2.2 The manifest

`vendor/formal_companion_annotations.manifest.json`, written by the sync
script (2.4), never by hand. Its shape, with the values it has for `v1.0.0`
except the two that only exist once the tag does:

```json
{
  "commit": "<the 40-hex commit v1.0.0 names>",
  "files": {
    "__init__.py": "<sha256>",
    "__main__.py": "<sha256>",
    "ids.py": "<sha256>",
    "py.typed": "<sha256>",
    "schema/annotations-v1.schema.json": "<sha256>",
    "schemacheck.py": "<sha256>",
    "validate.py": "<sha256>",
    "vocab.py": "<sha256>"
  },
  "license": "Apache-2.0",
  "source": "src/formal_companion_annotations",
  "tag": "v1.0.0",
  "upstream": "https://github.com/mathlib-initiative/formal-companion-annotations",
  "version": "1.0.0"
}
```

### 2.3 The path bootstrap

`scripts/cflib/vendored.py`, new. Every module that imports the format
imports it first (section 4), and section 8's test checks that they do. It is
not imported by `cflib/__init__.py`: an import site names it, so the
dependency is visible where the format is used. `scripts/cflib/vocab.py`
imports nothing from the format (section 5).

```python
"""Put ``vendor/`` on ``sys.path``, so the vendored annotation format imports.

New code, for the switchover to formal-companion-annotations (CLAUDE.md
section 2).  ``vendor/formal_companion_annotations/`` is one tagged release of
the format's own repository, copied byte for byte and sealed by
``vendor/formal_companion_annotations.manifest.json``
(``scripts/annotations/sync_format.py`` writes both; never edit them by hand).
A module that imports the format imports this first::

    from cflib import vendored  # noqa: F401  (vendor/ on sys.path)
    from formal_companion_annotations import ids

``vendor/`` goes FIRST on the path, so the vendored release is the one that
runs even where some other copy of the package is installed: the skill's
behaviour is pinned by its tree, not by the machine.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: The skill checkout's ``vendor/`` directory.
VENDOR = Path(__file__).resolve().parents[2] / "vendor"

if str(VENDOR) not in sys.path:
    sys.path.insert(0, str(VENDOR))
```

### 2.4 The sync script

`scripts/annotations/sync_format.py`, new, run by the maintainer by path. It
reads the release from a local checkout of this repository through
`cflib.gitsafe` (so `tests/test_rf_gate.py`'s bare-git check holds), from the
tag and never the working tree, checks every file against the tag's blob id
and the package's `__version__` against the tag, and then replaces
`vendor/formal_companion_annotations/` and the manifest together.

```python
"""Vendor one tagged release of formal-companion-annotations into vendor/.

New code, for the switchover to formal-companion-annotations (CLAUDE.md
section 2).  The annotation format is its own repository; the skill carries
one release's package under ``vendor/formal_companion_annotations/`` and a
sealed manifest beside it, ``vendor/formal_companion_annotations.manifest.json``:
the upstream URL, the tag, the commit it names, the version, and the sha256 of
every vendored file.  ``tests/test_vendored_format.py`` fails on any byte that
differs from the manifest, so the copy is never edited here: a change to the
format is a release upstream, then this script, then the skill's own changes.

Run by the maintainer, by path, against a local checkout of the upstream
repository that has the tag::

    python3 scripts/annotations/sync_format.py <formal-companion-annotations checkout> v1.0.0

It copies the package as the tag has it (``git ls-tree`` and ``git cat-file``
through :mod:`cflib.gitsafe`, never the checkout's working tree), checks each
file against the tag's blob id, checks that the package's ``__version__`` is
the tag's, and then replaces the vendored tree and the manifest.  ``--check``
changes nothing: it exits 1 unless the vendored tree matches the manifest and
the manifest matches the tag in the checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from cflib import gitsafe                                           # noqa: E402

SKILL = _SCRIPTS.parent
VENDOR = SKILL / "vendor"
PACKAGE = "formal_companion_annotations"
TARGET = VENDOR / PACKAGE
MANIFEST = VENDOR / f"{PACKAGE}.manifest.json"
UPSTREAM = "https://github.com/mathlib-initiative/formal-companion-annotations"
#: Where the package sits in the upstream tree.
SOURCE = f"src/{PACKAGE}"
_TAG = re.compile(r"v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)")
_VERSION = re.compile(r'^__version__ = "([^"]+)"$', re.M)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob_id(data: bytes) -> str:
    """The git blob id of ``data``, as ``git hash-object`` computes it."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def vendored_files(root: Path = TARGET) -> dict[str, str]:
    """``{path relative to the package: sha256}`` of every vendored file, bytecode left out."""
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and "__pycache__" not in rel.parts and path.suffix != ".pyc":
            out[rel.as_posix()] = sha256(path.read_bytes())
    return out


def git(checkout: Path, *args: str) -> str:
    proc = gitsafe.run(checkout, list(args))
    if proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed in {checkout}: {proc.stderr.strip()}")
    return proc.stdout


def release(checkout: Path, tag: str) -> tuple[str, dict[str, bytes]]:
    """The commit ``tag`` names and the package's files at it, each checked against its blob id."""
    if _TAG.fullmatch(tag) is None:
        raise SystemExit(f"{tag}: not a release tag (vMAJOR.MINOR.PATCH)")
    if git(checkout, "cat-file", "-t", f"refs/tags/{tag}").strip() != "tag":
        raise SystemExit(f"{tag}: not an annotated tag in {checkout}")
    commit = git(checkout, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}").strip()
    files: dict[str, bytes] = {}
    for line in git(checkout, "ls-tree", "-r", "--full-tree", commit, "--", SOURCE).splitlines():
        meta, path = line.split("\t", 1)
        mode, kind, oid = meta.split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise SystemExit(f"{path}: not a regular file at {tag}")
        data = git(checkout, "cat-file", "blob", oid).encode("utf-8")
        if blob_id(data) != oid:
            raise SystemExit(f"{path}: the bytes read back are not the blob {oid} (not UTF-8 text?)")
        files[path[len(SOURCE) + 1:]] = data
    if not files:
        raise SystemExit(f"{SOURCE}/ is empty at {tag}")
    found = _VERSION.search(files["__init__.py"].decode("utf-8"))
    version = _TAG.fullmatch(tag)["version"]
    if found is None or found.group(1) != version:
        raise SystemExit(f"{tag}: the package says __version__ {found and found.group(1)!r}, not {version!r}")
    return commit, files


def manifest_for(tag: str, commit: str, files: dict[str, bytes]) -> dict:
    return {
        "upstream": UPSTREAM,
        "tag": tag,
        "commit": commit,
        "version": _TAG.fullmatch(tag)["version"],
        "source": SOURCE,
        "license": "Apache-2.0",
        "files": {rel: sha256(data) for rel, data in sorted(files.items())},
    }


def write(manifest: dict, files: dict[str, bytes]) -> None:
    VENDOR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=VENDOR) as tmp:
        staged = Path(tmp) / PACKAGE
        for rel, data in files.items():
            (staged / rel).parent.mkdir(parents=True, exist_ok=True)
            (staged / rel).write_bytes(data)
        if vendored_files(staged) != manifest["files"]:
            raise SystemExit("the staged copy does not match its own manifest")
        if TARGET.exists():
            shutil.rmtree(TARGET)
        staged.rename(TARGET)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vendor a formal-companion-annotations release.")
    parser.add_argument("checkout", type=Path, help="a local checkout of formal-companion-annotations")
    parser.add_argument("tag", help="the release tag, vMAJOR.MINOR.PATCH")
    parser.add_argument("--check", action="store_true",
                        help="change nothing; exit 1 unless vendor/ is exactly this release")
    args = parser.parse_args(argv)
    commit, files = release(args.checkout.resolve(), args.tag)
    manifest = manifest_for(args.tag, commit, files)
    if args.check:
        current = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else None
        ok = current == manifest and vendored_files() == manifest["files"]
        print(f"vendor/{PACKAGE}: {'is' if ok else 'is NOT'} {args.tag} ({commit[:12]})")
        return 0 if ok else 1
    write(manifest, files)
    print(f"vendor/{PACKAGE}: {args.tag} ({commit[:12]}), {len(files)} files; "
          f"now run the suite and commit vendor/ with the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Then:

```sh
git clone https://github.com/mathlib-initiative/formal-companion-annotations <checkout>
python3 scripts/annotations/sync_format.py <checkout> v1.0.0
python3 scripts/annotations/sync_format.py <checkout> v1.0.0 --check   # "is v1.0.0 (<commit>)"
```

## 3. Delete

| path | why |
|---|---|
| `schema/annotations-v1.schema.json` (and `schema/`) | the vendored package carries it, as `vendor/formal_companion_annotations/schema/` |
| `examples/annotations/*.json` (and `examples/`) | they live in this repository now, with their tests |
| `scripts/annotations/ids.py` | `formal_companion_annotations.ids` |
| `scripts/annotations/schemacheck.py` | `formal_companion_annotations.schemacheck` |
| `scripts/annotations/validate.py` | `formal_companion_annotations.validate` |
| `tests/test_annotations_schema.py` | this repository's `tests/test_annotations_schema.py` |
| `scripts/cflib/vocab.py` lines 200-330 | the "annotation documents" block, from `# --- annotation documents` through `PASSAGE_PAGE_ID_PATTERN`, and the blank line 331 after it; section 5 |

Keep `scripts/annotations/__init__.py`, `scripts/annotations/review_tags.py`
and `scripts/annotations/export/`: they are the skill's tooling that produces
and reads documents. Replace the `__init__.py` docstring (it names the three
deleted modules and the schema path) with:

```python
"""The skill's tooling around the annotation format: exporters and the tag review.

``export`` holds the companion exporters behind ``cf export`` and
``review_tags`` the tag review behind ``cf review-tags``.  The format itself
(its schema, checker, id rules and vocabulary) is the vendored
``formal_companion_annotations`` package under ``vendor/``, imported through
:mod:`cflib.vendored`; its specification is formal-companion-annotations'
docs/annotations.md.
"""
```

**`docs/annotations.md`: replace, do not delete.** Once the files above are
gone, 45 lines in 19 files of the skill still cite it, mostly by section
number, from docs, code docstrings and exporter error messages
(`scripts/annotations/export/attribution_table.py` lines 359 and 372):
`git grep -c 'docs/annotations.md' -- ':!vendor' ':!docs/annotations.md'`.
Replace its body with a stub that cites no path from the table above, or
section 6's tests fail on it:

```markdown
# Annotation documents: `lean-companion/annotations`

The annotation format's specification moved to its own repository,
formal-companion-annotations
(`github.com/mathlib-initiative/formal-companion-annotations`), as
`docs/annotations.md` there. Every section number this repository cites is
that document's; the numbers are unchanged.

The skill carries one tagged release of the format's package under `vendor/`
(its manifest names the release) and imports it through `cflib.vendored`.
```

## 4. Change imports

Every site, exactly. In each file, the bootstrap line
`from cflib import vendored  # noqa: F401  (vendor/ on sys.path)` goes on its
own line directly above the file's first format import (with `E402,F401` in
the `noqa` where the file's imports already carry `E402`: `common.py` and the
three tests).

| file | line(s) | from | to |
|---|---|---|---|
| `scripts/annotations/export/common.py` | 42 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `scripts/annotations/export/common.py` | 43 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `scripts/annotations/export/docstring_tags.py` | 46 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `scripts/annotations/export/docstring_tags.py` | 47 | `from annotations.validate import site_sha256` | `from formal_companion_annotations.validate import site_sha256` |
| `scripts/annotations/export/docstring_tags.py` | 49 | `from cflib import vocab, yamlio` | `from cflib import yamlio` and `from formal_companion_annotations import vocab` |
| `scripts/annotations/export/attribution_table.py` | 38 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `scripts/annotations/export/attribution_table.py` | 40 | `from cflib import vocab` | `from formal_companion_annotations import vocab` |
| `scripts/cfcmd/export.py` | 27 | `from annotations import validate as V` | the bootstrap, then `from formal_companion_annotations import validate as V` |
| `scripts/cfcmd/review_tags.py` | 23 | `from annotations import validate as V` | the bootstrap, then `from formal_companion_annotations import validate as V` |
| `scripts/pipeline/document.py` | 19 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `scripts/pipeline/document.py` | 20 | `from annotations import validate as annotations_validate` | `from formal_companion_annotations import validate as annotations_validate` |
| `scripts/pipeline/document.py` | 21 | `from cflib import vocab` | `from formal_companion_annotations import vocab` |
| `scripts/pipeline/inventory.py` | 47 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `scripts/pipeline/inventory.py` | 48 | `from annotations.validate import loads` | `from formal_companion_annotations.validate import loads` |
| `scripts/pipeline/recall.py` | 28 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `tests/test_export.py` | 62 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `tests/test_export.py` | 63 | `from annotations import validate as V` | `from formal_companion_annotations import validate as V` |
| `tests/test_review_tags.py` | 38 | `from annotations import validate as V` | the bootstrap, then `from formal_companion_annotations import validate as V` |
| `tests/test_m1_source_side.py` | 49 | `from annotations import ids` | the bootstrap, then `from formal_companion_annotations import ids` |
| `tests/test_m1_source_side.py` | 116-117 | `[sys.executable, str(SCRIPTS / "annotations" / "validate.py"),` ... `capture_output=True, text=True)` | `[sys.executable, "-m", "formal_companion_annotations.validate",` ... `capture_output=True, text=True, env={**os.environ, "PYTHONPATH": str(vendored.VENDOR)})`: the one place the skill runs the checker as a command, in `validate_cli`. The child process has no bootstrap, so it is given `vendor/` on its path; a `git grep` for the old path misses the line, since it is built with `/` |

The three `vocab` rows are safe because those modules use only annotation
constants from it (`ANNOTATION_SCHEMA`, `ANNOTATION_SCHEMA_VERSION`,
`CONFORMS_TO_PDF`, `CONFORMS_TO_HTML`), which the package defines with the
same values. No other skill module uses a constant from the deleted block
(`git grep -E "vocab\.(ANNOTATION_|CONFORMS_TO_|HASH_ID|DECLARED_|PASSAGE_|ANONYMOUS_)"`
finds only these three files and the deleted ones).

Unchanged and still needed: `from annotations import review_tags`,
`from annotations.export import ...`, `from annotations.export.common import
read_bytes`, and the `sys.path` insert of `scripts/` in
`scripts/annotations/export/common.py` (lines 39-40, for `cflib`, which the
bootstrap needs too). The skill's own `annotations` package and
`formal_companion_annotations` do not collide.

Docstrings that name the old modules, to rename in the same pass (nothing
fails on them, since they carry no file extension): ``annotations.ids`` in
`scripts/annotations/export/common.py` (lines 22 and 340),
`scripts/annotations/export/attribution_table.py` (line 19) and
`scripts/annotations/export/docstring_tags.py` (lines 13-14, with
``annotations.validate``), and `(annotations.ids)` in `docs/exporters.md`
line 42: each becomes the `formal_companion_annotations` name.

## 5. Vocabulary

CLAUDE.md section 4's first rule (line 94, "`scripts/cflib/vocab.py` is the
only definition of the enums") gains an exception, appended to that bullet:

> The exception is the annotation format: its enums, and nine sets it shares
> with the skill, are defined by the vendored
> `formal_companion_annotations.vocab`; `cflib.vocab` keeps copies of the nine
> for the skill's stages, and `tests/test_vendored_format.py` checks that they
> equal the format's.

The format **owns** every value it uses, including nine sets it shares with
the skill, where they were first written: `VIEWER_VERDICTS`,
`VIEWER_SEVERITIES`, `VIEWER_STATUS`, `LEDGER_VERDICTS`, `FINDING_KINDS`,
`SOURCE_ROLES`, `SORRY_CLASSES`, `STATIC_RESOLUTIONS` and
`RESOLUTION_PREFIXES` (`ANNOTATION_RESOLUTION_STATES` is derived from the last
two). The package defines their values, and
`formal-companion-annotations/docs/vocabulary.md` section 2 a meaning for
each; the skill, like any producer, conforms. It keeps its own literal copies
in `cflib.vocab`, because its stages (findings, the ledger, the viewer,
sources) use them, and `cflib.vocab` imports nothing from the format:
`cflib` is imported by everything, the bootstrap included. A change to one of
them starts in the format: a release (a new minor version for a new value, a
new major version for a value removed or given another meaning), then the
sync (section 11), then the skill's copy. Section 8's test fails until the
skill's copies agree with the release it vendors.

**`references/vocabulary.md` section 1.10** (lines 178-226, up to the blank
line and the `---` before section 2): keep the heading, so "section 1.10"
citations stay true, and replace the body (lines 179-226) with:

```markdown
The annotation enums are defined in the vendored `formal_companion_annotations.vocab`
(`vendor/formal_companion_annotations/vocab.py`, one release of formal-companion-annotations)
and documented, value by value, in `formal-companion-annotations/docs/vocabulary.md`. The nine
sets sections 1.2, 1.4, 1.5, 1.6 and 1.7 and `SORRY_CLASSES` document for the skill's stages
(`VIEWER_VERDICTS`, `VIEWER_SEVERITIES`, `VIEWER_STATUS`, `LEDGER_VERDICTS`, `FINDING_KINDS`,
`SOURCE_ROLES`, `SORRY_CLASSES`, `STATIC_RESOLUTIONS`, `RESOLUTION_PREFIXES`) are the format's,
defined with their meanings in that file's section 2; `cflib.vocab` keeps copies for the stages,
and those sections of this document must agree with the format. `tests/test_vendored_format.py`
checks that the values do.
```

The `formal-companion-annotations/` prefix matters: a bare `docs/vocabulary.md`
in backticks is read as the skill's own path and fails section 6's tests.
The contents paragraph (lines 12-15) still fits; update it if the wording of
the section title changes.

## 6. Citations the skill's doc tests will catch

`tests/test_rf_scrub.py` (`TestNoCitationOfAFileThatIsNotHere`) scans every
tracked file for a token that starts with one of its `REPO_ROOTS` and ends in
a file extension, and fails when the file is missing;
`tests/test_rf_docs.py` does the same for backticked paths in the docs.

**The vendored tree is another repository's.** Its modules cite paths of
this repository (`schema/annotations-v1.schema.json`, `docs/vocabulary.md`,
`tests/test_annotations_schema.py`) and the skill's former
`scripts/annotations/ids.py`, and the manifest's file list names
`schema/annotations-v1.schema.json`: 8 citations in 5 files under `vendor/`
that do not resolve in the skill, and that cannot be edited without breaking
the seal. In
`tests/test_rf_scrub.py`, after `ARCHIVE = "docs/design/archive/"` (line
266), add

```python

#: `vendor/` is another repository's tree, copied byte for byte from a tagged
#: release of formal-companion-annotations: the paths it cites are paths in
#: THAT tree, and `tests/test_vendored_format.py` pins its bytes, so it can be
#: neither checked against this tree nor edited to pass.
VENDORED = "vendor/"
```

and in `test_every_repo_path_a_tracked_file_cites_resolves` (line 292) make
line 295, `if rel.startswith(ARCHIVE):`, read
`if rel.startswith((ARCHIVE, VENDORED)):`.
The machine-local rules of the same file still scan `vendor/`, and pass on
it. `tests/test_rf_docs.py` reads only the docs, so it needs no exemption.

After section 3, each of these fails until it is rewritten. Name the file in
its new home with a `formal-companion-annotations/` prefix (the prefix is not
a repo root, so it is not checked as a path here), or name the module:

| file | line | now | becomes |
|---|---|---|---|
| `.github/workflows/tests.yml` | 14 | `scripts/annotations/schemacheck.py` | the bullet (lines 14-16) is replaced (section 9) |
| `.github/workflows/tests.yml` | 57 | `tests/test_annotations_schema.py` | dropped, with the jsonschema step (section 9) |
| `CHANGELOG.md` | 154 | `schema/annotations-v1.schema.json` | `formal-companion-annotations/schema/annotations-v1.schema.json` |
| `CHANGELOG.md` | 168 | `scripts/annotations/validate.py` | `formal-companion-annotations/src/formal_companion_annotations/validate.py` |
| `docs/pipeline.md` | 25 | `scripts/annotations/validate.py --canonical` | the vendored checker (`PYTHONPATH=vendor python3 -m formal_companion_annotations.validate --canonical`) |
| `docs/proposals/pdf-to-companion.md` | 72 | `schema/annotations-v1.schema.json`, `scripts/annotations/validate.py` | the `formal-companion-annotations/` forms above |
| `docs/proposals/pdf-to-companion.md` | 204 | `schema/annotations-v1.schema.json` | `formal-companion-annotations/schema/annotations-v1.schema.json` |
| `docs/proposals/pdf-to-companion.md` | 878 | `scripts/annotations/validate.py` | `formal_companion_annotations.validate` |
| `references/vocabulary.md` | 180-181 | `schema/annotations-v1.schema.json`, `tests/test_annotations_schema.py` | rewritten with section 1.10 (section 5) |
| `scripts/pipeline/document.py` | 5 | ``scripts/annotations/validate.py --canonical`` | ``formal_companion_annotations.validate --canonical`` |
| `scripts/annotations/__init__.py` | 4 | `schema/annotations-v1.schema.json` | rewritten (section 3) |
| `scripts/cflib/vocab.py` | 200, 316-317 | the block's own comments | deleted with the block |

The CHANGELOG lines are history; rewriting the path, not the entry, keeps the
record and passes the test. `REPO_ROOTS` in both tests can keep `"schema/"`
and `"examples/"`: with the directories gone, any later citation of them
fails, which is the point. Rewrap the lines these edits lengthen.

Then this prints nothing (the leading class skips the prefixed forms, which
contain the old paths, and `vendor/` is left out; it printed nothing on the
dry run of section 10):

```sh
git grep -nE "(^|[^-/a-z_])(schema/annotations-v1\.schema\.json|scripts/annotations/(validate|ids|schemacheck)\.py|tests/test_annotations_schema\.py|examples/annotations/)" -- ':!vendor'
```

## 7. Prose

- `CLAUDE.md` section 2, the layout block: replace the `schema/` and
  `examples/` lines (40-42) with a `vendor/` entry
  ("`formal_companion_annotations/`: one release of the annotation format
  (formal-companion-annotations), byte for byte, sealed by its manifest;
  never edited here"), add `vendored` to the `scripts/cflib/` list (line
  48), and rewrite the `scripts/annotations/` entry (52-55): it now holds
  `export/` (`cf export`), `review_tags.py` (`cf review-tags`) and
  `sync_format.py`, and the format itself is
  `vendor/formal_companion_annotations/`.
- `CLAUDE.md` section 3, the first bullet (lines 70-73): after "Do not add a
  dependency without changing this paragraph.", say that `vendor/` is not
  one: it holds one release of formal-companion-annotations, itself standard
  library only, copied into the tree (section 2), so a clone still runs with
  nothing installed.
- `README.md`, the layout block: the same for its `schema/` and `examples/`
  lines (41-44) and its `scripts/annotations/` entry (55-58).
- `CHANGELOG.md`: a new entry saying the format moved to
  formal-companion-annotations 1.0.0 (schema, spec, checker, id rules,
  examples and their tests), that the skill vendors it under `vendor/` with a
  manifest and a test that fails on drift, that the checker's behaviour is
  unchanged, and that the schema's `$id` is now the package's (the raw URL
  of the schema at `v1.0.0`). Bump `scripts/cflib/__init__.py`
  `__version__` (line 20) and `pyproject.toml` `version` (line 25) together
  if this is released.
- `SKILL.md` line 210 cites `docs/annotations.md`, which the stub keeps; no
  change needed.
- The test gate: no change. `python3 -m unittest discover -s tests` still
  needs nothing installed, so `CONTRIBUTING.md` (lines 10-18, 73-74, 110),
  `README.md` (lines 364-381), `CLAUDE.md` section 7 (line 221) and
  `docs/adding-an-adapter.md` (line 110) stay as they are.

**Prose that names the old `validate.py`.** No test fails on these, since
none cites a path under one of the doc tests' repository roots, but each
names a command that no longer exists once section 3's deletions land. The
skill has no console script for the vendored checker, so prose names the
module, `formal_companion_annotations.validate`:

| file | line | now | becomes |
|---|---|---|---|
| `scripts/pipeline/document.py` | 150 | docstring: a checkpoint that ``validate.py --canonical`` would reject | ``formal_companion_annotations.validate --canonical`` |
| `scripts/pipeline/document.py` | 157 | the `CfError` message a user sees when a stage builds a bad checkpoint: "the document does not pass validate.py --canonical: ..." | "... does not pass formal_companion_annotations.validate --canonical: ..." (keep the rest of the message) |
| `scripts/pipeline/inventory.py` | 36 | docstring: the gates of ``pipeline/source_gates.py``, ``validate.py --canonical``, ... | ``formal_companion_annotations.validate --canonical`` |
| `docs/proposals/pdf-to-companion.md` | 240 | "The document passes `validate.py --canonical`." | `formal_companion_annotations.validate --canonical` |
| `docs/proposals/pdf-to-companion.md` | 778 | "CI gate: `validate.py --canonical`; ..." | the same |
| `docs/proposals/pdf-to-companion.md` | 878 | the first column, `validate.py --canonical` (the third is in section 6's table) | the same |
| `docs/proposals/pdf-to-companion.md` | 999 | "1. `validate.py --canonical`." | the same |
| `docs/proposals/pdf-to-companion.md` | 1182 | "passes `validate.py --canonical` with no warnings" | the same |

One more line goes stale with this repository's `docs/annotations.md` section
11, which lists the skill's producers and readers:
`docs/proposals/pdf-to-companion.md` lines 94-95, "No producer or consumer
reads or writes the annotation format yet; only the checker does
(`docs/annotations.md` section 11)". Rewrite it to say which of the skill's
commands write and read documents (`cf export`, `cf ingest`, `cf inventory`,
`cf review-tags`), citing that section.

## 8. The skill's test of the vendored copy

`tests/test_vendored_format.py`, new. It fails on any vendored byte that
drifts from the manifest (a file changed, added or removed), on a manifest
that names no release, on a module under `scripts/` or `tests/` that imports
the format before the bootstrap, and on a shared set whose copy in
`cflib.vocab` is not the format's:

```python
"""The vendored annotation format is exactly the release its manifest names.

New code, for the switchover to formal-companion-annotations (CLAUDE.md
sections 2 and 4).  ``vendor/formal_companion_annotations/`` is one tagged
release of the format's repository, and
``vendor/formal_companion_annotations.manifest.json`` seals it: the upstream,
the tag, the commit, the version and the sha256 of every file.  Any vendored
byte that differs from the manifest, a file added or removed, fails here; so
does a module that imports the format without the ``cflib.vendored``
bootstrap, and a shared set whose copy in ``cflib.vocab`` is not the format's.
A change to the format starts upstream (a release), then
``scripts/annotations/sync_format.py``, then our copy.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
SCRIPTS = SKILL / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from cflib import vendored, vocab                                  # noqa: E402
import formal_companion_annotations as fmt_package                  # noqa: E402
from formal_companion_annotations import vocab as fmt               # noqa: E402

VENDOR = SKILL / "vendor"
PACKAGE = VENDOR / "formal_companion_annotations"
MANIFEST = VENDOR / "formal_companion_annotations.manifest.json"
UPSTREAM = "https://github.com/mathlib-initiative/formal-companion-annotations"

SHARED = ("VIEWER_VERDICTS", "VIEWER_SEVERITIES", "VIEWER_STATUS", "LEDGER_VERDICTS",
          "FINDING_KINDS", "SOURCE_ROLES", "SORRY_CLASSES", "STATIC_RESOLUTIONS",
          "RESOLUTION_PREFIXES")


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def on_disk() -> dict[str, str]:
    out = {}
    for path in sorted(PACKAGE.rglob("*")):
        rel = path.relative_to(PACKAGE)
        if path.is_file() and "__pycache__" not in rel.parts and path.suffix != ".pyc":
            out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class TestTheVendoredBytesAreTheRelease(unittest.TestCase):

    def test_the_manifest_names_a_release(self):
        m = manifest()
        self.assertEqual(set(m), {"upstream", "tag", "commit", "version", "source", "license", "files"})
        self.assertEqual(m["upstream"], UPSTREAM)
        self.assertRegex(m["tag"], r"^v[0-9]+\.[0-9]+\.[0-9]+$")
        self.assertEqual(m["tag"], f"v{m['version']}")
        self.assertRegex(m["commit"], r"^[0-9a-f]{40}$")
        self.assertEqual(m["source"], "src/formal_companion_annotations")

    def test_no_vendored_byte_drifts_from_the_manifest(self):
        self.assertEqual(on_disk(), manifest()["files"],
                         "vendor/ is not the release its manifest names; rerun "
                         "scripts/annotations/sync_format.py instead of editing it")

    def test_the_vendored_version_is_the_manifests(self):
        self.assertEqual(fmt_package.__version__, manifest()["version"])

    def test_the_bootstrap_imports_the_vendored_copy(self):
        self.assertEqual(vendored.VENDOR, VENDOR)
        self.assertIn(str(VENDOR), sys.path)
        self.assertEqual(Path(fmt_package.__file__).resolve().parent, PACKAGE.resolve())


class TestEveryImportGoesThroughTheBootstrap(unittest.TestCase):

    def test_the_bootstrap_comes_before_the_format(self):
        """A module that imports the format first would find it only by luck of import order."""
        offenders = []
        for path in sorted([*SCRIPTS.rglob("*.py"), *(SKILL / "tests").glob("*.py")]):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = sorted((n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))),
                             key=lambda n: (n.lineno, n.col_offset))
            booted = False
            for node in imports:
                if isinstance(node, ast.ImportFrom) and node.module == "cflib" \
                        and any(a.name == "vendored" for a in node.names):
                    booted = True
                names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(n.split(".")[0] == "formal_companion_annotations" for n in names) and not booted:
                    offenders.append(f"{path.relative_to(SKILL)}:{node.lineno}")
        self.assertEqual(offenders, [], "import `from cflib import vendored` first")


class TestTheFormatAgrees(unittest.TestCase):
    """The format owns nine sets that cflib.vocab also holds; our copies must equal its."""

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
        self.assertEqual(manifest()["version"].split(".")[0], str(fmt.ANNOTATION_SCHEMA_MAJOR))


if __name__ == "__main__":
    unittest.main()
```

It builds no workspace, so it needs no `_hermetic` import
(`tests/test_rf_final_tests.py` only requires that of modules that do).

## 9. CI

In `.github/workflows/tests.yml`, nothing is installed for the format:

- **The header comment's third bullet** (lines 14-16, the in-repo JSON
  Schema evaluator against `jsonschema`) goes; in its place:

  ```yaml
  #   * the vendored annotation format (vendor/, CLAUDE.md S2): every job runs
  #     tests/test_vendored_format.py, so a vendored byte that is not the
  #     release its manifest names fails everywhere; nothing is installed for it.
  ```

- **`pytest` (the 3.11/3.12/3.13 matrix)**: delete the jsonschema step
  (lines 56-60, its comment and the `if: matrix.python-version == '3.13'`
  install). The only tests that used it, `TestAgreementWithJsonschema`,
  moved to this repository, whose own CI runs them.
- **`pytest-no-pyyaml`**, **`unittest`**, **`registry`** and
  **`synthetic-e2e`**: no change. The vendored package is in the checkout,
  so each job already has it, and the `unittest` job (line 90, "the command
  CLAUDE.md documents") still runs exactly the documented gate.

## 10. Checking the result

**Dry run.** Sections 2 to 9 (the code of sections 2 and 8 exactly as
printed here, the prose of section 7's layout blocks and CLAUDE.md sections
3 and 4, and its prose table) were applied to a scratch clone of the skill
at `d4deedb` (never to the skill itself), with `vendor/` written by the sync
script from a local checkout of this repository at a scratch `v1.0.0` tag.
The CHANGELOG entry of section 7 was not written. The skill's full suite,
with PyYAML installed:

| | `pytest` passed | skipped | failed | `unittest discover` |
|---|---|---|---|---|
| before, at `d4deedb` | 2230 | 201 | 0 | 2396 tests, OK (skipped 173) |
| after | 2105 | 201 | 0 | 2271 tests, OK (skipped 173) |

2105 is 2230, less the 133 tests of `tests/test_annotations_schema.py`,
which moved here, plus the 8 of section 8. With `vendor/` untracked the
first run was green; once it was tracked, one test failed,
`test_every_repo_path_a_tracked_file_cites_resolves`, on the 8 citations of
section 6's first paragraph, which is how the `VENDORED` exemption got into
this document. The citations of section 6's table, `validate_cli`'s
`PYTHONPATH` (section 4) and the path prefix of section 5 were written before
that run, from the previous edition of this document, whose dry run found
them. Changing one byte of a vendored file failed
`test_no_vendored_byte_drifts_from_the_manifest`; restoring it and running
`sync_format.py --check` printed "is v1.0.0". `python3 scripts/cf.py --help`
listed `export`, `ingest`, `inventory` and `review-tags`, `python3
scripts/pipeline/derive_truth.py --help` ran, and the stale-path `git grep`
of section 6 printed nothing.

In the skill:

```sh
python3 scripts/annotations/sync_format.py <checkout> v1.0.0
git add vendor scripts tests
python3 -m pytest -q tests/                      # 2105 passed, 201 skipped at d4deedb
python3 -m unittest discover -s tests            # the documented gate, nothing installed
python3 scripts/cf.py --help                     # export, ingest, inventory, review-tags listed
PYTHONPATH=vendor python3 -m formal_companion_annotations.validate --canonical <document.json>
```

The `git add` comes before the suite because `tests/test_rf_scrub.py` reads
only tracked files. The exporter reference tests (`tests/test_export.py`,
with `CF_M3_REFERENCE_DIR` and the pinned checkouts) should reproduce the
reference documents byte for byte, since the canonical writer and the id
rules are unchanged; the dry run could not run them (they skip without the
maintainer's references).

## 11. The next release

When this repository tags a new release `vX.Y.Z`:

1. `python3 scripts/annotations/sync_format.py <checkout> vX.Y.Z`: it
   replaces `vendor/formal_companion_annotations/` and the manifest together.
2. Read this repository's `CHANGELOG.md` for the release. A patch changes no
   document the spec admits, but a patch that makes the checker refuse a
   document the spec always forbade is called out there: run the exporters
   and the pipeline tests against it. A minor adds optional keys or values;
   the skill's writers keep declaring the `schema_version` minor they write
   (`vocab.ANNOTATION_SCHEMA_VERSION` of the release they were written
   against), and move it only when they use a new key. A major (`2.0.0`)
   reads only `"2.*"` documents and needs the exporters and the pipeline
   changed with it.
3. If a shared set changed, update `cflib.vocab`'s copy and
   `references/vocabulary.md` to match; section 8's test fails until they
   do.
4. Run the suite, and commit `vendor/` and the manifest in one commit, with
   the skill changes the release needs, naming the tag.
