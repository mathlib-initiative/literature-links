# Adopting Literature Links

A library that already cites the literature, in docstrings or in attributes
such as Mathlib's `@[stacks]`, can turn each citation into one annotation.

Make a folder for the annotations, such as `annotations/`, and name the library
and its version once, in `annotations/_defaults.json`:

```json
{ "object": { "type": "lean", "uri": "https://github.com/TauCetiProject/TauCeti",
              "version": "37f5e9dce5ac83d2825198ac72d7f5d64eb26c85" } }
```

TauCeti tags `IsNormalScheme` with `@[stacks 033I]`, which becomes:

```json
{ "subject": [ { "type": "html", "uri": "https://stacks.math.columbia.edu/tag/033I" } ],
  "object": [ { "location": { "declaration": "TauCeti.AlgebraicGeometry.IsNormalScheme" } } ] }
```

The subject gives its own `uri`, so it takes nothing from the defaults and
states its `type` itself. A short script over the library's sources usually
writes all of these.

`literature-links scan annotations/` checks the folder, and can run in CI. It
checks the format, not that the declarations exist.

An annotation claims only that its sides correspond. Add a `relation` after
comparing the two statements, and a `location` for a passage found in the
document. A citation in a module docstring links the module,
`{ "module": "…" }`, rather than a guessed declaration.
