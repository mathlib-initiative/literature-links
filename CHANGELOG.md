# Changelog

## 1.0.0 (unreleased)

First public release.

- One annotation links one informal `source`, optionally narrowed by a
  `location`, to one formal `target`. Sources are PDF, LaTeX, HTML or generic.
  Without `target`, an annotation records the passage alone.
- A PDF location selects a page, optionally narrowed by a `rect` or a `quote`,
  not both. The `quote` is the HTML quote object, matched against the
  extracted text of that one page.
- A location with a `profile` key is application-defined under every source
  type, so a location no built-in form fits does not force a `generic` source.
- Optional typed pins on `source`, `target` and `status`: `website`, `book`,
  `paper`, `repository` and `generic`.
- Optional `status`, `kind`, `label` and `note` describe the link. `status` may
  be an object with `value`, `pin` and `extensions`.
- Folder defaults: a `_defaults.json` file supplies shared members to every
  annotation in its folder and below, merged like JSON Merge Patch.
- Annotation files: a JSON document holds one annotation, and a JSONL document
  one per nonblank line.
- The `literature-links` command with `validate` and `scan`, and the
  `companion`, `discovery` and `schemacheck` modules, documented in
  `docs/tools.md`. `companion.normalize` gives readers one shape for `target`
  and `status`.
- Records valid under 1.x stay valid in later 1.x; a breaking change bumps the
  major version.
