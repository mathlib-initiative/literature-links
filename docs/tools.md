# Literature Links tools

The `literature_links` package checks annotations offline and reads them from
files. It needs Python 3.11 or newer and nothing else. The format is defined in
[companion.md](companion.md); this page documents the checker, its Python API,
the command line and how files are found and read.

## Python API

`companion` checks one annotation:

- `check(document)` returns a `Report` whose `problems` are
  `Problem(code, path, message)` items with the codes `JSON`, `SCHEMA`,
  `PDF_RECT` and `LINES`. Any problem makes the annotation invalid.
  `PDF_RECT` and `LINES` are checked in each end, subject first, only when the
  schema finds nothing, and name the end, as in `$.subject[1].location.rect`.
  `warnings` is always empty.
- `validate(document)` returns the problems as `path: message` strings.
- `loads(text)` only parses. It keeps integers exact and reads other numbers as
  floats. It raises `LoadError`, a `ValueError`, for duplicate keys, NaN and
  Infinity, unpaired surrogates, overflow and nonzero underflow.
- `dumps(value)` keeps key order and writes two-space indentation and a final
  newline.
- `merge(inherited, written, *, defaults=False)` and `rebase(value, base)`
  implement [folder defaults](companion.md#folder-defaults). Where `inherited`
  holds an end template and `written` a list of ends, `merge` merges the
  template into each end that has no `uri` member, and a `location` on the end
  replaces the template's whole. Ends with their own `uri` and items that are
  not objects are kept as written. `merge` reads `written` as a record, so a
  side it leaves out gets the end template alone. With `defaults=True`,
  `written` is another defaults file, and end templates stay objects. `rebase`
  rewrites `$schema` and each end's `uri` and `location.profile`, in end
  templates and lists of ends; `citation` and `extensions` are left as they
  are.
- `load_schema()` reads the bundled schema at `SCHEMA_PATH`.

Every record has one shape, so 2.0 has no `normalize`. Nothing checks
uniqueness across annotations.

`discovery` reads annotations from files and folders, as in
[Discovery](#discovery):

- `collect(paths, *, include=None, exclude=())` returns a `Collection` of
  `records`, `problems` and the `files` read. Valid records are kept when other
  files fail, so check `problems` first. Each argument is a list: one string
  raises `TypeError`.
- A `Record(annotation, path, *, line=None, defaults=())` holds the
  `annotation` with its folder defaults applied, its file `path`, its `line` in
  a JSONL file (None in a JSON file), the `defaults` files applied, outermost
  first, and the `base_uri` that its relative references resolve against.
- `inherit(annotation, path)` applies the folder defaults that cover the file
  `path` to a record read from it. It returns the merged annotation or None,
  the defaults files applied, and the problems.
- `DEFAULTS` is the file name of folder defaults, `_defaults.json`.
- Reading adds the codes `IO`, `JSON`, `PATH`, `SYMLINK`, `SHAPE`, `DEFAULTS`
  and `NO_ANNOTATIONS` to those of `check`.

`schemacheck` is the JSON Schema evaluator that `check` runs, not a general
JSON Schema implementation. `Validator(schema)` raises `SchemaError`, a
`ValueError`, for what it does not implement; `errors(value)` returns
`(path, message)` pairs and `is_valid(value)` a bool. `cli.main(argv)` runs the
command line and returns its exit status.

```python
from literature_links import companion, discovery
problems = companion.validate({"subject": [{"type": "generic", "uri": "a"}], "object": []})
collection = discovery.collect(["examples/companion"])  # check .problems before .records
```

## Command line

```sh
literature-links validate FILE... [--format text|json]
literature-links scan PATH... [--include PATTERN]... [--exclude PATTERN]... [--format text|json]
literature-links --version
```

`validate` checks each file with its folder defaults applied: a JSONL file one
annotation per line, as in [Discovery](#discovery), and any other file as one
annotation. It exits 0 when every file is valid, 1 for an invalid annotation,
file shape or defaults file, and 2 for a read, JSON, path or symlink failure,
or a JSONL file with no annotations. A `_defaults.json` named directly is a
problem: it is not an annotation.

`scan` reads annotations from files and folders, as in [Discovery](#discovery).
It exits 0 when it finds annotations and no problems. It exits 1 for an invalid
annotation, file shape or defaults file. It exits 2 for a read, JSON, path or
symlink failure, or when it finds no annotations.

In text, `validate` prints a line for each valid file that counts its
annotations and lists each type of end once, subject ends first, such as
`latex.json: ok (1 annotation, latex, lean)`, and a line for each problem.
`scan` prints each problem and then a summary, such as
`3 annotations from 2 files; 0 problems`.

For both, status 2 wins over 1, and a usage error exits 2. `--format json`
writes machine-readable output: one report per input for `validate`, and one
report with the files, the records with their origins, and the problems for
`scan`. A problem's path in `scan` is the file, then `(line N)` for a JSONL
line, then the place in the annotation, such as `$.subject[0].location`; a
problem with the whole run, such as finding no annotations, has the path `$`,
which the text output leaves out. `validate` names the file first and gives a
JSONL line as `line N`. `--help` lists the options and the exit statuses.

## Discovery

`literature-links scan` and `discovery.collect` read annotations from local
files, and `literature-links validate` reads each file the same way. The
[specification](companion.md#discovery) says what a JSON and a JSONL document
carry; the rest is a reader convention.

| File | Annotations | Origin |
|---|---|---|
| JSON | One object | The file |
| JSONL or NDJSON | One object per nonblank line | Line number, from 1 |

- Files are UTF-8. A byte order mark is a `JSON` problem. A JSON file holds
  one annotation, an object. A JSON file
  that holds an array is a `SHAPE` problem: put several annotations in a
  `.jsonl` file. A JSONL line holds an object, not an array.
- In JSONL, CRLF, CR and LF each end a line; JSON Lines ends lines at LF
  only. U+2028 and U+2029 do not end a line. A line
  with only spaces and tabs is blank. Blank lines are skipped but still counted.
- Directories are walked recursively for `.json`, `.jsonl` and `.ndjson` files,
  ignoring case. A file named explicitly may have any suffix.
- `.jsonl` and `.ndjson` files are read by line. Other files are read as JSON.
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
