# One annotation is the unit of interchange

**Status:** Proposed implementation of the user's single-annotation requirement.
**Date:** 2026-10-06.
**Decision owner:** Project maintainers before a public release.

The [annotation specification](../companion.md) defines one informal–formal
association. The [PR #2 comparison](pr-2-synthesis.md) records why both the PR's
repository graph and the earlier local source-level collection are larger than
the requested unit.

## Decision

```json
{
  "source": { "type": "latex", "uri": "../chapters/groups.tex" },
  "location": { "label": "thm:lagrange" },
  "target": "https://example.org/formal/Groups.html#lagrange"
}
```

This is one complete annotation. Only `source` and `target` are required.
The unreleased format has no annotation version field; software releases retain
their own package versions. A companion is assembled by finding many such
records. The core does not specify their directory layout, file grouping, or
collection manifest. Discovery is a separate utility; applications can supply
other carrier readers without changing the annotation schema.

The link asserts association only. Resource existence, anchor resolution,
proof completion, faithful mathematical correspondence, and review are separate
claims. A viewer must not turn an unresolved anchor into a whole-resource link
or present an unknown generic locator as a successfully anchored highlight.

## Options considered

| Unit | Advantages | Costs | Decision |
|---|---|---|---|
| Entire companion graph, as in PR #2 | Shared inventories and repository-wide consistency | Mandatory registry/provenance/ID machinery; difficult to exchange one link alone | Keep graph data in its producer |
| One source with an annotations array, as in local a1 | Avoids repeating source metadata | Couples a link to its wrapper and makes regrouping semantic | Superseded |
| One independent annotation | Each link can validate, move, or be consumed independently | Repeats source references; collections need their own reader | Adopt for the core |

A source reference can still be relative, so moving a record requires retaining
or deliberately changing its containing carrier's URI base. Independence from a
registry does not make relative references independent of location.

## Tradeoffs and consequences

| Choice | Benefit | Responsibility left to applications |
|---|---|---|
| Exactly one informal source and formal destination | Clear association with no cross-reference tables | Multiple targets/occurrences use multiple records |
| Four modes: PDF, LaTeX, HTML, generic | Small shared locator vocabulary with an escape hatch | Unknown locators need application-specific support |
| Optional location | Whole-resource associations are simple | Absence differs from a failed/malformed locator |
| Closed core fields | Typos fail early | New anchor conventions start in generic mode |
| Opaque JSON extensions | Custom evidence and metadata survive exchange | Consumers agree on their meaning separately |
| No required source lock or provenance | Handwritten and unpublished annotations work | Reproducibility requires explicit pinning/evidence where needed |
| Optional opaque ID | No central identity service or generated IDs | Synchronization and ID conflicts need a consumer policy |
| No canonical bytes or ordering | Writers preserve supplied data | Signing/deduplication policies are external |
| No mandatory storage envelope | A directory can mix singles, arrays, and JSONL | A reader identifies carriers and retains origins |

Root annotation and source extensions have separate scopes. Neither inherits
from the other. Namespaced extension keys are recommended, not mandatory.
A generic location can be any JSON object; `profile` is optional caller data,
not an instruction to fetch or execute something.

## Examples

The [nine examples](../../examples/companion) use synthetic resources.
Their references need not resolve for the data to validate.

- [PDF page](../../examples/companion/pdf.json), [LaTeX label](../../examples/companion/latex.json),
  [HTML fragment](../../examples/companion/html.json), and
  [whole generic resource](../../examples/companion/generic.json).
- Two links from the same PDF region are
  [two independent records](../../examples/companion/pdf-region-first.json)
  ([second record](../../examples/companion/pdf-region-second.json)).
  Their optional grouping/review metadata imposes no collection schema.
- [Image region](../../examples/companion/generic-image.json),
  [database record](../../examples/companion/generic-database.json), and
  [Markdown block](../../examples/companion/generic-markdown.json) demonstrate
  custom locators, including one without a mandatory profile or namespace.

## Discovery and existing systems

The [included reader](../discovery.md) recursively selects files and validates
complete records from JSON objects, arrays, and JSONL/NDJSON. It keeps origins
rather than silently rebasing or deduplicating. A graph file or review ledger
beside the shards is separate data, selected only deliberately.

WikiLean's requested target is native storage and editing of these records as
its link authority, with review/coverage items and private moderation state kept
as application data. Targetless work items are not yet informal–formal links.
Its current converter is a transitional bridge, not a permanent format boundary.

For Autoform, the recommended model keeps Markdown wiki articles as independent
informal resources and attaches separate companion records to them. An article
can have no links or many links. The roadmap/proof graph remains application
state, and ordinary citations to an original paper do not automatically transfer
an article's formal associations to that paper. Generic locations can select
parts of Markdown without adding a new core mode.

The Tao companions can adopt records from their existing graph and overlays.
Native application storage, migration and rendering remain application work;
the [repository findings](../discovery.md#relation-to-existing-companions) identify
actual inputs and coordinate/base conversions.

## W3C relationship

The [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
motivates independent annotations and selection of parts of resources.
This draft does not require JSON-LD or claim W3C serialization conformance.

Field orientation must be explicit: our `source` is informal and `target`
is the formal destination. In a usual W3C mapping, the informal resource being
annotated is the W3C target, and the formal resource is a body. Similar names do
not imply an identity mapping. A future adapter must translate selector
semantics and preserve or report unsupported data.

## Follow-through

The local draft implements single-record validation, explicit v1 projection,
independent discovery, origin-preserving reports, and synthetic tests.
Before release, maintainers must coordinate the version/identifier with PR #2.
PR rc3 migration requires its own actual schema/rule reader and mappings;
viewer rendering and native WikiLean/Autoform/Tao adoption remain application work.
