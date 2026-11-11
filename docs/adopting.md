# Adopting Literature Links

A formal library that already cites the literature, in docstrings or in
attributes such as Mathlib's `@[stacks]`, can turn those references into
annotations. The [specification](companion.md) says what an annotation may
contain. This page says how to convert existing references without claiming
more than they say.

1. **List what the library has.** Count each kind of reference: "References"
   sections in module docstrings, declaration docstrings that cite a numbered
   result, cross-reference attributes, blueprint entries, external tables.
   Convert one kind at a time, with a script wherever the source is regular.
2. **Give the annotations a folder of their own.** Any name works;
   `annotations/` is usual. Every `.json`, `.jsonl` and `.ndjson` file under it
   is read as annotations, so keep other JSON out ([Discovery](tools.md#discovery)).
   Put the library and its version in a `_defaults.json`
   ([Folder defaults](companion.md#folder-defaults)).
3. **Link only what the reference says.** A reference on a declaration, in its
   docstring or an attribute, links that declaration by its full name. A
   reference in a module docstring links the module, unless it names a
   declaration; it does not say which declaration it means.
4. **Pin the library.** A `lean` end's `version` is a release tag or a full
   commit, not a branch ([Lean](companion.md#lean)).
5. **Locate the passage only as far as it has been checked.** Give a page,
   quote, label or fragment after finding the passage there. A reference that
   gives only a number, such as "Theorem 1.20", becomes an end with no
   `location`, the whole work, with the number in the annotation's `id`.
6. **Add a relation only after comparing the two statements.** A reference says
   that the two sides correspond, which is what an annotation without a
   `relation` claims ([Relation](companion.md#relation)). A `noMatch` needs a
   search of the library at a known version.
7. **Check.** `literature-links scan` checks the form. It does not check that a
   declaration exists at the pinned version or that a page holds the passage, so
   check those too, for a sample at least. Running the scan in CI keeps the
   folder valid.

An end template in a `_defaults.json` fills only the ends that have no `uri` of
their own. A link to a Stacks tag or a Wikipedia article has its own `uri`, so
it takes nothing from a template, not even its `type`, and is written in full.

For example, TauCeti tags its definition of a normal scheme with
`@[stacks 033I]`. With this `annotations/_defaults.json`:

```json
{ "object": { "type": "lean", "uri": "https://github.com/TauCetiProject/TauCeti",
              "version": "37f5e9dce5ac83d2825198ac72d7f5d64eb26c85" } }
```

the tag becomes this annotation, which claims what the tag claims and no more:

```json
{ "subject": [ { "type": "html", "uri": "https://stacks.math.columbia.edu/tag/033I" } ],
  "object": [ { "location": { "declaration": "TauCeti.AlgebraicGeometry.IsNormalScheme" } } ],
  "kind": "definition" }
```
