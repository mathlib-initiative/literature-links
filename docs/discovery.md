# Discovering a companion

A companion is a collection of [single annotations](companion.md) assembled by an
application. Authors choose where to keep them. The annotation schema imposes no
directory structure, collection manifest, shared header, or file naming rule.
This page describes the optional offline reader included in this package.

## Choose the files to read

The reader accepts individual files or recursively traverses selected directories:

```sh
formal-companion-annotations scan examples/companion/
formal-companion-annotations scan repo/ --include '*.annotations.json' --include '*.jsonl'
formal-companion-annotations scan first/ second/ --exclude 'generated/archive/*' --format json
```

Run the first command from this checkout; the other paths are illustrative.
It finds nine annotations in the [syntax examples](../examples/README.md).
The [local tutorial](../examples/tutorial/README.md) demonstrates a record with
both resources present.

Every selected file is treated as an intended shard. Unrelated or malformed JSON
is an error, not silently ignored. Choose narrow roots or include/exclude patterns
when a repository also holds package manifests, configuration, or other data.
Store generated reader reports outside the selected files.

## Supported carriers

| Carrier | What is read | Origin of each record |
|---|---|---|
| JSON object | One complete annotation | Empty JSON pointer `""` |
| JSON array | One complete annotation per member | JSON pointer `/0`, `/1`, … |
| JSONL or NDJSON | One complete annotation per nonblank line | Physical line number, starting at 1; empty pointer |

Each record validates independently, including repeated source fields. An array
is a carrier, not a valid annotation. JSONL lines cannot themselves contain
arrays. The reader does not search inside arbitrary objects for annotation-shaped
values or infer shared defaults. Empty arrays and blank JSONL files are valid
empty shards; a scan finding no annotations reports `NO_ANNOTATIONS`.

Carriers use UTF-8. JSONL/NDJSON records are separated by LF; CRLF also works.
Rows containing only spaces, tabs, or carriage returns are skipped. Blank rows
still count toward physical line numbers.

One file per link, chapter arrays, and generated JSONL can coexist:

```text
chosen-root/
  introductory-link.json
  chapters/
    chapter-01.annotations.json
  generated/
    matches.jsonl
```

Other applications can implement different carriers and pass each extracted
record to the same atomic validator. A transport envelope remains application
data; it does not become a new required annotation field.

## Selection rules

By default, directory scans select `.json`, `.jsonl`, and `.ndjson` files,
case-insensitively. An explicit include pattern replaces this suffix filter.
Selected `.jsonl`/`.ndjson` files use line-based parsing; other suffixes use JSON.
An explicitly named ordinary file may have any suffix.

Include/exclude patterns match root-relative POSIX paths case-sensitively. `*`
can match across directory separators; a leading `**/` also permits a root-level
match. Exclusion wins. Hidden directories receive no special treatment. Selected
files are read in deterministic resolved-path order, and overlapping roots do
not reread the same resolved file path.

Symlinks encountered during traversal are skipped. An explicitly supplied symlink
is an error. Directory traversal reads local carrier files only; it fetches no
resources and executes no selectors.

## Origins and relative references

Each collected record retains its decoded annotation and carrier context:

| Origin field | Meaning |
|---|---|
| `path` | The resolved carrier path captured during collection. |
| `base_uri` | That carrier's file URI, captured with the record. |
| `pointer` | `""` for a single object/JSONL record, or an array member's JSON pointer. |
| `line` | A JSONL/NDJSON physical line number; otherwise `None` in Python / `null` in the JSON report. |

Relative references resolve against `base_uri`, not the scan root, current
working directory, annotation ID, or informal resource. A pointer or line number
locates the record but does not change its base. For example:

| Carrier URI | Reference | Resolved reference |
|---|---|---|
| `file:///work/a/links.json` | `chapter.pdf` | `file:///work/a/chapter.pdf` |
| `file:///work/b/links.json` | `chapter.pdf` | `file:///work/b/chapter.pdf` |
| `file:///work/a/links.json` | `../chapter.pdf` | `file:///work/chapter.pdf` |
| `https://example.org/notes/links.json` | `formal.html#result` | `https://example.org/notes/formal.html#result` |

The last row illustrates a hosted carrier; this offline reader itself does not
download it. A web consumer retains the hosted carrier's URI as its base. These
are ordinary [URI-resolution rules](https://www.rfc-editor.org/rfc/rfc3986#section-5),
with FCA choosing the carrier as context.

The reader never rewrites annotations. Moving or combining shards requires either
retaining each original base in application transport metadata or deliberately
rebasing the affected references. Copying an annotation into a new directory
without either step can change both endpoints. A copied report is not a portable
bundle of the source resources.

Repeated `id` values and identical-looking annotations are preserved. An `id` is
an opaque application label, not an instruction to merge records. File plus
pointer/line identifies an occurrence in this scan, not an eternal annotation
identity. A consuming application defines any further identity/conflict policy.

## Use the Python result

```python
from formal_companion_annotations import discovery

collection = discovery.collect(["examples/companion"])
if collection.problems:
    raise ValueError("; ".join(str(problem) for problem in collection.problems))
for record in collection.records:
    print(record.base_uri, record.pointer, record.line, record.annotation["target"])
```

`collect(paths, include=None, exclude=())` returns a `Collection` with `records`,
`files`, and `problems`. Problems contain `code`, `path`, and `message`. Valid
records can remain available even when another record or file fails. **Inspect
`problems` before accepting the collection**; the presence of records alone does
not mean the scan succeeded. Origins preserve context, not a byte-for-byte copy
of the input: see the [JSON and number limits](companion.md#validation-and-serialization).

## Command results

Text output reports counts and problems. `--format json` returns one reader
report containing `valid`, `status`, `files`, `records` with `origin`, and
`problems`. The report is operational data, not a new annotation schema or a
portable resource bundle. Keep origins when retaining relative references.

| Exit status | Meaning |
|---|---|
| `0` | At least one annotation found; all selected inputs accepted. |
| `1` | An annotation or carrier shape is invalid. |
| `2` | Reading, JSON parsing, path, symlink, or no-annotation failure. |

All selected inputs are processed; status `2` takes precedence over `1`.
No resource, schema URI, or selector is fetched or executed.

## Relation to existing companions

See [integration notes](integrations.md) for existing companion systems and the
adapters they need. Their viewers, graphs, source documents, and review workflows
remain application concerns; discovery only collects independent links.
