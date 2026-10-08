# Changelog

## 2.0.0a2 (unreleased)

- New format: one annotation links one informal `source`, optionally narrowed by
  a `location`, to one formal `target`. Sources are PDF, LaTeX, HTML or generic.
  The format has no version field.
- Add the `formal-companion-annotations` command with `validate` and `scan`.
- Remove v1: its `ids`, `validate` and `vocab` modules and the
  `formal-companion-annotations-validate` command. v1 remains available at tag
  `v1.0.0`.
- The schema's `$id` is the raw URL of `schema/companion.schema.json` on `main`.
  It is a name; nothing fetches it.
- `target` is optional and may be an object with `uri`, `pin` and `extensions`.
  A record without `target` is an informal passage with no formal counterpart.
- Add optional typed pins on `source` and `target`: `website`, `book`, `paper`,
  `repository` and `generic`. Inside a pin only `type` is required.
- Add optional `status`, `kind`, `label` and `note`.

## 1.0.0 (2026-09-28)

First release: the v1 format (`schema_version` `"1.0"`) and the
`formal-companion-annotations-validate` command, extracted from the
formal-companion skill at `d4deedb`. The full release notes are in
`CHANGELOG.md` at tag `v1.0.0`.
