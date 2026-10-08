# Changelog

## 2.0.0a2 (unreleased)

- New format: one annotation links one informal `source`, optionally narrowed by
  a `location`, to one formal `target`. Sources are PDF, LaTeX, HTML or generic.
  The format has no version field.
- Add the `formal-companion-annotations` command with `validate` and `scan`.
- Remove v1 and the `formal-companion-annotations-validate` command. v1 remains
  available at tag `v1.0.0`.
- The schema's `$id` is the raw URL of `schema/companion.schema.json` on `main`.
  It is a name; nothing fetches it.

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
