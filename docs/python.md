# Python API

The package requires Python 3.11 or newer and has no runtime dependencies.
Install it from a checkout as shown in [the README](../README.md).

## Read and validate one annotation

```python
from pathlib import Path
from formal_companion_annotations import companion

path = Path("examples/companion/latex.json")
annotation = companion.loads(path.read_text(encoding="utf-8"))
report = companion.check(annotation)

if report.problems:
    for problem in report.problems:
        print(problem.code, problem.path, problem.message)
else:
    print(annotation["source"]["uri"], "->", annotation["target"])
```

`loads(text)` is a strict JSON decoder, not schema validation. It raises
`companion.LoadError`, a `ValueError`, for malformed or unsupported JSON, including
duplicate object keys, nonfinite numbers, unpaired Unicode surrogates, and
nonzero numbers too small for a Python float to retain as nonzero.
Use it before `check`: once an ordinary JSON parser has discarded duplicate keys,
a checker cannot recover that information.

`check(value)` returns a `Report` containing `problems` and `warnings`. Any problem
makes the annotation invalid; warnings are currently empty. Each `Problem` has
`code`, `path`, and `message`. Codes identify the kind of failure; messages explain
it to a person. Paths locate the value within the record. See the
[specification](companion.md#validation-and-serialization) for the checks.

`validate(value)` returns the same problems as a list of readable strings.
Neither function changes the input or accesses the network. A missing or invalid
installed schema is an installation error, not evidence that the input is invalid.

## Read a directory of annotations

```python
from formal_companion_annotations import discovery

collection = discovery.collect(["examples/companion"])
if collection.problems:
    for problem in collection.problems:
        print(problem.code, problem.path, problem.message)
    raise SystemExit("The selected inputs were not all valid.")

for record in collection.records:
    print(record.annotation["target"])
    print(record.base_uri, record.pointer, record.line)
```

Always inspect `collection.problems`. A failed scan can still contain valid
records from other files; consuming only those records without acknowledging the
errors can hide missing associations. `collection.files` lists selected carriers.

Each `Record` keeps the annotation and its origin: `path`, `pointer`, `line`, and
`base_uri`. Carry that origin into your own storage when any references are
relative. The reader does not resolve references, fetch resources, or interpret
generic locations. See [discovery](discovery.md) for traversal and carrier rules.

## Write JSON

```python
formatted = companion.dumps(annotation)
```

`dumps(value)` writes readable JSON with two-space indentation and a trailing
newline. It preserves decoded values and object/array order without sorting or
rewriting references. It is a JSON encoder, so call `check` separately when the
value must be an annotation. It raises `LoadError` for unsupported values.

Original whitespace and number spellings are not retained. Integers retain
Python's precision within interpreter limits; fractions use Python floats.
Overflow and nonzero underflow to zero are reported as range errors; ordinary
nonzero float rounding remains. True signed zero is accepted.
Use strings for application values that require exact decimal interchange or
integers beyond another consumer's supported range. There is no canonical-byte
or content-hash contract for the current annotation.

Moving formatted output to another directory changes the base of relative
references. Preserve the original base in your application's envelope, keep the
same carrier location, or deliberately rebase references before relocating it.

## Schema and diagnostics

`companion.SCHEMA_PATH` identifies the installed schema file;
`companion.load_schema()` reads it without fetching anything. The structural
schema can be used by other JSON Schema implementations. Full conformance also
requires the additional checks in the specification.

The bundled `schemacheck.Validator` implements the subset used by this package;
it is not a general-purpose JSON Schema engine. Unknown schema keywords are
rejected so a rule cannot be silently ignored. Use a complete JSON Schema
implementation if your application accepts arbitrary schemas.

The [language-neutral conformance cases](../conformance/README.md) distinguish
structural validity from full validation and can be reused by other implementations.

See [compatibility](compatibility.md) for the retained legacy modules.
