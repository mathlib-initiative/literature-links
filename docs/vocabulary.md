# Vocabulary of the annotation format

Every enum of `schema/annotations-v1.schema.json` is a set in
`src/formal_companion_annotations/vocab.py`. **The format owns every value it uses.**
A new value is a minor version; a value removed or given another meaning is a major version.

---

## 1. The annotation enums (`lean-companion/annotations`, schema_version `1.0`)

The enums of `schema/annotations-v1.schema.json`, specified in `docs/annotations.md`:
`vocab.ANNOTATION_*`. The sets the format shares with the skill are defined in section 2
rather than repeated here: a verdict record's `verdict` and each `declarations[].verdict` are
`VIEWER_VERDICTS`, its `severity` and `status` are `VIEWER_SEVERITIES` and `VIEWER_STATUS`, its
`ledger_verdict` is `LEDGER_VERDICTS` and its `finding_kind` `FINDING_KINDS`; a source's `role`
is `SOURCE_ROLES`; a declaration's `sorry` is `SORRY_CLASSES` (`exercise` | `gap` | `none`). Two
fields are open rather than enums, each with a documented core: a link's `relation`, a
lower-case snake_case token, and a FragmentSelector's `conformsTo`, an IRI. A value outside the
core passes with a warning.

| field | values |
|---|---|
| source `kind` | `pdf` \| `web` \| `tex` \| `lean` \| `other` (named by `media_type`) |
| source `scope` | `page` \| `site` (web only) |
| item `form` | `numbered` \| `passage` |
| item `id_source` | `label` \| `quote_hash` \| `page_title_hash` \| `declared` |
| item `kind_source`, `title_source` | `source` \| `producer` |
| item `relations` keys | `same_as` \| `part_of` \| `near` |
| item `coverage` | `formalized` \| `partial` \| `not_formalized` \| `out_of_scope` \| `support_only` \| `example_only` (the fallback to an item's clusters is the separate boolean `cluster_fallback`) |
| `pages.basis` | `printed` \| `physical` |
| `pages.anchor` | `own` \| `crossref` \| `inferred` |
| link `role` | `key` \| `attributed` \| `support` \| `example` \| `helper` |
| link `relation` (an open lower-case snake_case token; the core) | `exact` \| `generalization` \| `special_case` \| `invocation` \| `related` |
| declaration `kind` | `theorem` \| `lemma` \| `def` \| `abbrev` \| `structure` \| `class` \| `inductive` \| `instance` \| `example` \| `opaque` \| `axiom` \| `field` \| `projection` |
| declaration `id_source` | `name` \| `private` \| `statement_hash` \| `declared` |
| artifact `kind` | `module_doc` \| `check` \| `figure` \| `other` |
| membership `role` | `primary` \| `support` \| `consumer` |
| unattributed `claim` | `unattributed` \| `api` \| `infrastructure` |
| provenance `actor` | `author` \| `agent` \| `human` \| `tool` |
| provenance `method` | `docstring_tag` \| `curation` \| `blueprint_macro` \| `lean_scan` \| `layout_extraction` \| `text_match` \| `manual` \| `agent_annotation` \| `pipeline` \| `adjudication` \| `site_index` |
| verdict `resolution.state` | `open` \| `fixed` \| `in_progress` \| `refuted` \| `argued_correct` \| `out_of_scope` (defined in section 2.8, from `STATIC_RESOLUTIONS` and `RESOLUTION_PREFIXES`; a verdict with no `resolution` is open) |
| destination `site` | `verso_literate` \| `doc_gen4` \| `blueprint` \| `other` |
| changelog `event` | `born` \| `retired` \| `restated` \| `renamed` \| `ordinal_assigned` |
| changelog `subject_kind` | `declaration` \| `item` \| `location` \| `artifact` |
| changelog `reason` | `statement_changed` \| `removed` \| `renamed` \| `moved` \| `other` |
| selector `type` | `FragmentSelector` \| `TextQuoteSelector` \| `TextPositionSelector` \| `DataPositionSelector` \| `CssSelector` \| `XPathSelector` \| `SvgSelector` \| `RangeSelector`, plus the extensions `PdfRegionSelector` and `SitePageSelector` |
| `coordinate_space.origin` | `top_left` \| `bottom_left` (`top_left` goes with `y_axis` `down`, `bottom_left` with `up`) |
| `coordinate_space.units` | `normalized` (fractions of the page box) \| `pt` (points) |
| `coordinate_space.x_axis` | `right` |
| `coordinate_space.y_axis` | `down` \| `up` |
| `coordinate_space.page_box` | `MediaBox` \| `CropBox` \| `BleedBox` \| `TrimBox` \| `ArtBox` |
| `text_layer.unicode` | `none` \| `nfc` \| `nfkc` |
| `text_layer.whitespace` | `exact` \| `collapse` \| `ignore` |
| `text_layer.case` | `sensitive` \| `insensitive` |
| destination `resolution` | `exact` (needs a `fragment`) \| `fallback` (needs a `fallback_label`) |
| `conformsTo` with a grammar check (open) | `http://tools.ietf.org/rfc/rfc8118` and its synonym `http://tools.ietf.org/rfc/rfc3778` (PDF), `http://tools.ietf.org/rfc/rfc5147` (text), `http://tools.ietf.org/rfc/rfc3236` (HTML id), `http://www.w3.org/TR/media-frags/` (Media Fragments) |

---

## 2. The shared sets

Shared with the formal-companion skill; defined here.

### 2.1 `VIEWER_VERDICTS`: a verdict's `verdict`

| value | meaning |
|---|---|
| `faithful` | the declarations state what the item says: no defect was found, or the finding was refuted (`REFUTED`) |
| `convention` | the declarations differ from the text only by an encoding or degenerate-case choice whose recovery argument is written down, or the printed text is what diverges (`CONVENTION`, `ERRATA`) |
| `attribution_gap` | a faithful statement exists, but not in the declaration attributed to the item: the fix is naming, not mathematics (`ATTRIBUTION_GAP`) |
| `proxy` | the declarations are about a stand-in: a library object adopted as the item's notion, whether or not an equivalence to the source's notion is proved (finding kind `PROXY`) |
| `deviation` | the declarations assert something materially different from the text, or leave out a main clause (`CONFIRMED_CONTENT`) |

### 2.2 `VIEWER_SEVERITIES`: a verdict's `severity`

Ordered `none` < `low` < `medium` < `high`.

| value | meaning |
|---|---|
| `none` | no defect to weigh: the verdict is `faithful`, or the finding was refuted |
| `low` | a real defect of the least weight, such as an attribution gap where a faithful declaration exists, or a proxy with a proved bridge |
| `medium` | a real defect of middle weight, such as a proxy with no bridge, or a notion the companion does not define at all |
| `high` | a real defect of the greatest weight, such as one that changes what the item's main claim says |

### 2.3 `VIEWER_STATUS`: a verdict's `status`

| value | meaning |
|---|---|
| `unconfirmed` | the verdict stands as a machine pass wrote it: nobody has contested it, a human has not confirmed it, and it is not fixed |
| `contested` | the adjudication recorded dissent it did not settle |
| `human_confirmed` | a human confirmed the verdict; a machine pass never writes it |
| `fixed` | the defect is fixed in the companion; the verdict's `resolution.state` is then `fixed` |

### 2.4 `LEDGER_VERDICTS`: a verdict's `ledger_verdict`

| value | meaning |
|---|---|
| `CONFIRMED_CONTENT` | the Lean asserts something materially different from the source, or a main clause is missing |
| `ATTRIBUTION_GAP` | a faithful statement exists in the repository, but the declaration attributed to the item does not state it: the fix is naming, not mathematics |
| `CONVENTION` | an encoding or degenerate-case choice: the source's claim is recoverable, and the recovery argument is written down |
| `ERRATA` | the printed text is what diverges; the errata entry decides it |
| `REFUTED` | the finding's factual premise is wrong (misread Lean, misread source, wrong edition) |
| `UNSURE` | adjudicated and undecided; the verdict's `summary` says what would decide it |

### 2.5 `FINDING_KINDS`: a verdict's `finding_kind`

| value | meaning |
|---|---|
| `CONTENT` | the Lean states something other than the source's claim; the evidence is a quote of the source and a witness |
| `VACUITY` | the statement is vacuous or trivially true; the witness is the instance that makes it so |
| `PROXY` | a definition stands in for the source's notion: a library object adopted as the definition, with a bridge to the source's notion that is proved, taken by fiat, or missing |
| `SUSPECTED_ERRATA` | the divergence may be the printed text's; the evidence cites the errata entry by date and URL |
| `COVERAGE` | no declaration formalises the item; the evidence is the item and its page |
| `PAGE_ANCHOR` | a page anchor in the companion names the wrong page of its anchor edition; found by a mechanical check, never by a model |

### 2.6 `SOURCE_ROLES`: a source's `role`

| value | meaning |
|---|---|
| `audited` | at least one companion is checked against this source |
| `reference` | prepared only so that a page map to a sibling edition can be checked, and audited by nobody: an edition a repository bundles but does not anchor to |

### 2.7 `SORRY_CLASSES`: a declaration's `sorry`

| value | meaning |
|---|---|
| `exercise` | the declaration's proof holds a `sorry` left on purpose, for an exercise the reader is to do; a companion's policy may keep it permanently |
| `gap` | the declaration's proof holds a `sorry` that stands for work not done yet |
| `none` | the declaration holds no `sorry` |

### 2.8 Resolution states: a verdict's `resolution.state`

`open`, `STATIC_RESOLUTIONS` (`refuted`, `argued_correct`, `out_of_scope`), and
`RESOLUTION_PREFIXES` (`fixed:`, `in_progress:`) without the colon.

| value | meaning |
|---|---|
| `open` | nobody has resolved the verdict; a verdict with no `resolution` is open too |
| `fixed` | the defect is fixed; the resolution names the `pr` or the `commits` |
| `in_progress` | a fix is under way; the resolution names the `pr` or the `branch` |
| `refuted` | the finding's premise was wrong, so there is nothing to fix |
| `argued_correct` | the owner answered the finding rather than fixing it: the statement is argued to be right as it stands |
| `out_of_scope` | the finding concerns something outside what the companion sets out to formalise, and is closed without a fix |

---
