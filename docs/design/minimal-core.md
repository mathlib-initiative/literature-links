# One annotation is the unit of interchange

**Status:** accepted for the local, unreleased draft.

**Date:** 2026-10-06.

## Context

A companion connects informal mathematics with formal resources. Different
applications organize these connections differently: a PDF overlay groups them
by page, a wiki groups them by article, and a formalization project relates them
to a dependency graph. Requiring one application's organization would make the
format harder for the others to use.

The core must express a useful individual link by hand, support the common
source formats, and leave applications room to add their own conventions.
[The specification](../companion.md) defines the resulting contract.

## Decision

One complete annotation contains one informal `source` and one formal `target`.
Only those fields are required. A `location` optionally selects part of the
source. An annotation can also carry an optional label, schema hint, or extension
data. There is no annotation version field in this unreleased draft.

Use separate records for multiple targets or informal occurrences. A companion
is assembled by collecting those records; the core requires no shared registry,
manifest, directory layout, or particular file grouping. The included
[discovery utility](../discovery.md) is one reader convention, not part of the
annotation's shape.

An association is a limited claim. Resource existence, selection resolution,
faithful mathematical correspondence, proof completion, and human review are
separate questions. A valid record does not answer them.

## Alternatives considered

| Unit of interchange | Advantage | Cost | Decision |
|---|---|---|---|
| An entire companion graph | Shared inventories and global consistency rules | One link requires surrounding graph, identity, and workflow machinery | Keep this in applications |
| One source with an array of links | Avoids repeating source metadata | Each link depends on its wrapper and inherited context | Do not use as the schema unit |
| One independent annotation | A link can be written, checked, and exchanged on its own | Repeats references; readers handle collections | Use for the core |

An array of complete annotations remains a useful storage choice. It adds no
inheritance and does not turn the array into another annotation schema.
Independence from a registry also does not remove reference context: a relative
URI still depends on its containing carrier's address.

## Consequences

| Choice | Benefit | Responsibility left to applications |
|---|---|---|
| PDF, LaTeX, HTML, and generic modes | A small shared selection vocabulary with room for custom formats | Interpret generic locations and report unsupported ones |
| Optional location | Simple whole-source associations | Distinguish absence from failed or missing selection data |
| Closed core fields | Catch misspelled keys | Put experimental conventions in generic locations or extensions |
| Opaque extension values | Carry evidence and metadata without a registry | Agree on their meaning and preserve unfamiliar data |
| No required source lock or provenance | Support handwritten and unpublished annotations | Pin resources and record evidence when reproducibility matters |
| Optional opaque ID | Avoid a central identity service | Decide how synchronization and ID conflicts work |
| No canonical bytes | Avoid imposing one signing or storage policy | Define hashing, signatures, and deduplication explicitly |
| No required carrier | Permit files, streams, and database rows | Retain reference bases and origin information |

Source extensions and annotation extensions have separate scopes, with no
inheritance or merging. Namespaced extension keys are encouraged, not required.
A generic location may be any JSON object. A `profile` key is optional application
data, not an instruction to download a schema or execute a resolver.

## Relationship to W3C Web Annotation

The [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
informs the choice of independent annotations and selections within resources.
This draft uses a smaller application format and does not claim W3C JSON-LD
serialization compatibility.

The field orientation matters. Here `source` is informal and `target` is formal.
A W3C representation can instead use the informal selection as its target and
the formal resource as its body. An adapter must translate that orientation
and the selector conventions explicitly; renaming fields is insufficient.

## Boundaries and future review

New modes should be justified by recurring use cases and shared selection
semantics. Generic mode already accommodates Markdown, wikitext, images, and
database records. A new application's needs alone do not require a new core mode.

The core deliberately leaves publication, resource resolution, trust, and
mathematical verification to consumers. The [integration guide](../integrations.md)
describes how WikiLean and Autoform use that boundary. The
[compatibility guide](../compatibility.md) separates the current format from
legacy data, while the [PR comparison](pr-2-synthesis.md) preserves the historical
reasoning at the reviewed commits.

Before a public release, maintainers still need to agree on the public format
and schema identifier and coordinate competing prerelease work. This design
record documents the local decision; it does not imply community endorsement.
