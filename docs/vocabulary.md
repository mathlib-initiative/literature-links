# Vocabulary of the annotation format

Every closed set of values in `schema/annotations-v1.0.schema.json` is
defined once, in `src/formal_companion_annotations/vocab.py`, and named
here. The schema repeats the values because it is data a reader in any
language can use. `tests/test_annotations_schema.py` walks every `enum` in
the schema and fails when one has no set in that module or the two disagree.
A test also fails when a value of section 1 is missing here, or when a value
of section 2 has no meaning.

**The format owns every value it uses.** A change to a set is a change to the
format, made here first. A new value is a new minor version at least; a value
removed or given another meaning is a new major version (section 12 of
`docs/annotations.md`). A producer that writes a value this file does not
list writes an invalid document.

Three fields are open rather than enums, each with a documented core: a link's
`relation` and an xref's `database`, both lower-case snake_case tokens, and a
FragmentSelector's `conformsTo`, an IRI. A value outside the core passes with
a warning (`W-RELATION`, `W-XREF`, `W-CONFORMS`).

**Contents**: 1 the enums · 2 the audit, source and declaration sets: 2.1
verdicts · 2.2 severities · 2.3 verdict statuses · 2.4 resolution states ·
2.5 source roles · 2.6 sorry classes

---

## 1. The enums (`formal-companion/annotations`, schema_version `1.0`)

The sets of `vocab.py` (`ANNOTATION_*`), as `docs/annotations.md` specifies
them. The six sets of section 2 are listed here and defined there.

| field | values |
|---|---|
| root `profiles` keys | `audit` \| `graph` \| `history` \| `site` (each with its own `"1.<minor>"`; the package knows `1.0` of each) |
| source `kind` | `pdf` \| `web` \| `tex` \| `lean` \| `other` (named by `media_type`) |
| source `scope` | `page` \| `site` (web only) |
| source `role` | `audited` \| `reference` (section 2.5; a core field, not an audit one) |
| item `form` | `numbered` \| `passage` |
| item `id_source` | `label` \| `quote_hash` \| `page_title_hash` \| `declared` |
| item `kind_source`, `title_source` | `source` \| `producer` |
| item `relations` keys | `same_as` \| `part_of` \| `near` |
| item `coverage` | `formalized` \| `partial_only` \| `support_only` \| `example_only` \| `private_only` \| `not_formalized` \| `out_of_scope` |
| item `xrefs[].database` (an open lower-case snake_case token; the core) | `stacks` \| `kerodon` \| `wikidata` \| `lmfdb` |
| `pages.basis` | `printed` \| `physical` |
| `pages.anchor` | `own` \| `crossref` \| `inferred` |
| link `role` | `key` \| `attributed` \| `support` \| `example` \| `helper` |
| link `relation` (an open lower-case snake_case token; the core) | `exact` \| `generalization` \| `special_case` \| `part` \| `invocation` \| `related` |
| declaration `kind` | `theorem` \| `lemma` \| `def` \| `abbrev` \| `structure` \| `class` \| `inductive` \| `instance` \| `example` \| `opaque` \| `axiom` \| `alias` \| `irreducible_def` \| `field` \| `projection` \| `constructor` \| `recursor` |
| declaration `parent` kinds, by member kind | `field`, `projection`: `structure` \| `class`; `constructor`, `recursor`: `inductive` \| `structure` \| `class` |
| declaration `id_source` | `name` \| `private` \| `statement_hash` \| `declared` |
| declaration `sorry` | `exercise` \| `gap` \| `none` (section 2.6) |
| artifact `kind` (graph profile) | `module_doc` \| `check` \| `figure` \| `other` |
| membership `role` (graph profile) | `primary` \| `support` \| `consumer` |
| unattributed `claim` | `unattributed` \| `api` \| `infrastructure` |
| provenance `actor` | `author` \| `agent` \| `human` \| `tool` |
| provenance `method` | `docstring_tag` \| `curation` \| `blueprint_macro` \| `lean_scan` \| `layout_extraction` \| `text_match` \| `manual` \| `agent_annotation` \| `pipeline` \| `adjudication` \| `site_index` |
| verdict `verdict`, `declarations[].verdict` (audit profile) | `faithful` \| `convention` \| `attribution_gap` \| `proxy` \| `deviation` (section 2.1) |
| verdict `severity` (audit profile) | `none` \| `low` \| `medium` \| `high` (section 2.2) |
| verdict `status` (audit profile) | `unconfirmed` \| `contested` \| `human_confirmed` \| `fixed` (section 2.3) |
| verdict `resolution.state` (audit profile) | `open` \| `fixed` \| `in_progress` \| `refuted` \| `argued_correct` \| `out_of_scope` (section 2.4; a verdict with no `resolution` is open) |
| destination `site` (site profile) | `verso_literate` \| `doc_gen4` \| `blueprint` \| `other` |
| destination `resolution` (site profile) | `exact` (needs a `fragment`) \| `fallback` (needs a `fallback_label`) |
| changelog `event` (history profile) | `born` \| `retired` \| `restated` \| `renamed` \| `ordinal_assigned` |
| changelog `subject_kind` (history profile) | `declaration` \| `item` \| `location` \| `artifact` |
| changelog `reason` (history profile) | `statement_changed` \| `removed` \| `renamed` \| `moved` \| `other` |
| selector `type` | `FragmentSelector` \| `TextQuoteSelector` \| `CssSelector`, plus the extensions `PdfRegionSelector` and `SitePageSelector` |
| `coordinate_space.origin` | `top_left` \| `bottom_left` (`top_left` goes with `y_axis` `down`, `bottom_left` with `up`) |
| `coordinate_space.units` | `normalized` (fractions of the page box) \| `pt` (points) |
| `coordinate_space.x_axis` | `right` |
| `coordinate_space.y_axis` | `down` \| `up` |
| `coordinate_space.page_box` | `MediaBox` \| `CropBox` \| `BleedBox` \| `TrimBox` \| `ArtBox` |
| `text_layer.unicode` | `none` \| `nfc` \| `nfkc` |
| `text_layer.whitespace` | `exact` \| `collapse` \| `ignore` |
| `text_layer.case` | `sensitive` \| `insensitive` |
| `conformsTo` with a grammar check (open) | `http://tools.ietf.org/rfc/rfc8118` and its synonym `http://tools.ietf.org/rfc/rfc3778` (PDF), `http://tools.ietf.org/rfc/rfc5147` (text), `http://tools.ietf.org/rfc/rfc3236` (HTML id), `http://www.w3.org/TR/media-frags/` (Media Fragments) |

The meaning of an item's `coverage` value is in `docs/annotations.md`
section 5.2, and invariant I5 (section 5.4) ties it to the item's links.
`example_only` is for an item whose only formalisations are anonymous
`example` declarations that the producer links with role `example`, not
`key`. An anonymous example MAY be a `key` link's target: it then states the
item, and the item is `formalized`.

---

## 2. The audit, source and declaration sets

The `verdicts` record of the `audit` profile (section 8.3 of
`docs/annotations.md`) records the adjudicated outcome of checking an item's
declarations against its source. Its vocabulary is the format's own: how a
producer arrives at a verdict is its own method, which the verdict's
`provenance` names. A producer's finer categories (finding kinds, finding
ids, adjudication outcomes) go in `x_` keys. A source's `role` (2.5) and a
declaration's `sorry` (2.6) are core fields.

| set | where the format uses it |
|---|---|
| `ANNOTATION_VERDICTS` | a verdict's `verdict` and each `declarations[].verdict` (2.1) |
| `ANNOTATION_SEVERITIES` | a verdict's `severity` (2.2) |
| `ANNOTATION_VERDICT_STATUSES` | a verdict's `status` (2.3) |
| `ANNOTATION_RESOLUTION_STATES` | a verdict's `resolution.state` (2.4) |
| `ANNOTATION_SOURCE_ROLES` | a source's `role` (2.5) |
| `ANNOTATION_SORRY_CLASSES` | a declaration's `sorry` (2.6) |

### 2.1 `ANNOTATION_VERDICTS`: a verdict's `verdict`

The verdict on an item, and on each declaration the verdict names.

| value | meaning |
|---|---|
| `faithful` | the declarations state what the item says: no defect was found, or a suspected defect was refuted |
| `convention` | the declarations differ from the text only by an encoding or degenerate-case choice whose recovery argument is written down, or the printed text is what diverges and an errata entry says so |
| `attribution_gap` | a faithful statement exists in the companion, but not in the declaration attributed to the item: the fix is naming, not mathematics |
| `proxy` | the declarations are about a stand-in: a library object adopted as the item's notion, whether or not an equivalence to the source's notion is proved |
| `deviation` | the declarations assert something materially different from the text, or leave out a main clause |

### 2.2 `ANNOTATION_SEVERITIES`: a verdict's `severity`

Four levels, ordered `none` < `low` < `medium` < `high`. The format fixes the
levels and their order; how a producer weighs a defect is its own method.

| value | meaning |
|---|---|
| `none` | no defect to weigh: the verdict is `faithful`, or the suspected defect was refuted |
| `low` | a real defect of the least weight, such as an attribution gap where a faithful declaration exists, or a proxy with a proved bridge |
| `medium` | a real defect of middle weight, such as a proxy with no bridge, or a notion the companion does not define at all |
| `high` | a real defect of the greatest weight, such as one that changes what the item's main claim says |

### 2.3 `ANNOTATION_VERDICT_STATUSES`: a verdict's `status`

| value | meaning |
|---|---|
| `unconfirmed` | the verdict stands as a machine pass wrote it: nobody has contested it, no human has confirmed it, and it is not fixed |
| `contested` | the adjudication recorded dissent it did not settle |
| `human_confirmed` | a human confirmed the verdict; a machine pass never writes it |
| `fixed` | the defect is fixed in the companion; the verdict's `resolution.state` is then `fixed` |

### 2.4 Resolution states: a verdict's `resolution.state`

`vocab.ANNOTATION_RESOLUTION_STATES`. `resolution` is optional: a verdict
without one is open. A `fixed` resolution names the `pr` or the `commits`;
an `in_progress` one names the `pr` or the `branch`.

| value | meaning |
|---|---|
| `open` | nobody has resolved the verdict; a verdict with no `resolution` is open too |
| `fixed` | the defect is fixed; the resolution names the `pr` or the `commits` |
| `in_progress` | a fix is under way; the resolution names the `pr` or the `branch` |
| `refuted` | the suspected defect's premise was wrong, so there is nothing to fix |
| `argued_correct` | the owner answered the finding rather than fixing it: the statement is argued to be right as it stands |
| `out_of_scope` | the finding concerns something outside what the companion sets out to formalise, and is closed without a fix |

### 2.5 `ANNOTATION_SOURCE_ROLES`: a source's `role`

What a source is for. The field is core (section 5.1 of
`docs/annotations.md`): a document with no verdicts MAY still say which
source it audits or keeps as a reference.

| value | meaning |
|---|---|
| `audited` | at least one companion is checked against this source |
| `reference` | prepared only so that a page map to a sibling edition can be checked, and audited against by nobody: an edition a repository bundles but does not anchor to |

### 2.6 `ANNOTATION_SORRY_CLASSES`: a declaration's `sorry`

| value | meaning |
|---|---|
| `exercise` | the declaration's proof holds a `sorry` left on purpose, for an exercise the reader is to do; a companion's policy may keep it permanently |
| `gap` | the declaration's proof holds a `sorry` that stands for work not done yet |
| `none` | the declaration holds no `sorry` |

---
