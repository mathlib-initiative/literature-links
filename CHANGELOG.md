# Changelog

## Unreleased

- Breaking: a `.json` file holds one annotation, an object. One that holds an
  array is now a `SHAPE` problem, and `scan` exits 1 on it; 1.0.0 read `[x]`
  and `[x, y]` with exit 0, and `[]` was `NO_ANNOTATIONS` with exit 2.
  `validate` reports `SHAPE` there instead of `SCHEMA`. To migrate, put one
  object in each `.json` file, or convert: `jq -c '.[]' a.json > a.jsonl`. The
  schema is unchanged.
- Breaking: `discovery.Record` has no `pointer`, and its `line` and `defaults`
  are keyword-only, so a positional call fails instead of shifting fields. The
  `scan --format json` origin has no `pointer`. Problem paths no longer put `#`
  after the file name: `a.json $.location`, `a.jsonl (line 2) $.location`.
- `validate` reads `.jsonl` and `.ndjson` files one annotation per line and
  names the line in each problem; an empty one exits 2. A JSON file holding a
  scalar is a `SHAPE` problem, as in `scan`, and a `JSON` problem exits 2, as
  in `scan`.
- `companion.normalize` copies a record with a string `target` as
  `{"uri": ...}` and a string `status` as `{"value": ...}`, so readers handle
  one shape. It raises `TypeError` for anything but a dict.
- The specification says what an annotation file carries: a JSON document one
  annotation, a JSONL document one per nonblank line, for files and web
  responses alike.
- `docs/companion.md` now holds only the format. The checker, its Python API,
  the command line and how files are found and read moved to `docs/tools.md`.
  The specification keeps its headings.

## 1.0.0 (2026-10-09)

First public release.

- One annotation links one informal `source`, optionally narrowed by a
  `location`, to one formal `target`. Sources are PDF, LaTeX, HTML or generic.
  Without `target`, an annotation records the passage alone.
- A location with a `profile` key is application-defined under every source
  type, so a location no built-in form fits does not force a `generic` source.
- Optional typed pins on `source`, `target` and `status`: `website`, `book`,
  `paper`, `repository` and `generic`.
- Optional facts `status`, `kind`, `label` and `note`. `status` may be an object
  with `value`, `pin` and `extensions`.
- Folder defaults: a `_defaults.json` file supplies shared members to every
  annotation in its folder and below, merged like JSON Merge Patch.
- The `literature-links` command with `validate` and `scan`, and the
  `companion` and `discovery` modules.
- Records valid under 1.x stay valid in later 1.x; a breaking change bumps the
  major version.
