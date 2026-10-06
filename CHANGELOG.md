# Changelog

## 2.0.0a2 (unpublished working draft)

- Make the schema describe exactly one informal–formal association: required
  `source` and `target`; optional location, ID, and extensions.
  This supersedes a1's unpublished source-plus-annotations wrapper.
- Keep the unreleased annotation format unversioned; remove its `version` field
  and use neutral schema, specification, and example paths. Software package
  version `2.0.0a2` is unchanged.
- Keep companion assembly outside the schema. Add recursive discovery of JSON
  objects, array shards, and JSONL/NDJSON with configurable selection, precise
  origins, preserved relative-reference bases, and explicit failures.
- Adopt PR #2's structured-diagnostic and one-source-schema packaging ideas.
  Add JSON validation reports and process all inputs with exit 2 precedence.
  Keep opaque extensions and large-integer preservation; do not import the
  PR's aggregate profiles, required provenance, or canonical ordering.
- Emit independent records from released-v1 migration. Explicitly identify
  PR #2 rc3 as an incompatible dialect requiring a separate adapter; preserve
  unsupported legacy selectors as generic rather than invalid native anchors.
- Document the PR comparison, version conflict, and existing Tao companion
  boundaries. No PR update, publication, or external integration is implied.

## 2.0.0a1 (unpublished working draft)

- Add a small v2 document: version, one source, and annotations with formal
  destinations. PDF, LaTeX, HTML, and generic are the only input modes.
- Keep provenance, inventories, dependency graphs, and workflow records outside
  the required core. Generic locators and optional extensions preserve custom
  JSON without registration or mandatory profiles.
- Add an offline v2 checker and strict JSON codec, packaged JSON Schema, eight
  synthetic examples, a short specification, and design rationale.
- Add `formal-companion-annotations validate`, `format`, and `migrate-v1`.
  Migration requires explicit destinations, preserves complex anchors as
  generic data, reports omissions, and archives the original v1 input.
- Preserve v1 schema, vocabulary, ID helpers, and canonical examples. Existing
  validation entry points also accept v2. V1 canonical APIs reject v2 to avoid
  accidental extension rounding or sorting.
- Report parser-limit and canonical serialization failures through CLI errors
  instead of tracebacks. V1 plain validation still has its historical overflow
  limitation; v2 validation and migration reject nonfinite values.
- This is local draft development, not a public package, schema publication, or
  deployment of WikiLean or Autoform integrations.

## 1.0.0 (2026-09-28)

First release: the annotation format, `schema_version` `"1.0"`, extracted with
its history from the formal-companion skill at `d4deedb`.

- Checker behaviour, problem messages and canonical bytes are unchanged from the skill's copy; only the program name and the missing-schema exit status differ.
- Package `formal_companion_annotations`, console script `formal-companion-annotations-validate`, `python3 -m` entry points, `--version`.
- A missing packaged schema exits 2 ("schema file not found") instead of blaming the document.
- The schema's `$id` is its raw URL at the `v1.0.0` tag (spec section 9.3).
- Each module's `__all__` is the public API; the package ships `py.typed`.

### Known issues

- A number such as `1e400` overflows to `inf`, passes plain validation, and crashes `--canonical` and `--print-canonical` with a traceback.
- `--print-canonical` never validates first, so malformed input can crash it with a traceback.
