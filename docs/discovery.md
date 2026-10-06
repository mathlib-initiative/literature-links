# Companion discovery and shards

An annotation is one informal–formal link. A companion is the result of
collecting annotations for an application. The annotation schema does not
define how a companion is stored, grouped, or indexed.

## Reader conventions, not schema requirements

The included offline reader accepts these convenient carriers:

| Carrier | Records read | Origin within the carrier |
|---|---|---|
| JSON object | One annotation | Empty JSON pointer |
| JSON array | One annotation per member | JSON pointer such as `/0` |
| JSONL or NDJSON | One annotation per nonblank line | Physical line number |

Every record is complete and validates separately. An array is not itself
valid against the annotation schema. No shared defaults or registry is inferred.
JSONL lines cannot themselves be arrays. Empty arrays/blank JSONL files are
allowed shards, but a scan finding no annotations reports `NO_ANNOTATIONS`.

Any directory layout is possible. For example, an author might keep one
annotation per file, another might group a chapter into an array, and another
might stream generated annotations into JSONL. These choices can coexist:

```text
chosen-root/
  introductory-link.json
  chapters/
    chapter-01.annotations.json
  generated/
    matches.jsonl
```

There is no required filename suffix in the schema. By default, recursive
discovery selects `.json`, `.jsonl`, and `.ndjson`. An explicit include pattern
can select another suffix; that carrier is interpreted as JSON. An explicitly
named ordinary file can have any suffix. Applications may implement other
carrier readers and feed their extracted records to the same atomic validator.

## Selection and traversal

```sh
formal-companion-annotations scan annotations/
formal-companion-annotations scan repo/ --include '*.annotations.json' --include '*.jsonl'
formal-companion-annotations scan first/ second/ --exclude 'generated/archive/*' --format json
```

Directories are traversed recursively, and selected files are read in
deterministic path order. Include/exclude patterns match the root-relative POSIX
path, case-sensitively; `*` can match across directory separators.
A leading `**/` also permits a root-level match. Explicit includes replace the
default suffix filter, and exclusion wins. Hidden directories are not special.

The reader skips symlinks found during traversal. An explicitly supplied symlink
is an error. Overlapping roots do not reread the same resolved file path.
It does not search nested arbitrary objects for annotation-shaped values:
extension payloads, graphs, ledgers, manifests, and configuration remain data.

Every selected file is an intended shard. Malformed or unrelated JSON is an
error, not silently ignored. Narrow the roots or patterns when scanning a
repository that also has `graph.json`, package manifests, and application data.
In particular, a migration bundle can be scanned with
`--include 'annotation-*.json'`, leaving its report and archive outside selection.

## Origins and relative references

Every collected record carries its annotation unchanged plus:

- `path`: the resolved carrier path.
- `pointer`: its position in a JSON carrier.
- `line`: the physical JSONL line when applicable.
- `base_uri`: the file URI of the carrier.

Relative `source.uri` and `target` values resolve against that carrier URI,
not the scan root, working directory, annotation ID, or informal source.
JSON array pointers and JSONL line numbers locate records; they do not change
their URI base. For a hosted shard, a web consumer uses its served URI instead.

Thus `a/links.json` and `b/links.json` can contain the same `../chapter.pdf`
text without confusing their origins. Moving or combining shards requires
preserving their original bases, rebasing relative references, or converting
them deliberately to absolute references. The reader returns origin metadata
and never rewrites the annotations.

Optional `id` is opaque application data. Repeated IDs and identical-looking
associations are preserved; the collector does not silently merge them or
impose a global uniqueness policy. A consuming application can impose its own
identity/conflict rules. File plus pointer/line identifies an occurrence in
this scan, not an eternal annotation identity.

## Results and failures

`discovery.collect(paths, include=None, exclude=())` returns a `Collection`
with `records`, `files`, and `problems`. Ordinary input failures become
structured problems with `code`, `path`, and `message`.
Valid records from other files remain available when one file fails, but the
result is unsuccessful whenever problems exist. Consumers must inspect them.

The CLI's text form reports counts and problems. Its JSON form returns
`valid`, `status`, `files`, `records` with `origin`, and `problems`.
This is a reader report, not a new companion schema or a portable annotation
bundle. Do not discard the origins when using relative references.

Exit 1 denotes invalid annotations/carrier shapes. Exit 2 denotes reading,
parsing, path, symlink, or no-annotation failures. All selected inputs are
processed, and 2 takes precedence. No resource, schema URI, or selector is
fetched or executed.

## Relation to existing companions

The inspected
[tao-measure-lean repository](https://github.com/mathlib-initiative/tao-measure-lean/tree/837525ab781e43480d35bcedd73ff80d99bcdacf)
uses book-tagged Lean docstrings, Verso pages, `graph.json`, and
`informal_content` Markdown. Its
[README](https://github.com/mathlib-initiative/tao-measure-lean/blob/837525ab781e43480d35bcedd73ff80d99bcdacf/README.md#L9)
and [blueprint generator](https://github.com/mathlib-initiative/tao-measure-lean/blob/837525ab781e43480d35bcedd73ff80d99bcdacf/scripts/make_depgraph.py#L119)
describe these existing relationships. They are exporter inputs, not evidence
that it already reads these annotations.

The related
[measure_theory PDF overlay](https://github.com/mathlib-initiative/measure_theory/blob/f6ad17eb86277f471b7f11c3992de6284f8a5c1f/pdf-overlay/ARCHITECTURE.md#L17)
keeps geometry, formal destinations, and its source/formalization ledger
separate. An adapter must convert its
[geometry conventions](https://github.com/mathlib-initiative/measure_theory/blob/f6ad17eb86277f471b7f11c3992de6284f8a5c1f/pdf-overlay/schema/README.md#L23):
its rectangles use endpoints, while this draft uses position and extent.
Relative formal destination URLs also need the original site's base, not the
new shard's location.

An exporter can emit independent annotation records from either system and let
a viewer rebuild an index from a directory scan. The graph, review ledger,
geometry extraction process, and directory organization remain owned by those
applications. Those exporters and viewers are not implemented by this reader.
