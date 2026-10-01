# The conformance suite

Language-neutral test vectors for the formal-companion annotation format
(`docs/annotations.md`, section 11.5). An implementation in any language can
run them: a checker, a canonical writer or a scanner for statement-hash ids.
Every document and every Lean text here is synthetic.

## What is here

| directory | holds | defined in |
|---|---|---|
| `conformance/documents/` | small annotation documents and `manifest.json`, the checker's expected findings for each | `docs/annotations.md` sections 9 and 12 |
| `conformance/canonical/` | `cases.json`: JSON values and their canonical text | `docs/annotations.md` section 10 |
| `conformance/ids/` | statement-hash, declared-id, passage-id and item-label vectors | `docs/id-algorithm.md` section 15 |
| `conformance/js/` | a Node runner (`run.mjs`) and a reference canonical writer (`canonical.mjs`) | this file |

## Documents

`conformance/documents/valid/` holds documents a checker MUST accept,
`conformance/documents/invalid/` documents it MUST refuse, and
`conformance/documents/unreadable/` files that are not I-JSON and MUST be
refused before any checking (`validate.loads` raises `LoadError`; the CLI
exits 2). Valid documents are in canonical form. Every document derives from
`examples/annotations/minimal.json`.

`conformance/documents/manifest.json` is an array with one entry per file:

```json
{
  "file": "invalid/dangling-reference.json",
  "valid": false,
  "schema_valid": true,
  "exit_status": 1,
  "problems": [{"code": "I3", "path": "$.links[0].declaration"}],
  "warnings": [],
  "note": "A link to a declaration id that is not in declarations[]."
}
```

- `valid`: whether the document is valid (section 9). It is `true` exactly
  when `problems` is empty.
- `schema_valid`: whether plain JSON Schema validation against
  `schema/annotations-v1.0.schema.json` alone accepts the document, with no
  invariant and no forward mode. A JSON Schema validator such as ajv can be
  checked against it. It is `null` for an unreadable file. The manifest reads
  the schema's patterns as ECMA-262 does, where a trailing `$` means end of
  string (`docs/annotations.md` section 9.2); so does the reference checker's
  own evaluator. A validator that hands `pattern` to Python `re` unchanged,
  such as python-jsonschema, lets `$` also match before a final newline, and
  so reports `schema_valid: true` for the three
  `invalid/trap-*-trailing-newline.json` documents. The manifest is right and
  ajv agrees with it; such a validator needs `$` read as end of string before
  it can run the suite.
- `exit_status`: what the reference CLI exits with for this file: 0 valid, 1
  invalid, 2 unreadable.
- `problems`, `warnings`: the exact sets of `{"code", "path"}` pairs the
  checker reports, listed sorted by code then path. The order is not part of
  the expectation; the sets are. Messages are not pinned (they are not under
  semantic versioning; codes and paths are). Paths are JSON paths from `$`,
  as the checker writes them: `$.links[0].declaration`, `$.$schema`.
- `note`: why the document is in the suite.

Optional keys:

- `lints`: lints to run, for example `["external-urls"]`. The expected
  problems are those of a run with these lints; without them every listed
  document that carries the key would be valid.
- `canonical`: `true` when the checker is run as `--canonical` would, on the
  file's exact bytes (invariant I11). The one such file is valid without the
  flag and invalid with it (I11), because its bytes are not the canonical
  form.
- `unreadable`: `true` for the files under `unreadable/`. They are stored
  byte for byte (a byte-order mark, Latin-1 bytes, a `1e400` literal, a
  duplicate key, a lone surrogate escape, nesting 70 deep, `NaN`, an integer
  past 2^53 - 1). Their `problems` is `[{"code": "IJSON", "path": "$"}]`, what
  the CLI's `--format json` reports.
- `known_divergence`: present when a JSON Schema validator and the reference
  checker disagree on `schema_valid` and the suite records which is right
  (none at present; the Python `re` reading of `$` above is a difference of
  regex dialect, not recorded per entry).

The documents cover every problem code (`SCHEMA`, `I1` to `I9`, `I11` to
`I14`, `L1`, and `IJSON` through the unreadable files), every warning code
(`W-CONFORMS`, `W-MEDIA`, `W-RELATION`, `W-XREF`, `W-NEWER`, `W-SCHEMA-ID`),
each rule of invariant I5, invariant I4 on a passage with its numbered twin
valid (`valid/numbered-item-without-anchor.json`: a number locates a numbered
item), invariant I14 for each profile, a source `role` with no profile
declared (a core field), a `pdf` source pinned by `identifiers` alone (valid
with a `page=` fragment, invalid with a `PdfRegionSelector`), a `sub` with a
prime, the regex-dialect traps of section 9.2 (a trailing newline in an id, a
commit and `schema_version`; U+FEFF and U+001C in an id; a non-ASCII digit in
`page=`), one valid document per profile and one with all four, one valid
document per source kind (`pdf`, `web` page, `web` site, `tex`, `lean`,
`other`), and forward mode (`valid/newer-minor.json`: a `1.7` document whose
unknown key is a `W-NEWER` warning, which plain schema validation rejects).

## Canonical form

`conformance/canonical/cases.json` is an array of
`{"name", "input", "canonical"}`: any JSON value and the exact text the
canonical writer produces for it, final newline included. The cases pin the
number spellings of section 10 (`1e21` and `1e-7` where exponent notation
starts, `5e-324`, `-0` written `0`, `2^53 - 1`, `0.1 + 0.2`, `1.0` written
`1`, `1e20` written in full), string escapes (control characters, `"` and
`\`, U+2028 and U+2029 written raw, astral characters raw), key order by
UTF-16 code units (an astral key before a U+E000 key; `"10"` before `"9"`
before `"a"`), empty containers and nested arrays. A case's `input` is any
JSON value, so load the file with a plain JSON parser, not an I-JSON loader
(one input is `1e20`, outside the I-JSON integer range). The cases exercise
the writer only: record arrays, sorted sets and keyed lists are given already
in order (`validate.canonicalize` sorts them; `validate.canonical_dumps` is
the writer).

## Ids

`conformance/ids/*.json` are the scanner and id vectors. Their shapes (scan,
multi-file scan, hash form, display form, named signature, passage, item
label, normalize text) are defined in `docs/id-algorithm.md` section 15,
which is normative for them; this file does not repeat it.

## Running the suite

From the repository root, against the Python package:

```sh
python3 -m pytest tests/test_conformance.py     # documents and canonical cases
python3 -m pytest tests/test_ids.py             # the ids vectors
```

`tests/test_conformance.py` also runs under
`python3 -m unittest discover -s tests`, with nothing installed. It checks
every manifest entry (problem and warning sets, `schema_valid` through the
package's own schema evaluator, the CLI exit status, the unreadable files
through `validate.loads`), every canonical case through
`validate.canonical_dumps`, and that the manifest covers what this file says
it covers.

Under Node (22 or later), with no network use after the install:

```sh
cd conformance/js && npm ci && cd ../..
node conformance/js/run.mjs
```

`run.mjs` validates every document of the manifest against the schema with
ajv (draft 2020-12, strict mode with `strictRequired` and `strictTypes`
relaxed for two of ajv's style rules; the comment in `run.mjs` says which)
and checks `schema_valid`; validates every
valid example under `examples/annotations/` and reports the `invalid-*` ones
(some fail only on an invariant, so the schema may accept them); runs every
canonical case through `canonical.mjs`, a reference writer written from
section 10 alone; and checks every `hash_form` against its
`statement_sha256` in the ids vectors with Node's `crypto`. It exits 1 on
any mismatch and prints each. It does not scan Lean text: a JavaScript
scanner is out of scope, and the ids vectors are run by `tests/test_ids.py`.
The unreadable files are skipped there, since an I-JSON loader is outside
what a schema validator checks.

`conformance/js/package.json` depends on `ajv` and `ajv-formats` only, with
no install scripts; `package-lock.json` pins them for `npm ci`.
The `node_modules/` directory that `npm ci` creates under `conformance/js/` is
ignored by git and left out of the sdist (`MANIFEST.in` prunes it). CI runs
both sides on every push (`.github/workflows/tests.yml`: the Python jobs and
`conformance-node`).

## Adding a case

Derive a document from `examples/annotations/minimal.json`, keep it synthetic
and small, write valid ones in canonical form
(`formal-companion-annotations-validate --print-canonical`), and add its
manifest entry with the exact codes and paths. `tests/test_conformance.py`
fails until the entry and the checker agree, and `node conformance/js/run.mjs`
until `schema_valid` agrees with ajv. A new canonical case needs only its
`input`; generate `canonical` with `validate.canonical_dumps` and review it
against section 10.
