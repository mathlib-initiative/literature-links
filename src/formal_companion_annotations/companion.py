"""Small, offline validator and JSON codec for one unversioned companion annotation.

Validation checks the document's shape and local invariants. It does not fetch
resources, resolve anchors, execute selectors, or verify a mathematical claim.
Generic locations and extension values are opaque JSON and retain their order.
"""
from __future__ import annotations

import functools
import json
import math
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from .schemacheck import Validator

__all__ = ["SCHEMA_PATH", "LoadError", "Problem", "Report", "check", "dumps", "load_schema", "loads", "validate"]

_HERE = Path(__file__).resolve().parent
_PACKAGE_SCHEMA = _HERE / "schema" / "companion.schema.json"
_SOURCE_CHECKOUT = _HERE.parent.name == "src" and (_HERE.parent.parent / "pyproject.toml").is_file()
SCHEMA_PATH = (_HERE.parent.parent / "schema" / "companion.schema.json"
               if not _PACKAGE_SCHEMA.is_file() and _SOURCE_CHECKOUT else _PACKAGE_SCHEMA)


class LoadError(ValueError):
    """The input is not an unambiguous, finite JSON value."""


@dataclass(frozen=True)
class Problem:
    """A stable diagnostic code, where it was found, and a readable explanation."""

    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class Report:
    """Validation findings; any problem makes the companion invalid."""

    problems: list[Problem] = field(default_factory=list)
    warnings: list[Problem] = field(default_factory=list)


def _child(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    return f"{path}[{json.dumps(key)}]"


def _json_problems(value: Any) -> list[Problem]:
    """Reject values JSON cannot represent, even inside opaque payloads."""
    problems: list[Problem] = []
    active: set[int] = set()

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            if any(0xD800 <= ord(char) <= 0xDFFF for char in node):
                problems.append(Problem("JSON", path, "strings must not contain unpaired Unicode surrogates"))
            return
        if node is None or isinstance(node, (bool, int)):
            return
        if isinstance(node, float):
            if not math.isfinite(node):
                problems.append(Problem("JSON", path, "numbers must be finite"))
            return
        if not isinstance(node, (dict, list)):
            problems.append(Problem("JSON", path, f"{type(node).__name__} is not a JSON value"))
            return
        identity = id(node)
        if identity in active:
            problems.append(Problem("JSON", path, "cyclic containers are not JSON"))
            return
        active.add(identity)
        if isinstance(node, dict):
            for key, item in node.items():
                if not isinstance(key, str):
                    problems.append(Problem("JSON", path, "object keys must be strings"))
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
        problems.append(Problem("JSON", "$", "JSON nesting exceeds this implementation's recursion limit"))
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


def _float(text: str) -> float:
    value = float(text)
    # Ordinary fractional rounding is part of this codec's float precision, but
    # losing every nonzero digit is an implementation range failure. Inspect the
    # mantissa directly so even extreme exponents need no bounded integer parse.
    if value == 0.0 and any(char in "123456789" for char in text.lower().partition("e")[0]):
        raise LoadError("nonzero JSON number is below this implementation's floating-point range")
    return value


def loads(text: str) -> Any:
    """Read JSON with duplicate-key, Unicode, and numeric-range checks.

    This is a JSON codec, not schema validation; call :func:`check` or
    :func:`validate` on the returned value to validate a companion document.
    Integers remain integers; fractional/exponent forms use Python float
    precision. Overflow and nonzero numbers that underflow to zero are errors.
    """
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
    except (ValueError, RecursionError) as exc:
        if isinstance(exc, LoadError):
            raise
        raise LoadError(f"not JSON: {exc}") from exc
    problems = _json_problems(value)
    if problems:
        raise LoadError("; ".join(map(str, problems)))
    return value


def dumps(value: Any) -> str:
    """Write readable JSON, preserving values and all object/array ordering.

    No key sorting, identifier rewriting, or float conversion of
    integers is performed. Invalid JSON values raise :class:`LoadError`.
    The result uses two-space indentation and ends with a newline.
    """
    problems = _json_problems(value)
    if problems:
        raise LoadError("; ".join(map(str, problems)))
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    except (ValueError, RecursionError) as exc:
        raise LoadError(f"cannot write JSON: {exc}") from exc


def load_schema() -> dict[str, Any]:
    """Read the bundled schema, without accessing any network resource."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@functools.cache
def _validator(path: Path) -> Validator:
    # Keyed by path so a swapped SCHEMA_PATH is still read.
    return Validator(load_schema())


def check(document: Any) -> Report:
    """Check one annotation's structure and local invariants without mutation.

    Diagnostic codes are ``JSON`` for values outside the JSON data model,
    ``SCHEMA`` for structural failures, ``PDF_RECT`` for rectangle semantics,
    and ``LATEX_LINES`` for reversed inclusive line ranges. Warnings are
    currently empty. No collection-wide identity or resource checks occur.
    """
    report = Report(problems=_json_problems(document))
    if report.problems:
        return report
    validator = _validator(SCHEMA_PATH)
    try:
        report.problems.extend(Problem("SCHEMA", path, message)
                               for path, message in validator.errors(document))
    except (ValueError, RecursionError) as exc:
        report.problems.append(Problem("SCHEMA", "$", f"cannot validate JSON: {exc}"))
    if report.problems:
        return report

    mode = document["source"]["type"]
    location = document.get("location")
    if location is None:
        return report
    if mode == "pdf" and "rect" in location:
        x, y, width, height = location["rect"]
        if width <= 0 or height <= 0:
            report.problems.append(Problem("PDF_RECT", "$.location.rect",
                                           "width and height must be positive"))
        # Exact decimal arithmetic avoids accepting .9 + .10000000000000002
        # because a binary floating-point sum happens to round to 1.
        outside = (Fraction(str(x)) + Fraction(str(width)) > 1
                   or Fraction(str(y)) + Fraction(str(height)) > 1)
        if outside:
            report.problems.append(Problem("PDF_RECT", "$.location.rect",
                                           "rectangle must stay within the page"))
    elif mode == "latex" and "lines" in location:
        start, end = location["lines"]
        if end < start:
            report.problems.append(Problem("LATEX_LINES", "$.location.lines",
                                           "end must be greater than or equal to start"))
    return report


def validate(document: Any) -> list[str]:
    """Return readable validation problems, or an empty list for one valid link."""
    return [str(problem) for problem in check(document).problems]
