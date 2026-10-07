# Documentation

Start with the [project overview](../README.md) and the
[worked example](../examples/tutorial/README.md). The current draft describes one
informal–formal association; it has no version field.

## Current format

- [Specification](companion.md): fields, source modes, selection semantics, and validation.
- [Discovery and storage](discovery.md): file selection, shard formats, and reference bases.
- [Python API](python.md): strict parsing, validation reports, and reading collections.
- [Conformance cases](../conformance/README.md): reusable cases for another implementation.
- [Design rationale](design/minimal-core.md): scope, alternatives, and consequences.
- [Integrations](integrations.md): how applications can use the same records.

## Existing data and development

- [Compatibility](compatibility.md): which formats and entry points are supported.
- [Migration](migration.md): explicit conversion from the original v1 graph.
- [Contributing](../CONTRIBUTING.md): development setup and review guidance.
- [Changelog](../CHANGELOG.md): package and draft history.

## Historical references

These explain earlier formats; they do not add requirements to the current one.

- [Legacy v1 specification](annotations.md) and [vocabulary](vocabulary.md).
- [PR #2 comparison](design/pr-2-synthesis.md), pinned to the commit reviewed there.
