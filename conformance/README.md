# Annotation conformance cases

[annotations.json](annotations.json) contains 30 representative cases for the
[current single-annotation contract](../docs/companion.md). They are synthetic,
language-neutral test data for people implementing another validator or an
application that exchanges these records. The corpus itself is not an annotation
or a supported discovery carrier; extract each case's `annotation` value.

Each case has a stable descriptive `id`, an explanation, the input `annotation`,
and three expectations:

- `schema_valid`: the result of applying the bundled
  [JSON Schema](../schema/companion.schema.json) alone.
- `valid`: the result of the complete contract, including semantic checks.
- `problem_codes`: the distinct expected reference-checker codes. Compare these
  as a set; message text, diagnostic count, paths, and ordering are not fixture
  expectations. Other implementations may use their own diagnostics.

`PDF_RECT` and `LATEX_LINES` deliberately distinguish schema-valid inputs from
valid annotations. Rectangle bounds must account for the represented decimal
coordinates: ordinary floating-point addition can round an overflowing sum down
to one. No case requires fetching a source, following a formal link, resolving a
selector, or interpreting an extension. Validity says nothing about whether an
association is true or an anchor resolves.

Parse the corpus without rounding its integer values: one opaque payload uses
`9007199254740993`, which exceeds JavaScript's exact integer range. A host that
cannot preserve a value must report its implementation/storage limitation
instead of silently rewriting it. That limitation is separate from the
annotation's schema validity. The codec's treatment of fractional JSON numbers
is documented in the specification; original numeric spellings are not an
interchange guarantee.

These cases complement the Python tests; they are not exhaustive. Malformed JSON
text, duplicate object members, nonfinite numbers, invalid Unicode, and cyclic
in-memory objects are tested separately in `tests/test_companion.py`. Ordinary
JSON Schema validation alone does not enforce all of those input requirements.

From the repository root, run:

```sh
python3 -m unittest discover -s tests -p 'test_conformance.py' -v
```

The tests check every case against the full reference checker and the small
bundled schema evaluator. When the optional `jsonschema` test dependency is
installed, they also check every structural expectation against its draft
2020-12 validator. Keep the corpus synchronized with the specification and
schema when an intentional contract change occurs.
