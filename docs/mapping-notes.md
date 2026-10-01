# Mapping common attribution conventions into the format

**Informative.** This note shows how five conventions that companions already
use map into the annotation format (`docs/annotations.md`). It states no
requirement. Every snippet is synthetic and is a fragment of a document, not
a whole one; keys are in canonical order.

## 1. Docstring tags

The oldest convention is a tag in the docstring of a declaration:

```lean
/-- Theorem 1.2 (Sums commute). -/
theorem Notes.sum_comm (f : Fin m → Fin n → ℕ) : ... := by
```

Each tag gives one numbered item, one declaration and one `key` link. The
tag stays verbatim in `raw_label`; a page in the tag ("book p. 12") becomes
the link's `pages`, since one item's declarations can anchor different
pages. A parenthesised part, "Theorem 1.2 (ii)", becomes the link's `sub`,
never a separate item. A part with a prime, "Exercise 1.4 (b')", becomes
`sub: b'`, prime included; when the part is an item of its own, its id
carries the prime too (`exercise-1.4-b'`). A declaration tagged with two
items, "Lemma 2.3" and "Exercise 2.8" when the exercise is to prove the
lemma, gets two `key` links, one per item, and the two items are related
with `relations.same_as`. An unnumbered "In-text remark" tag becomes a
passage whose title is the tag's words (`title_source: producer`).

```json
{
  "items": [{"form": "numbered", "id": "theorem-1.2", "id_source": "label", "kind": "Theorem",
             "number": "1.2", "pages": {"anchor": "own", "basis": "printed", "first": 12},
             "source": "book-pdf", "title": "Sums commute"}],
  "links": [{"declaration": "Notes.sum_comm", "id": "theorem-1.2/key/Notes.sum_comm",
             "item": "theorem-1.2", "provenance": "prov-tags", "raw_label": "Theorem 1.2 (Sums commute)",
             "role": "key"}],
  "provenance": [{"actor": "tool", "confirmed_by_human": false, "id": "prov-tags",
                  "method": "docstring_tag", "tool": {"name": "tag-scanner", "version": "0.3"}}]
}
```

A declaration that carries no tag and is meant for the library goes to
`unattributed` with `claim: api`; one that only supports the build gets
`claim: infrastructure`.

## 2. A curated attribution table and a dependency graph

Some companions keep a table (CSV, JSON, a Markdown list) that pairs each
book item with declarations, and a dependency graph of their own with coarse
nodes: a section, a chapter, a proof cluster. The table becomes links with
`curation` provenance. The graph becomes the `graph` profile. Its file is
pinned in `companion.graph`, its nodes are `clusters`, and its edges are
`memberships` with the role the graph gives each member. Its
non-declaration nodes (a module docstring, a `#check`, a figure) are
`artifacts`.

```json
{
  "clusters": [{"id": "node-boxes", "items": ["definition-1.1"], "locator": "printed pp. 3-9",
                "title": "Boxes"}],
  "companion": {"commit": "a4f28654648ee1d140ba992f7d7c4089da15dc17",
                "generated_at": "2026-09-26T12:00:00Z", "generator": "table-export 1.0",
                "graph": {"path": "data/dependency-graph.json",
                          "sha256": "65d83e0e8c05fe7a5bb3ad6c7b6249805c5ef65008d7ae90fccdb506b7096312"},
                "name": "notes-companion", "repo": "git.example.org/example/notes-companion"},
  "memberships": [{"cluster": "node-boxes", "declaration": "Notes.Box", "id": "node-boxes/primary/Notes.Box",
                   "provenance": "prov-graph", "role": "primary"}],
  "profiles": {"graph": "1.0"}
}
```

An item the table does not pair with a declaration, but whose cluster has
members, is shown through its `clusters`; it needs no link. When the table
gives a class ("only the special case is done"), that is `coverage:
partial_only` with the partial statements as `attributed` links whose
`relation` is `special_case` or `part`. A graph node that names an anonymous
example the scan cannot find at the pinned commit is an `unlocated`
declaration with a declared id.

## 3. Blueprint `\lean{}` macros

A LaTeX blueprint writes, beside each statement, the declarations that
formalise it:

```latex
\begin{theorem}\label{thm:sum-comm}
  \lean{Notes.sum_comm}\leanok
  Finite sums commute.
\end{theorem}
```

The `.tex` file is a `tex` source pinned by `git_blob` (or `sha256`). The
theorem environment is a location with an RFC 5147 line range and a quote of
its first line; the `\lean{}` name is a `key` link with `blueprint_macro`
provenance. RFC 5147 positions are zero-based points between lines, so
editor lines 42 to 47 are `line=41,47`. The blueprint's `\uses{}` graph fits
the `graph` profile in the same way as section 2.

```json
{
  "locations": [{"id": "theorem-1.2@tex", "items": ["theorem-1.2"],
                 "target": {"selector": [
                   {"conformsTo": "http://tools.ietf.org/rfc/rfc5147", "type": "FragmentSelector",
                    "value": "line=41,47"},
                   {"exact": "\\begin{theorem}\\label{thm:sum-comm}", "type": "TextQuoteSelector"}],
                   "source": "blueprint-ch1"}}],
  "sources": [{"git_blob": "3cadbb64981a9ded5375be13a60a739eba24737d", "id": "blueprint-ch1",
               "kind": "tex", "path": "blueprint/src/chapter1.tex",
               "revision": "a4a20ca4d74657aa358cb7145d7d1381ac0c9240",
               "title": "Blueprint, chapter 1 (synthetic)"}]
}
```

## 4. In-Lean cross-reference attributes

An attribute such as `@[stacks 0123]` says a declaration states an entry of a
public database. The database is one `web` source, pinned by the `revision`
or `retrieved_at` the producer recorded. Each tag is one item, a passage or a
numbered item as the database numbers it, with an `xrefs` entry naming the
database and the tag. The attribute gives a `key` link. The `xrefs` entry is
what lets two documents, of two companions, pair the item (section 13 of the
specification).

```json
{
  "items": [{"form": "numbered", "id": "tag-0123", "id_source": "label", "kind": "Tag",
             "number": "0123", "quote": {"exact": "Lemma 0123."}, "source": "stacks-web",
             "xrefs": [{"database": "stacks", "tag": "0123"}]}],
  "links": [{"declaration": "Notes.exists_prime_ideal", "id": "tag-0123/key/Notes.exists_prime_ideal",
             "item": "tag-0123", "provenance": "prov-attr", "raw_label": "@[stacks 0123]", "role": "key"}],
  "sources": [{"id": "stacks-web", "kind": "web", "retrieved_at": "2026-09-01T08:00:00Z",
               "revision": "2026-09-01", "title": "A tag database (synthetic)",
               "url": "https://tags.example.org/tag/0123"}]
}
```

The core database names of `xrefs` (`stacks`, `kerodon`, `wikidata`,
`lmfdb`) are the ones Mathlib's cross-reference attributes use. Another
database name passes with a `W-XREF` warning. A companion that wants its own
in-Lean tags for a book defines an attribute and exports a document from it;
the format does not require one.

## 5. Per-statement annotations of a revision-pinned wiki article

A wiki article is annotated statement by statement, each annotation naming
the Mathlib declaration that formalises the statement. The article at one
revision is a `web` source pinned by `revision` (the `oldid`) and, when the
bytes were kept, `sha256`. Each annotated statement is a passage item with a
`quote_hash` id, located by a `TextQuoteSelector` and, as a second
alternative, a `CssSelector` of the element that holds it. The article's own
section heading goes in `item.section`. A statement that is "not
formalised, nearest result X" is `coverage: not_formalized` with a `support`
link of relation `related`, never a `key` link.

```json
{
  "items": [{"form": "passage", "id": "passage-15d8f8b4", "id_source": "quote_hash", "kind": "definition",
             "kind_source": "producer", "quote": {"exact": "an ideal whose complement is closed under multiplication",
             "prefix": "a prime ideal is "}, "section": "Definition", "source": "wiki-prime-ideal",
             "title": "Definition of a prime ideal", "title_source": "producer"}],
  "locations": [{"id": "passage-15d8f8b4@lead", "items": ["passage-15d8f8b4"],
                 "target": {"selector": [
                   {"exact": "an ideal whose complement is closed under multiplication",
                    "prefix": "a prime ideal is ", "type": "TextQuoteSelector"},
                   {"type": "CssSelector", "value": "#mw-content-text > p:nth-of-type(2)"}],
                   "source": "wiki-prime-ideal"}}],
  "sources": [{"id": "wiki-prime-ideal", "kind": "web", "retrieved_at": "2026-09-01T08:00:00Z",
               "revision": "1000001", "title": "Prime ideal (synthetic wiki page)",
               "url": "https://wiki.example.org/w/index.php?title=Prime_ideal&oldid=1000001"}]
}
```

The `quote_hash` id is the first 8 hex digits of the sha256 of the
normalised quote (section 7.2 of the specification). The annotation's
provenance string (a model, a moderated model, a person) becomes a provenance
record with `actor: agent` and `method: agent_annotation`, or
`actor: human`.
