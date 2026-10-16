# Changelog

## 2.0.0 (unreleased)

First public release.

An annotation records a correspondence between two documents, or parts of
them, such as a passage of a book and a Lean declaration. Its `subject` and
`object` are lists of ends. An end names a document by `type` (`pdf`, `latex`,
`html`, `lean` or `generic`) and `uri`, and an optional `location` selects part
of it. An optional `relation` says how the sides relate; SKOS's mapping
relations, `hasPart` and `noMatch` are recommended. A JSON file holds one
annotation and a JSONL file one per line, and a `_defaults.json` file gives the
annotations below it shared members, including end templates. The
`literature-links` command and the `companion`, `discovery` and `schemacheck`
modules check annotations offline.

### Changes from 1.x

- A record relates `subject` and `object`, lists of ends, in place of `source`,
  `location` and `target`. The ends on a side are taken jointly, and
  `"object": []` records an unlinked passage.
- `lean` ends: the project in `uri`, the commit in `version`, and a
  `declaration` or a `module` location, optionally narrowed to `lines`.
- `relation` says how the sides relate. `noMatch` over a project at a commit
  records a checked absence.
- `junk` lists the object's junk values, such as `x / 0 = 0`. An object that
  differs from the subject only through them is an `exactMatch`.
- `status` is a string that describes the subject. The status object is gone.
- `id` names the subject, and records about one subject share it.
- Pins are gone. An end's `citation` is a CSL-JSON item, beside its `version`,
  `sha256` and `identifiers`.
- An end's `title` replaces `label`, and an end may have a `role`.
- LaTeX `lines` may be `[n]`: the item that starts on line n.
- Folder defaults may hold an end template for each side. `merge` takes
  `defaults=True` to merge one defaults file over another.
- `normalize` is removed: every record has one shape.
- The `LINES` code replaces `LATEX_LINES` and also covers Lean locations.
- `validate` lists the types of all ends in its summary.
