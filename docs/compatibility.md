# Compatibility

Use [the current specification](companion.md) for new annotations. A record
requires `source` and `target`, with no annotation version field.

This repository retains readers for older data. Their presence does not make
the older formats alternative ways to write a current annotation.

| Format | Validation | Conversion to the current draft |
|---|---|---|
| Current single annotation | Supported | Already in the current format |
| Original `lean-companion/annotations` v1 graph | Retained | Explicit `migrate-v1` projection with an original archive |
| Unpublished a1 source-plus-annotations wrapper | Rejected by the current checker | No automatic conversion |
| PR #2 `formal-companion/annotations` rc3 graph | Use that dialect's checker | Requires a separate adapter |

The [migration guide](migration.md) explains which associations can be projected
from v1, what remains in the archive, and how diagnostics report omissions.
Migration does not invent formal URLs, convert review metadata into proof
claims, or preserve a whole graph in the single-annotation core.

## Commands and Python modules

`formal-companion-annotations` is the current command, with `validate`, `scan`,
`format`, and `migrate-v1` operations. `validate` also recognizes original v1
documents; `scan` discovers current annotations only. See `--help` for usage.

`python -m formal_companion_annotations` accepts the same subcommands. Historical
bare-file invocations still use the legacy validator. Use the explicit
`formal_companion_annotations.validate` module to avoid ambiguity when an input
filename is also a command name.

The legacy `formal-companion-annotations-validate` command and
`formal_companion_annotations.validate` module remain available. Their v1
canonicalization and ID rules apply only to v1. Current annotations have no
canonical byte representation and must not be passed through those operations.

The current Python API lives in `companion` and `discovery`. `migration` handles
explicit v1 conversion. The `validate`, `ids`, and `vocab` modules retain the
legacy API; names exported in each module's `__all__` define its public surface.

## Versions and identifiers

The Python package's prerelease version identifies software, not annotation
data. The current annotation rejects `version` and `schema_version` as unknown
core fields. Legacy v1 still uses its original `schema_version` marker.

The draft schema identifier is not a promise of a published endpoint. The
checker always uses its bundled schema and never fetches an annotation's
optional `$schema` hint. Pin a package or repository revision when reproducible
validation matters.

[The historical PR comparison](design/pr-2-synthesis.md) records the incompatible
format identities and release proposals at the reviewed commits. It is design
history, not a requirement to understand or use the current draft.
