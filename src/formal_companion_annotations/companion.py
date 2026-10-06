"""Small, offline validator and JSON codec for the companion v2 working draft.

Validation checks the document's shape and local invariants. It does not fetch
resources, resolve anchors, execute selectors, or verify a mathematical claim.
Generic locations and extension values are opaque JSON and retain their order.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from .schemacheck import Validator

__all__ = ["SCHEMA_PATH", "LoadError", "Report", "check", "dumps", "load_schema", "loads", "validate"]

SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "companion-v2.schema.json"


class LoadError(ValueError):
    """The input is not an unambiguous, finite JSON value."""


@dataclass
class Report:
    """Validation findings; any problem makes the companion invalid."""

    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _child(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}[{json.dumps(key)}]"


def _json_problems(value: Any) -> list[str]:
    """Reject values JSON cannot represent, even inside opaque payloads."""
    problems: list[str] = []
    active: set[int] = set()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in node):
                problems.append(f"{path}: strings must not contain unpaired Unicode surrogates")
            return
        if node is None or isinstance(node, (bool, int)):
            return
        if isinstance(node, float):
            if not math.isfinite(node):
                problems.append(f"{path}: numbers must be finite")
            return
        if not isinstance(node, (dict, list)):
            problems.append(f"{path}: {type(node).__name__} is not a JSON value")
            return
        identity = id(node)
        if identity in active:
            problems.append(f"{path}: cyclic containers are not JSON")
            return
        active.add(identity)
        if isinstance(node, dict):
            for key, item in node.items():
                if not isinstance(key, str):
                    problems.append(f"{path}: object keys must be strings")
                    continue
                walk(key, path + " (object key)")
                walk(item, _child(path, key))
        else:
            for index, item in enumerate(node):
                walk(item, _child(path, index))
        active.remove(identity)

    try:
        walk(value, "$")
    except RecursionError:
        problems.append("$: JSON nesting exceeds this implementation's recursion limit")
    return problems


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LoadError(f"duplicate key {key!r} in one object")
        result[key] = value
    return result


def _constant(name: str) -> Any:
    raise LoadError(f"{name} is not JSON")


def loads(text: str) -> Any:
    """Read JSON without duplicate keys, nonfinite numbers, or silent coercion.

    This is a JSON codec, not schema validation; call :func:`check` or
    :func:`validate` on the returned value to validate a companion document.
    """
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant)
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, LoadError):
            raise
        raise LoadError(f"not JSON: {exc}") from exc
    problems = _json_problems(value)
    if problems:
        raise LoadError("; ".join(problems))
    return value


def dumps(value: Any) -> str:
    """Write readable JSON, preserving values and all object/array ordering.

    No annotation sorting, identifier rewriting, or float conversion of
    integers is performed. Invalid JSON values raise :class:`LoadError`.
    The result uses two-space indentation and ends with a newline.
    """
    problems = _json_problems(value)
    if problems:
        raise LoadError("; ".join(problems))
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    except (ValueError, RecursionError) as exc:
        raise LoadError(f"cannot write JSON: {exc}") from exc


def load_schema() -> dict[str, Any]:
    """Read the bundled schema, without accessing any network resource."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def check(document: Any) -> Report:
    """Check v2 structure and local invariants without changing the input."""
    report = Report(problems=_json_problems(document))
    if report.problems:
        return report
    validator = Validator(load_schema())
    try:
        report.problems.extend(f"{path}: {message}" for path, message in validator.errors(document))
    except (ValueError, RecursionError) as exc:
        report.problems.append(f"$: cannot validate JSON: {exc}")
    if report.problems:
        return report

    seen_ids: set[str] = set()
    mode = document["source"]["type"]
    for index, annotation in enumerate(document["annotations"]):
        path = f"$.annotations[{index}]"
        if "id" in annotation:
            identity = annotation["id"]
            if identity in seen_ids:
                report.problems.append(f"{path}.id: duplicates an earlier annotation id {identity!r}")
            seen_ids.add(identity)
        location = annotation.get("location")
        if location is None:
            continue
        if mode == "pdf" and "rect" in location:
            x, y, width, height = location["rect"]
            if width <= 0 or height <= 0:
                report.problems.append(f"{path}.location.rect: width and height must be positive")
            # Exact decimal arithmetic avoids accepting .9 + .10000000000000002
            # because a binary floating-point sum happens to round to 1.
            outside = (Fraction(str(x)) + Fraction(str(width)) > 1
                       or Fraction(str(y)) + Fraction(str(height)) > 1)
            if outside:
                report.problems.append(f"{path}.location.rect: rectangle must stay within the page")
        elif mode == "latex" and "lines" in location:
            start, end = location["lines"]
            if end < start:
                report.problems.append(f"{path}.location.lines: end must be greater than or equal to start")
    return report


def validate(document: Any) -> list[str]:
    """Return validation problems, or an empty list for a valid companion."""
    return check(document).problems
