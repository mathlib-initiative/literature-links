# Contributing

Issues and pull requests are welcome. Include the smallest annotation that shows
the problem.

Run the tests with Python 3.11 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test,jsonschema]'
python -m pytest -q
python -m unittest discover -s tests   # standard library only
```

A format change updates the [specification](docs/companion.md), the
[schema](schema/companion.schema.json), the checker in
`src/formal_companion_annotations/companion.py`, the tests and the
[changelog](CHANGELOG.md) together. Tests must run offline. Public functions are
typed and listed in their module's `__all__`.
