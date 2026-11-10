# Changelog

## Unreleased

- The specification moved from `docs/companion.md` to `docs/spec.md`. The old
  path now only links to the new one.
- A `latex` or `lean` location may give `bytes`, `[start, end]`, which selects
  the bytes from offset start up to, not including, offset end, counting from
  0. It selects part of a line, such as one hypothesis, where `label` and
  `lines` select the whole statement. A `latex` end with `bytes` must give
  `sha256`, and a `lean` end must give `version`; in Lean, `bytes` needs
  `module` and excludes `lines`. The new `BYTES` problem says that a range
  ends at or before its start. Annotations valid under 1.0 stay valid.

## 1.0.2 (2026-11-05)

- `literature-links scan` and `discovery.collect` take about 40% less time on
  large companions: 44,652 annotations read in 13.7 s instead of 23.7 s, one file
  each, on a GitHub runner. Files in one folder share its walk to the root, its
  defaults files and their merge. The JSON check finds unpaired surrogates with
  one regular expression and builds a problem's path only when there is a
  problem, and the schema checker resolves each `$ref` once. What the tools
  accept, reject and report does not change.

## 1.0.1 (2026-11-01)

- A `lean` end's `version` may be a release tag, such as Mathlib's `v4.33.0`, as
  well as the full commit. It still should not be a branch. Annotations that give
  a commit stay valid, and the schema and the checker do not change. The examples
  name Mathlib by its tag.

## 1.0.0 (2026-10-30)

An annotation relates a `subject` and an `object`, each a list of ends, such as
a passage of a book and a Lean declaration. An end names a document by `type`
(`pdf`, `latex`, `html`, `lean` or `generic`) and `uri`, and its optional
`location` selects part of it. An optional `relation`, such as `exactMatch` or
`noMatch`, says how the sides relate. A JSON file holds one annotation and a
JSONL file one per line, and a `_defaults.json` file gives the annotations
below it shared fields. The `literature-links` command and the
`literature_links` Python package check annotations offline.

### Changes from 0.x

- `subject` and `object`, lists of ends taken jointly, replace `source`,
  `location` and `target`. `"object": []` records an unlinked passage.
- `relation` is new. `noMatch` records a checked absence.
- A `lean` end names the project in `uri` and the commit in `version`, and its
  `location` a `declaration` or a `module`, optionally with `lines`.
- An end may list its `junk` values and give a `role`. Its `title` replaces the
  annotation's `label`.
- Pins are gone. An end's `citation` is a CSL-JSON item, beside its `version`,
  `sha256` and `identifiers`.
- `status` is a string about the subject, not an object. `id` names the
  subject: annotations about one subject share it, and within a companion,
  annotations that share it are about one subject.
- LaTeX `lines` may be `[n]`, the item that starts on line n.
- Folder defaults may hold an end template for each side.
- A reader may be given the companion's root folder, and `validate` and `scan`
  take `--root`.
- `normalize` is removed, and `merge` takes `defaults=True`.
- The `LINES` problem code replaces `LATEX_LINES` and covers Lean locations.
  `validate` lists the types of all ends.
- `validate` rejects a symlink or a file that is not a regular file, such as a
  pipe, as `scan` does.
