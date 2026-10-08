# Changelog

## 1.0.0 (unreleased)

First public release.

- One annotation links one informal `source`, optionally narrowed by a
  `location`, to one formal `target`. Sources are PDF, LaTeX, HTML or generic.
  Without `target`, an annotation records a passage with no formal counterpart.
- A location with a `profile` key is application-defined under every source
  type, so a location no built-in form fits does not force a `generic` source.
- Optional typed pins on `source`, `target` and `status`: `website`, `book`,
  `paper`, `repository` and `generic`.
- Optional facts `status`, `kind`, `label` and `note`. `status` may be an object
  with `value`, `pin` and `extensions`.
- The `literature-links` command with `validate` and `scan`, and the
  `companion` and `discovery` modules.
- Records valid under 1.x stay valid in later 1.x; a breaking change bumps the
  major version.
