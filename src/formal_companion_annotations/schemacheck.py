"""A small JSON Schema (draft 2020-12) evaluator for the keywords this package uses.

Extracted from the formal-companion skill (scripts/annotations/
schemacheck.py), where it was new code.  This package is standard library
only, so the ``jsonschema`` package cannot be assumed; this module evaluates the subset of
draft 2020-12 used by the bundled current and legacy schemas, and it
REFUSES a schema that uses any other keyword, so the schema cannot quietly rely
on a rule nothing here enforces.  ``tests/test_annotations_schema.py`` checks
that the real ``jsonschema`` package, when it is installed, agrees with this
evaluator on every shipped example.

Supported: ``$ref`` (local JSON Pointer fragments only), ``type``, ``enum``, ``const``,
``properties``, ``required``, ``additionalProperties``, ``patternProperties``,
``items``, ``minItems``, ``maxItems``, ``uniqueItems``, ``minLength``,
``maxLength``, ``pattern``, ``minimum``, ``maximum``, ``allOf``, ``anyOf``,
``oneOf``, ``not``, ``if``/``then``/``else``.  Annotation keywords
(``$schema``, ``$id``, ``$defs``, ``title``, ``description``) are accepted.
This is not a general-purpose JSON Schema implementation: it uses Python's
regular-expression engine, rejects nested ``$id`` resources, and never fetches
references. Schema and instance arguments are decoded JSON values.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Iterator
from urllib.parse import unquote

#: The stable public API of this module (README.md, "Public API"): exactly these
#: names.  Anything else, underscored or not, is internal and may change in any release.
__all__ = [
    "SchemaError", "Validator",
]

ANNOTATION_KEYWORDS = frozenset({"$schema", "$id", "$defs", "title", "description"})
ASSERTION_KEYWORDS = frozenset({
    "$ref", "type", "enum", "const", "properties", "required", "additionalProperties",
    "patternProperties", "items", "minItems", "maxItems", "uniqueItems", "minLength",
    "maxLength", "pattern", "minimum", "maximum", "allOf", "anyOf", "oneOf", "not",
    "if", "then", "else",
})
_SUBSCHEMA_MAPS = ("properties", "patternProperties", "$defs")
_SUBSCHEMA_LISTS = ("allOf", "anyOf", "oneOf")
_SUBSCHEMA_ONE = ("additionalProperties", "items", "not", "if", "then", "else")
_TYPES = frozenset({"object", "array", "string", "boolean", "null", "integer", "number"})
_NONNEGATIVE_INTEGER = frozenset({"minItems", "maxItems", "minLength", "maxLength"})


class SchemaError(ValueError):
    """The schema is malformed or uses something this evaluator does not implement."""


def _type_ok(value: Any, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    if isinstance(value, bool):
        return False
    if name == "integer":
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if name == "number":
        return isinstance(value, (int, float))
    raise SchemaError(f"unknown type {name!r}")


def _json_equal(a: Any, b: Any) -> bool:
    """Equality in the JSON data model: 1 == 1.0, but True is not 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_json_equal(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def _child(path: str, key: Any) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", str(key)):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key, ensure_ascii=False)}]"


class Validator:
    """Evaluate one supported schema; ``errors(instance)`` returns diagnostic pairs.

    Malformed rules and unsupported features raise :class:`SchemaError` during
    construction, including rules in branches that an instance does not reach.
    """

    def __init__(self, schema: dict[str, Any] | bool) -> None:
        self.root = schema
        self._patterns: dict[str, re.Pattern] = {}
        self._checked: set[int] = set()
        try:
            self._check_schema(schema, "#")
        except RecursionError as exc:
            raise SchemaError("schema nesting exceeds this implementation's recursion limit") from exc

    # -- schema self-check -------------------------------------------------
    def _check_schema(self, node: Any, where: str) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            raise SchemaError(f"{where}: a schema must be an object or a boolean")
        if id(node) in self._checked:
            return
        self._checked.add(id(node))
        for key, value in node.items():
            if key in ANNOTATION_KEYWORDS - {"$defs"}:
                if not isinstance(value, str):
                    raise SchemaError(f"{where}/{key}: must be a string")
                if key == "$id" and node is not self.root:
                    raise SchemaError(f"{where}/$id: nested schema resources are not supported")
                if key == "$schema" and value.removesuffix("#") != "https://json-schema.org/draft/2020-12/schema":
                    raise SchemaError(f"{where}/$schema: only draft 2020-12 is supported")
                continue
            if key not in ASSERTION_KEYWORDS and key not in _SUBSCHEMA_MAPS:
                raise SchemaError(f"{where}: keyword {key!r} is not implemented by schemacheck")
            if key in _SUBSCHEMA_MAPS:
                if not isinstance(value, dict) or any(not isinstance(name, str) for name in value):
                    raise SchemaError(f"{where}/{key}: must be an object with string keys")
                for name, sub in value.items():
                    if key == "patternProperties":
                        self._regex(name)
                    self._check_schema(sub, f"{where}/{key}/{name}")
            elif key in _SUBSCHEMA_LISTS:
                if not isinstance(value, list) or not value:
                    raise SchemaError(f"{where}/{key}: must be a nonempty array of schemas")
                for i, sub in enumerate(value):
                    self._check_schema(sub, f"{where}/{key}/{i}")
            elif key in _SUBSCHEMA_ONE:
                self._check_schema(value, f"{where}/{key}")
            elif key == "$ref":
                self._check_schema(self._resolve(value), f"{where}/$ref ({value})")
            elif key == "pattern":
                self._regex(value)
            elif key == "type":
                names = value if isinstance(value, list) else [value]
                if (not names or any(not isinstance(name, str) or name not in _TYPES for name in names)
                        or len(names) != len(set(names))):
                    raise SchemaError(f"{where}/type: must name a supported type or a nonempty unique array of types")
            elif key == "required":
                if (not isinstance(value, list) or any(not isinstance(name, str) for name in value)
                        or len(value) != len(set(value))):
                    raise SchemaError(f"{where}/required: must be an array of unique strings")
            elif key == "enum" and not isinstance(value, list):
                raise SchemaError(f"{where}/enum: must be an array")
            elif key in _NONNEGATIVE_INTEGER:
                if not _type_ok(value, "integer") or value < 0:
                    raise SchemaError(f"{where}/{key}: must be a nonnegative integer")
            elif key in ("minimum", "maximum"):
                if (not _type_ok(value, "number")
                        or isinstance(value, float) and not math.isfinite(value)):
                    raise SchemaError(f"{where}/{key}: must be a finite number")
            elif key == "uniqueItems" and not isinstance(value, bool):
                raise SchemaError(f"{where}/uniqueItems: must be a boolean")

    def _regex(self, pattern: str) -> re.Pattern:
        if not isinstance(pattern, str):
            raise SchemaError("a regular expression must be a string")
        compiled = self._patterns.get(pattern)
        if compiled is None:
            try:
                compiled = self._patterns[pattern] = re.compile(pattern)
            except (re.error, OverflowError) as exc:
                raise SchemaError(f"unsupported or malformed regular expression {pattern!r}: {exc}") from exc
        return compiled

    def _resolve(self, ref: str) -> Any:
        if not isinstance(ref, str) or not ref.startswith("#"):
            raise SchemaError(f"only local $ref is supported, got {ref!r}")
        if re.search(r"%(?![0-9A-Fa-f]{2})", ref):
            raise SchemaError(f"$ref {ref!r} contains malformed percent encoding")
        try:
            pointer = unquote(ref[1:], encoding="utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise SchemaError(f"$ref {ref!r} contains invalid UTF-8") from exc
        if pointer == "":
            return self.root
        if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
            raise SchemaError(f"$ref {ref!r} is not a supported JSON Pointer fragment")
        node: Any = self.root
        for part in pointer[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and re.fullmatch(r"0|[1-9][0-9]*", part):
                # Avoid converting an attacker-sized integer token before checking
                # its range; list indices have a bounded, ordinary decimal length.
                if len(part) > len(str(len(node))) or int(part) >= len(node):
                    raise SchemaError(f"$ref {ref!r} resolves nowhere")
                node = node[int(part)]
            else:
                raise SchemaError(f"$ref {ref!r} resolves nowhere")
        return node

    # -- evaluation --------------------------------------------------------
    def is_valid(self, instance: Any, schema: Any = None) -> bool:
        try:
            return next(self._eval(instance, self.root if schema is None else schema, "$"), None) is None
        except RecursionError as exc:
            raise SchemaError("schema evaluation exceeds this implementation's recursion limit") from exc

    def errors(self, instance: Any) -> list[tuple[str, str]]:
        try:
            return list(self._eval(instance, self.root, "$"))
        except RecursionError as exc:
            raise SchemaError("schema evaluation exceeds this implementation's recursion limit") from exc

    def _eval(self, inst: Any, schema: Any, path: str) -> Iterator[tuple[str, str]]:
        if schema is True:
            return
        if schema is False:
            yield path, "no value is allowed here"
            return
        if "$ref" in schema:
            yield from self._eval(inst, self._resolve(schema["$ref"]), path)
        if "type" in schema:
            names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_type_ok(inst, n) for n in names):
                yield path, f"must be of type {' or '.join(names)}"
                return
        if "const" in schema and not _json_equal(inst, schema["const"]):
            yield path, f"must be {json.dumps(schema['const'], ensure_ascii=False)}"
        if "enum" in schema and not any(_json_equal(inst, e) for e in schema["enum"]):
            allowed = ", ".join(json.dumps(e, ensure_ascii=False) for e in schema["enum"])
            yield path, f"{json.dumps(inst, ensure_ascii=False)} is not one of {allowed}"
        if isinstance(inst, str):
            if "minLength" in schema and len(inst) < schema["minLength"]:
                yield path, f"must be at least {schema['minLength']} character(s) long"
            if "maxLength" in schema and len(inst) > schema["maxLength"]:
                yield path, f"must be at most {schema['maxLength']} characters long"
            if "pattern" in schema and not self._regex(schema["pattern"]).search(inst):
                yield path, f"{json.dumps(inst, ensure_ascii=False)} does not match {schema['pattern']}"
        if _type_ok(inst, "number") and not isinstance(inst, bool):
            if "minimum" in schema and inst < schema["minimum"]:
                yield path, f"must be >= {schema['minimum']}"
            if "maximum" in schema and inst > schema["maximum"]:
                yield path, f"must be <= {schema['maximum']}"
        if isinstance(inst, list):
            if "minItems" in schema and len(inst) < schema["minItems"]:
                yield path, f"must have at least {schema['minItems']} item(s)"
            if "maxItems" in schema and len(inst) > schema["maxItems"]:
                yield path, f"must have at most {schema['maxItems']} item(s)"
            if schema.get("uniqueItems"):
                for i in range(len(inst)):
                    if any(_json_equal(inst[i], inst[j]) for j in range(i)):
                        yield _child(path, i), "duplicates an earlier entry"
            if "items" in schema:
                for i, value in enumerate(inst):
                    yield from self._eval(value, schema["items"], _child(path, i))
        if isinstance(inst, dict):
            for key in schema.get("required", ()):
                if key not in inst:
                    yield path, f"is missing required key {key!r}"
            props = schema.get("properties", {})
            pats = schema.get("patternProperties", {})
            for key, value in inst.items():
                matched = False
                if key in props:
                    matched = True
                    yield from self._eval(value, props[key], _child(path, key))
                for pat, sub in pats.items():
                    if self._regex(pat).search(key):
                        matched = True
                        yield from self._eval(value, sub, _child(path, key))
                if not matched and "additionalProperties" in schema:
                    extra = schema["additionalProperties"]
                    if extra is False:
                        yield _child(path, key), "is not an allowed key here"
                    else:
                        yield from self._eval(value, extra, _child(path, key))
        for sub in schema.get("allOf", ()):
            yield from self._eval(inst, sub, path)
        if "anyOf" in schema and not any(self.is_valid(inst, s) for s in schema["anyOf"]):
            yield path, "matches none of the allowed alternatives (anyOf)"
        if "oneOf" in schema:
            hits = sum(self.is_valid(inst, s) for s in schema["oneOf"])
            if hits != 1:
                yield path, f"must match exactly one alternative (oneOf), matched {hits}"
        if "not" in schema and self.is_valid(inst, schema["not"]):
            yield path, "matches a shape that is not allowed here (not)"
        if "if" in schema:
            if self.is_valid(inst, schema["if"]):
                if "then" in schema:
                    yield from self._eval(inst, schema["then"], path)
            elif "else" in schema:
                yield from self._eval(inst, schema["else"], path)
