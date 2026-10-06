# Synthesis with PR #2: one annotation at a time

This is an unpublished design and implementation draft, package `2.0.0a2`.
It compares [PR #2](https://github.com/mathlib-initiative/formal-companion-annotations/pull/2)
at commit `e985d3e4735fa43cd1004ee7a631eb03526e7a03` with the earlier local
`2.0.0a1` draft at commit `1de6461`. It does not merge, publish, or change that PR.

## Decision

The schema describes **one informal-to-formal association**. It does not
describe a companion, a source registry, or a collection of annotations.

```json
{
  "version": 2,
  "source": { "type": "pdf", "uri": "../notes.pdf" },
  "location": { "page": 4 },
  "target": "https://example.org/formal/Result.html#result"
}
```

`version`, `source`, and `target` are required. The informal `source` requires
a `type` and `uri`. `location`, `id`, `$schema`, and `extensions` are optional.
PDF, LaTeX, and HTML supply small built-in location formats; generic mode
allows application-defined JSON locations. An absent location selects the
whole source, so an unknown anchor must never silently become absence.

An annotation records an association. It does not claim mathematical
equivalence, a completed proof, or human review. Multiple formal targets or
informal occurrences are separate annotation records.

The earlier draft's `annotations` array has been removed. This is an
intentional breaking revision of an unpublished draft. A previous collection
document is not an atomic annotation even if it contains only one link.

## Comparison

| Concern | PR #2 | Earlier local draft | This synthesis |
|---|---|---|---|
| Schema unit | Entire companion repository | One source and many annotations | One annotation |
| Required root | Eight fields: schema identity/version, companion metadata, sources, items, declarations, links, provenance | Version, source, annotations | Version, source, target |
| Source | Registry record, edition pinning rules | Concrete resource and mode | Concrete resource and mode |
| Link | References to item, declaration or cluster, and provenance; role and ID | Formal target, optional locator and ID | Same small association, at the root |
| Additional data | Graph, site, audit, history profiles | Extensions | Extensions; collection applications own their graph and workflow |
| Ordering | Sorted record arrays and canonicalization rules | Preserve ordering | No aggregate ordering or canonical byte contract |

The PR's aggregate boundary is explicit in its
[purpose and document structure](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/docs/annotations.md#L13),
and its schema requires the
[eight root fields](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/schema/annotations-v1.0.schema.json#L3159).
The [four profiles and their gating rules](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/docs/annotations.md#L38)
are useful companion application features, but they are not requirements for
publishing one association.

## What the PR contributes

The PR's implementation discipline does not depend on its aggregate format.
This synthesis adopts or retains:

- Structured findings with stable codes, paths, and human-readable messages,
  and machine-readable validation output. The PR's
  [Problem record](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/src/formal_companion_annotations/validate.py#L223)
  and [JSON report](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/src/formal_companion_annotations/validate.py#L1877)
  provide the model, without importing its graph-invariant codes into the new core.
- One authoritative schema source, packaged with the offline checker, following
  the PR's [package mapping](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/pyproject.toml#L46).
- Descriptions on schema fields, precise coordinate and selector conventions,
  and a short specification for rules that the schema cannot express.
- Strict JSON checks already present in the local draft: duplicate keys,
  nonfinite numbers, invalid Unicode, unsupported in-memory values, and cycles
  are errors. Unknown extension values are preserved. Validation fetches nothing.
- Tests of malformed inputs, schema/checker agreement, and installed package
  behavior. The PR's [CLI tests](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/tests/test_checker.py#L1942)
  illustrate the value of checking actual output and exit statuses.

The PR's [I-JSON contract](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/docs/annotations.md#L78)
also limits integer-valued numbers to the interoperable binary64 range and
sets fixed nesting and numeric-literal limits. Those restrictions are not
silently imported into generic extension data. The atomic format retains its
documented JSON codec behavior, including exact Python integers within the
interpreter's limits. It does not claim the PR's I-JSON conformance. Applications
should use strings where exact large integers or decimals must cross runtimes.

Mandatory repository commits, hashes, generator information, timestamps,
provenance records, declaration inventories, coverage rules, and graph profiles
are not adopted into the atomic core. Applications can store them in extensions
or companion metadata they own. Lean scanning also remains producer work, as
the PR's [public-API test](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/tests/test_package.py#L198)
explicitly recognizes.

## A directory can be a companion

A reader can traverse a directory and discover annotation shards. Neither the
schema nor an annotation mandates directory names, file names, a manifest,
one file per annotation, or one global packing format. A reader documents the
encodings it understands and validates each extracted annotation separately.
For example, standalone JSON records and arrays of records can be different
reader conventions without creating two annotation schemas.

Each extracted record retains its containing file's location as its reference
base. Relative references do not suddenly become relative to the scan root,
another source file, or a repository root. Relocating records therefore needs
an explicit base-preservation or URI-rewriting decision. Traversal and shard
parsing do not fetch the referenced informal or formal resources.

Collection policies such as deduplication, identity collisions, trust,
ordering, and aggregate indexes belong to the collecting application. A
tao_measure-style companion, WikiLean, and Autoform can each choose those
policies while exchanging the same single annotation records. Their adapters
and viewers are separate work, not implemented by this schema revision.

## Migration and version boundaries

Three distinct formats must not be confused:

1. The original `lean-companion/annotations` v1 graph.
2. PR #2's `formal-companion/annotations` release-candidate graph, which still
   declares `schema_version: "1.0"` at the reviewed commit.
3. This unpublished atomic draft, identified by `version: 2`.

The [PR version comment](https://github.com/mathlib-initiative/formal-companion-annotations/pull/2#issuecomment-5930681089)
already identifies the release candidate's format identity and ID-rule changes
as requiring a new major rather than reuse of the original 1.0.0 identity.
Its proposed `2.0.0` and this local draft's `2.0.0a2` are not evidence of
compatibility. A published version and schema identifier need coordination
before either is released. This work neither resolves that release decision
nor presents its draft schema identifier as a public hosted endpoint.

The current migrator supports only the original v1 dialect. It validates that
input, archives it, and emits one atomic record for each convertible
location/destination association. Source metadata is copied into each record's
extensions; the result's document list is an API return value, not a collection
schema. Unresolved associations remain in the archive with diagnostics.

**PR #2 migration is not implemented.** Its marker produces an explicit
unsupported-dialect error. Running its four valid examples against the earlier
local migration confirmed that none were supported: all had the changed schema
identity; the mixed example additionally uses profile fields and declaration
kinds the original schema does not accept. Renaming its identifier would hide
this incompatibility rather than migrate it.

A future rc3 adapter must validate the actual rc3 schema and invariants, then
extract associations with explicit source and formal-target mappings where
needed. The PR's [minimal example](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/examples/annotations/minimal.json)
has a source hash but no concrete source URI and no rendered formal target.
Neither a hash nor a Lean declaration name licenses inventing a URL.
Alternative/refined selectors, text normalization, PDF coordinate conventions,
orphaned links, cluster targets, and review/coverage claims need explicit
translation or opaque preservation with diagnostics.

Finally, this is W3C-inspired, not a claim of W3C Web Annotation interchange.
Here `source` is informal and `target` is formal. In the PR,
[`locations[].target`](https://github.com/mathlib-initiative/formal-companion-annotations/blob/e985d3e4735fa43cd1004ee7a631eb03526e7a03/docs/annotations.md#L23)
names the informal selection. A future W3C exporter must state its body/target
mapping and translate selector semantics explicitly.
