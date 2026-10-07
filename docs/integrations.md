# Using annotations in a companion application

This package supplies an annotation contract and an offline reader. Applications
can share those records while keeping their own storage, user interface, review
process, and formalization workflow.

The integrations below describe local development work and existing source
formats. They do not imply deployment or adoption by another project.

## A common boundary

An application can store the complete annotation as its link data and put its
own information beside it. For example, a database row may hold an annotation,
its original carrier address, and a moderation status. That row is application
data; only the annotation inside it follows this schema.

When exchanging records:

1. Validate each complete annotation. Check collection errors before accepting a scan.
2. Retain its original reference base when any references are relative. Generic
   locations and extensions may also use that context under their own conventions.
3. Preserve unknown JSON data and repeated occurrences. Use an explicit policy
   for identities, conflicts, and deduplication.
4. Report unsupported or unresolved locations. Do not silently substitute a
   whole-source link or claim that a selector resolved.
5. Keep mathematical verification and human review separate from association data.

Applications may choose different storage limits. The Python reader retains
arbitrary integers within interpreter limits; a JavaScript application may need
to reject integers outside its exact range. Such a restriction is an application
constraint and should produce a diagnostic, never silent rounding.

## WikiLean

The local WikiLean integration stores and edits complete annotations directly.
Its review items contain links alongside application metadata, targetless source
occurrences, and private moderation history. Targetless occurrences are not
annotations: the shared format requires a formal destination.

Existing WikiLean records need an explicit database migration. After migration,
ordinary reads and edits use stored annotations, without a routine export step.
WikiLean's application storage marker is separate from the unversioned annotation.
Its raw-annotation response can only omit the carrier envelope when doing so
preserves interpretation; its records response retains that context.

WikiLean still owns source-revision handling, human edits, moderation, coverage,
and page highlighting. Its current JavaScript storage rejects unsafe integers.
The schema package neither connects to WikiLean's database nor deploys that code.

## Autoform

An Autoform Markdown article is an informal resource. Separate annotations
associate that article, or a selected part of it, with formal resources. The
article can have no annotations or many; its prose is not an annotation wrapper.

The local integration reads retained records and their original bases. Explicit
bindings associate source addresses with local articles and record a digest of
the article bytes. A changed article can show the association as historical
instead of silently applying it to a new revision. These bindings are Autoform
configuration, not additional annotation fields.

The generated web view displays associations beside the article. The authored
Obsidian vault remains unchanged and does not yet have a native annotation reader.
Associations do not change Autoform's proof graph, readiness, or review results.
A citation from an article to a paper also does not automatically transfer that
article's associations to the paper.

## Tao companions and other viewers

The inspected
[tao-measure-lean repository](https://github.com/mathlib-initiative/tao-measure-lean/tree/837525ab781e43480d35bcedd73ff80d99bcdacf)
uses book-tagged Lean docstrings, Verso pages, `graph.json`, and
`informal_content` Markdown. Its
[README](https://github.com/mathlib-initiative/tao-measure-lean/blob/837525ab781e43480d35bcedd73ff80d99bcdacf/README.md#L9)
and [blueprint generator](https://github.com/mathlib-initiative/tao-measure-lean/blob/837525ab781e43480d35bcedd73ff80d99bcdacf/scripts/make_depgraph.py#L119)
describe those relationships. They are potential migration inputs, not evidence
that the repository already reads this draft.

The related
[measure_theory PDF overlay](https://github.com/mathlib-initiative/measure_theory/blob/f6ad17eb86277f471b7f11c3992de6284f8a5c1f/pdf-overlay/ARCHITECTURE.md#L17)
keeps geometry, formal destinations, and its source/formalization ledger
separate. An adapter must translate its
[coordinate conventions](https://github.com/mathlib-initiative/measure_theory/blob/f6ad17eb86277f471b7f11c3992de6284f8a5c1f/pdf-overlay/schema/README.md#L23):
its rectangles use endpoints, while the current annotation uses position and
extent. Relative formal URLs also require the original site's base.

A viewer can rebuild its index by traversing chosen annotation shards. Source
extraction, coordinate conversion, review ledgers, and rendering remain its
responsibilities. This package does not provide those adapters or a universal
selector resolver.
