# Literature Links tools

The `literature_links` package checks annotations offline and reads them from
files. It needs Python 3.11 or newer and nothing else. The format is defined in
[companion.md](companion.md); this page documents the checker, its Python API,
the command line and how files and folders are read.

## Python API

`companion` checks one annotation:

- `check(document)` returns a `Report` whose `problems` are
  `Problem(code, path, message)` items with the codes `JSON`, `SCHEMA`,
  `PDF_RECT` and `LATEX_LINES`. Any problem makes the annotation invalid.
  `warnings` is always empty.
- `validate(document)` returns the problems as `path: message` strings.
- `loads(text)` only parses, and raises `LoadError`, a `ValueError`, for input
  that is not strict JSON. It keeps integers exact and reads other numbers as
  floats. It rejects overflow and nonzero underflow.
- `dumps(value)` keeps key order and writes two-space indentation and a final
  newline.
- `merge(inherited, written)` and `rebase(value, base)` implement
  [folder defaults](companion.md#folder-defaults).
- `normalize(annotation)` copies a record with a string `target` as
  `{"uri": ...}` and a string `status` as `{"value": ...}`, so readers handle
  one shape; it does not validate, and belongs after folder defaults are
  applied.
- `load_schema()` reads the bundled schema at `SCHEMA_PATH`.

Nothing checks uniqueness across annotations.

`discovery` reads annotations from files and folders, as in
[Discovery](#discovery):

- `collect(paths, include=None, exclude=())` returns a `Collection` of
  `records`, `problems` and the `files` read. Valid records are kept when other
  files fail, so check `problems` first.
- A `Record` holds the `annotation` with its folder defaults applied, its file
  `path`, its `pointer` and `line`, the `defaults` files applied, outermost
  first, and the `base_uri` that its relative references resolve against.
- `inherit(annotation, path)` applies the folder defaults that cover the file
  `path` to a record read from it.
- Reading adds the codes `IO`, `JSON`, `PATH`, `SYMLINK`, `SHAPE`, `DEFAULTS`
  and `NO_ANNOTATIONS` to those of `check`.

```python
from literature_links import companion, discovery
problems = companion.validate({"source": {"type": "generic", "uri": "a"}, "target": "b"})
collection = discovery.collect(["examples/companion"])  # check .problems before .records
```

## Command line

```sh
literature-links validate FILE...
literature-links scan PATH... [--include PATTERN]... [--exclude PATTERN]...
```

`validate` checks files that each hold one annotation, with their folder
defaults applied. It exits 0 when every file is valid, 1 for an invalid
annotation or defaults file, and 2 for a read, JSON, path or symlink failure. A
`_defaults.json` named directly is a problem: it is not an annotation.

`scan` reads annotations from files and folders, as in [Discovery](#discovery).
It exits 0 when it finds annotations and no problems. It exits 1 for an invalid
annotation, file shape or defaults file. It exits 2 for a read, JSON, path or
symlink failure, or when it finds no annotations.

For both, status 2 wins over 1. `--format json` writes machine-readable output:
one report per input for `validate`, and one report with the files, the records
with their origins, and the problems for `scan`.

## Discovery

`literature-links scan` and `discovery.collect` read annotations from local
files. This is a reader convention, not part of the format.

| File | Annotations | Origin |
|---|---|---|
| JSON object | One | Pointer `""` |
| JSON array | One per member | Pointer `/0`, `/1`, ... |
| JSONL or NDJSON | One per nonblank line | Line number, from 1 |

- Files are UTF-8. A JSONL line holds an object, not an array.
- In JSONL, CRLF, CR and LF each end a line. U+2028 and U+2029 do not. A line
  with only spaces and tabs is blank. Blank lines are skipped but still counted.
- Directories are walked recursively for `.json`, `.jsonl` and `.ndjson` files,
  ignoring case. A file named explicitly may have any suffix.
- `.jsonl` and `.ndjson` files are read by line. Other files are one JSON value.
- `--include` replaces the suffix filter, and `--exclude` always wins. Patterns
  are case-sensitive shell wildcards on the path relative to the root, or on
  the file name for a file named explicitly. `*` also matches `/`, and a
  leading `**/` also matches files in the root.
- Hidden directories are read. Symlinks are skipped while walking and are an
  error when named explicitly.
- A file named `_defaults.json` holds
  [folder defaults](companion.md#folder-defaults), not annotations. Every
  defaults file that covers a selected file applies, whatever `--include` and
  `--exclude` select, and a symlinked one is an error.
- Files are read in sorted path order, each resolved path once.
- Unrelated or malformed JSON in a selected file is reported, not skipped. Valid
  annotations from other files are still returned.
- Repeated `id` values and identical annotations are kept.

Scanning a repository root reads every JSON file under it, vendored and
generated ones included, and reports each one that is not an annotation as a
problem. Keep annotations in a directory of their own, or name them
`*.annotations.json` and select them with `--include '*.annotations.json'`.
