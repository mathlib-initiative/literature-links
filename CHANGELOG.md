# Changelog

## 2.0.0 (unreleased)

First public release.

An annotation relates a `subject` and an `object`, each a list of ends, such as
a passage of a book and a Lean declaration. An end names a document by `type`
(`pdf`, `latex`, `html`, `lean` or `generic`) and `uri`, and its optional
`location` selects part of it. An optional `relation`, such as `exactMatch` or
`noMatch`, says how the sides relate. A JSON file holds one annotation and a
JSONL file one per line, and a `_defaults.json` file gives the annotations
below it shared fields. The `literature-links` command and the
`literature_links` Python package check annotations offline.

### Changes from 1.x

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
  subject, and annotations about one subject share it.
- LaTeX `lines` may be `[n]`, the item that starts on line n.
- Folder defaults may hold an end template for each side.
- `normalize` is removed, and `merge` takes `defaults=True`.
- The `LINES` problem code replaces `LATEX_LINES` and covers Lean locations.
  `validate` lists the types of all ends.
