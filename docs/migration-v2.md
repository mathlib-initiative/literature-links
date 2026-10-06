# Migrating a v1 companion

V1 is a rich graph of sources, items, declarations, links, locations, and
workflow records. V2 is independent single associations. Migration is a **projection**, not
a lossless replacement of the graph. Keep the archive. No files change until
an explicit command is run; v1 validation remains available.

The supported input is the released `lean-companion/annotations` v1 dialect.
PR #2's `formal-companion/annotations` rc3 dialect needs a separate adapter and
is explicitly rejected. It changes core rules as well as its format identifier;
renaming that identifier would not validate or safely migrate it. See the
[PR synthesis](design/pr-2-synthesis.md). The earlier unpublished a1 collection
wrapper is also not an input to this v1 migrator.

## Command

```sh
formal-companion-annotations migrate-v1 old-annotations.json \
  --output migration-output \
  --source-base file:///absolute/path/to/source-repository/ \
  --target-base https://example.org/formal-docs/
```

Supply the actual source root and formal documentation base. Directory bases
end in `/`; normal URI joining semantics apply otherwise. The command makes
no guess that the old annotation file lives at the repository root. It refuses
to relocate a relative source without an explicit base or absolute mapping.
Sources that already have absolute URLs do not need `--source-base`.

To override a missing or unsuitable source address, add
`--source-uri SOURCE_ID=https://example.org/notes.pdf`. Repeat this for distinct
original source IDs. Otherwise a v1 path takes precedence over a URL which might
only identify a repository. Literal path characters are URI-escaped before
resolution; URLs and explicit mappings are already URI references.

The output directory must not exist. Conversion and serialization finish in
a temporary sibling directory before exposing the output. The bundle contains:

- `original-v1.json`: the exact bytes of the supplied input.
- `annotation-001.json`, etc.: one validated v2 annotation per association.
- `report.json`: output filenames, resolution options, and structured diagnostics
  naming affected v1 records.

Read the report even on success. Exit 0 means a valid bundle was written, not
that every v1 record became a v2 annotation. Zero annotations is valid when
nothing can be mapped safely. Warnings and generic locators need review.
To discover just the generated annotations, scan this directory with
`--include 'annotation-*.json'`. Reports and archives are separate application
data. These output filenames are the converter's convention, not schema rules.

## Native and generic locations

| V1 data | V2 projection |
|---|---|
| Simple physical PDF page fragment | PDF `page` |
| One printed PDF page with known offset | Physical PDF `page` |
| Finite RFC 5147 LaTeX line interval | Inclusive, one-based `lines` |
| Simple HTML CSS selector | HTML `css` |
| Unencoded HTML ID fragment | HTML `fragment` |
| PDF regions, normalized quotes, ranges, refinements, multiple selectors, source states, unsupported anchors | Generic object retaining original locator data |
| Numbered item without a representable anchor | Generic object retaining item identity; never a whole-source claim |

For example, RFC 5147 `line=41,47` becomes lines 42 through 47, following its
[zero-based boundary convention](https://www.rfc-editor.org/rfc/rfc5147.html#section-2.1).
PDF rotation/box semantics and legacy quote normalization cannot be assumed to
match the new conventions. One source may yield both native and generic
annotations. Every location/destination pair becomes its own independent record,
even when another record has the same source. No resource is fetched.

## Targets and metadata

Only explicit v1 destinations with `resolution: "exact"` become formal targets.
No URL is invented from a Lean name. Relative formal destinations require
`--target-base`; otherwise they stay archived with diagnostics. Several exact
destinations produce separate associations. Fallback destinations, cluster
membership, and orphaned links are not promoted into direct associations.

Projected sources retain the original source record in their
`org.mathlib-initiative.fca-v1` extension. Associations retain legacy link, item,
destination, provenance IDs, role, and supported link metadata there. Those IDs
refer back to the archive, not a new required inventory. Generic locators use
`urn:formal-companion:legacy-v1:locator`, an opaque application profile that is
never fetched.

The full archive preserves review records, declaration inventories, dependencies,
snippets, locks, provenance, and other unprojected data. Diagnostics identify
unexported items/destinations and archived categories. Legacy role or review
metadata does not turn a core association into a proof claim.

## Python API

```python
from formal_companion_annotations import companion, migration

old = companion.loads(text)
result = migration.migrate_v1(
    old,
    source_uris={"source-id": "https://example.org/notes.pdf"},
    target_base="https://example.org/formal-docs/",
)
documents = result.documents
diagnostics = result.diagnostics
original = result.original
```

The API validates v1 and every projected v2 document, leaves input unchanged,
and returns an independent deep copy in `original`. This copy preserves decoded
data, not original whitespace. API callers may keep relative sources with a
`relative_source_context` warning and must preserve their original base when
storing documents. The CLI requires resolution because it writes elsewhere.

`MigrationError` is a `ValueError`. Invalid input or malformed explicit mappings
raise it. Missing information in valid v1 data produces diagnostics instead of
fabricated annotations. The adapter performs no network requests.
