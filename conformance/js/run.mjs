#!/usr/bin/env node
// The conformance suite under Node (conformance/README.md):
//
//   1. every document of conformance/documents/manifest.json against
//      schema/annotations-v1.0.schema.json with ajv (draft 2020-12), checking
//      the manifest's `schema_valid` (plain schema validation, no invariants);
//   2. every valid example under examples/annotations/ passes the schema; the
//      invalid-* examples are reported but not required to fail, since some
//      fail only on an invariant;
//   3. every case of conformance/canonical/cases.json through canonical.mjs;
//   4. every (hash_form, statement_sha256) pair in conformance/ids/*.json:
//      sha256 of the UTF-8 of hash_form is statement_sha256.
//
// Unreadable documents (not I-JSON) are skipped: an I-JSON loader is outside
// what a schema checks.  Exit status 1 on any mismatch, each one printed.
import { readFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { canonical } from "./canonical.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
const SCHEMA = "schema/annotations-v1.0.schema.json";

let checks = 0;
let failures = 0;
const pass = () => { checks += 1; };
const fail = (message) => { failures += 1; console.log(`FAIL ${message}`); };
const readText = (rel) => readFileSync(path.join(ROOT, rel), "utf8");
const readJson = (rel) => JSON.parse(readText(rel));
const firstErrors = (errors, n = 3) =>
  (errors ?? []).slice(0, n).map((e) => `${e.instancePath || "$"} ${e.message}`).join("; ");

// 1. the documents against the schema -------------------------------------------
// Strict mode, with two of its style rules off; neither changes what validates:
//   - strictRequired refuses a `required` whose property is defined in the
//     enclosing object rather than in the `then` subschema itself, and the
//     schema states its conditional rules as `if {...} then {required: [...]}`;
//   - strictTypes refuses a `pattern` in an `allOf` member that does not repeat
//     `type: "string"`, and the schema writes `allOf: [{$ref}, {pattern}]`.
const ajv = new Ajv2020({ strict: true, strictRequired: false, strictTypes: false, allErrors: true });
addFormats(ajv);
const validate = ajv.compile(readJson(SCHEMA));
const manifest = readJson("conformance/documents/manifest.json");
let skipped = 0;
for (const entry of manifest) {
  const file = `conformance/documents/${entry.file}`;
  if (entry.unreadable) {
    skipped += 1;
    continue;
  }
  const doc = JSON.parse(readText(file));
  const ok = validate(doc);
  if (ok === entry.schema_valid) {
    pass();
  } else if (entry.known_divergence) {
    console.log(`note ${file}: ajv says schema_valid=${ok}, the manifest says ${entry.schema_valid}: ${entry.known_divergence}`);
    pass();
  } else {
    fail(`${file}: ajv says schema_valid=${ok}, the manifest says ${entry.schema_valid}`
      + (ok ? "" : ` (${firstErrors(validate.errors)})`));
  }
}
console.log(`documents: ${manifest.length - skipped} checked against the schema, ${skipped} unreadable skipped`);

// 2. the examples ------------------------------------------------------------------
const examples = readdirSync(path.join(ROOT, "examples/annotations")).filter((n) => n.endsWith(".json")).sort();
let invalidExamples = 0;
for (const name of examples) {
  const file = `examples/annotations/${name}`;
  const ok = validate(JSON.parse(readText(file)));
  if (name.startsWith("invalid-")) {
    invalidExamples += 1;
    console.log(`     ${file}: schema ${ok ? "accepts it (it fails on an invariant)" : "rejects it"}`);
  } else if (ok) {
    pass();
  } else {
    fail(`${file}: the schema rejects a valid example (${firstErrors(validate.errors)})`);
  }
}
console.log(`examples: ${examples.length - invalidExamples} valid ones pass the schema, ${invalidExamples} invalid ones reported`);

// 3. the canonical writer ---------------------------------------------------------
const cases = readJson("conformance/canonical/cases.json");
for (const c of cases) {
  const got = canonical(c.input);
  if (got === c.canonical) {
    pass();
  } else {
    fail(`canonical case ${JSON.stringify(c.name)}: got ${JSON.stringify(got)}, expected ${JSON.stringify(c.canonical)}`);
  }
}
console.log(`canonical: ${cases.length} cases`);

// 4. the statement-hash vectors --------------------------------------------------
const sha256 = (text) => createHash("sha256").update(text, "utf8").digest("hex");
let pairs = 0;
function walk(node, where) {
  if (Array.isArray(node)) {
    node.forEach((child, i) => walk(child, `${where}[${i}]`));
    return;
  }
  if (node === null || typeof node !== "object") return;
  if (typeof node.hash_form === "string" && typeof node.statement_sha256 === "string") {
    pairs += 1;
    const got = sha256(node.hash_form);
    if (got === node.statement_sha256) {
      pass();
    } else {
      fail(`${where}: sha256 of hash_form ${JSON.stringify(node.hash_form)} is ${got}, not ${node.statement_sha256}`);
    }
  }
  for (const [key, child] of Object.entries(node)) walk(child, `${where}.${key}`);
}
const vectorFiles = readdirSync(path.join(ROOT, "conformance/ids")).filter((n) => n.endsWith(".json")).sort();
for (const name of vectorFiles) walk(readJson(`conformance/ids/${name}`), `conformance/ids/${name}`);
console.log(`ids: ${pairs} (hash_form, statement_sha256) pairs in ${vectorFiles.length} files`);

// ---------------------------------------------------------------------------------
console.log(`${checks} checks, ${failures} failures`);
process.exit(failures === 0 ? 0 : 1);
