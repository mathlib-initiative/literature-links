"""Read independent annotations from local shards without imposing a layout.

Discovery is a transport utility, not a collection schema. It accepts JSON
objects, JSON arrays, and JSONL/NDJSON files, retaining the containing file as
the base of each annotation's relative references. Nothing is fetched, merged,
deduplicated by content, or inferred from a repository's layout.
"""
from __future__ import annotations

import fnmatch
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import companion

__all__ = ["Collection", "Problem", "Record", "collect"]


@dataclass
class Problem:
    """A machine-readable finding with a carrier origin and human explanation."""

    code: str
    path: str
    message: str


@dataclass
class Record:
    """An annotation and its origin; ``pointer`` is relative to its JSON value.

    A standalone JSON annotation and every JSONL row use the empty pointer.
    Array members use ``/0``, ``/1``, and so on. JSONL origins additionally
    provide their one-based physical line number.
    """

    annotation: dict[str, Any]
    path: Path
    pointer: str
    line: int | None = None

    @property
    def base_uri(self) -> str:
        """The carrier URI against which relative resource references resolve."""
        return self.path.resolve().as_uri()


@dataclass
class Collection:
    """Discovered records, all findings, and selected files in traversal order.

    Valid records are retained even when other inputs fail. Consumers must
    inspect ``problems`` before treating a collection as successfully loaded.
    Repeated annotation IDs and equal records remain unchanged.
    """

    records: list[Record] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    # Wildcards match the complete root-relative POSIX path, including '/'.
    # A leading '**/' also matches zero directories, including root files.
    for pattern in patterns:
        while True:
            if fnmatch.fnmatchcase(relative, pattern):
                return True
            if not pattern.startswith("**/"):
                break
            pattern = pattern[3:]
    return False


def _origin(path: Path, pointer: str = "", line: int | None = None) -> str:
    result = str(path) + "#" + pointer
    return result if line is None else f"{result} (line {line})"


def _read(path: Path, result: Collection) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        result.problems.append(Problem("IO", str(path), str(exc)))
        return

    def record(value: Any, pointer: str = "", line: int | None = None) -> None:
        origin = _origin(path, pointer, line)
        if not isinstance(value, dict):
            result.problems.append(Problem("SHARD_SHAPE", origin,
                                           "each annotation must be a JSON object"))
            return
        findings = companion.check(value).problems
        if findings:
            for finding in findings:
                result.problems.append(Problem(finding.code, f"{origin} {finding.path}", finding.message))
            return
        result.records.append(Record(value, path, pointer, line))

    if path.suffix.lower() in (".jsonl", ".ndjson"):
        # splitlines() would incorrectly split valid strings containing U+2028.
        for line, row in enumerate(text.split("\n"), 1):
            if not row.strip(" \t\r"):
                continue
            try:
                value = companion.loads(row)
            except companion.LoadError as exc:
                result.problems.append(Problem("JSON", _origin(path, line=line), str(exc)))
                continue
            record(value, line=line)
        return

    try:
        value = companion.loads(text)
    except companion.LoadError as exc:
        result.problems.append(Problem("JSON", str(path), str(exc)))
        return
    if isinstance(value, list):
        for index, annotation in enumerate(value):
            record(annotation, pointer=f"/{index}")
    else:
        record(value)


def collect(paths: Iterable[Path | str], *, include: Iterable[str] | None = None,
            exclude: Iterable[str] = ()) -> Collection:
    """Recursively collect local annotation shards, retaining every origin.

    Directory inputs select ``.json``, ``.jsonl`` and ``.ndjson`` files by
    default (case-insensitively). Explicit files may have any suffix and are
    interpreted as ordinary JSON unless their suffix selects JSONL. ``include``
    replaces the directory suffix filter; ``exclude`` always wins. Patterns
    are case-sensitive shell wildcards against root-relative POSIX paths;
    for explicit files the relative path is the filename. ``*`` can match
    slashes, and a leading ``**/`` also matches files directly in the root.

    Files are read in sorted absolute-path order, preserving carrier order.
    Overlapping selections of the same resolved file are read once. Directory
    symlinks and file symlinks are skipped; explicitly selected symlinks,
    missing paths, unreadable paths and nonregular inputs are reported.
    There are no hidden-directory exclusions, required manifests, identifier
    uniqueness rules, or automatic searches inside arbitrary JSON objects.
    """
    result = Collection()
    includes = None if include is None else tuple(include)
    excludes = tuple(exclude)
    selected: dict[Path, Path] = {}

    def select(path: Path, relative: str, *, explicit: bool = False) -> None:
        if _matches(relative, excludes):
            return
        if includes is not None:
            if not _matches(relative, includes):
                return
        elif not explicit and path.suffix.lower() not in (".json", ".jsonl", ".ndjson"):
            return
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            result.problems.append(Problem("PATH", str(path), str(exc)))
            return
        selected.setdefault(resolved, path)

    def walk(directory: Path, root: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            result.problems.append(Problem("IO", str(directory), str(exc)))
            return
        for child in children:
            relative = child.relative_to(root).as_posix()
            if _matches(relative, excludes):
                continue
            try:
                mode = child.lstat().st_mode
            except OSError as exc:
                result.problems.append(Problem("PATH", str(child), str(exc)))
                continue
            if stat.S_ISLNK(mode):
                continue
            if stat.S_ISDIR(mode):
                walk(child, root)
            elif stat.S_ISREG(mode):
                select(child, relative)
            elif ((includes is None and child.suffix.lower() in (".json", ".jsonl", ".ndjson"))
                  or (includes is not None and _matches(relative, includes))):
                result.problems.append(Problem("PATH", str(child),
                                               "selected input is not a regular file"))

    roots = sorted({Path(path).absolute() for path in paths}, key=str)
    for path in roots:
        try:
            if path.is_symlink():
                result.problems.append(Problem("SYMLINK", str(path),
                                               "explicit inputs must not be symlinks"))
                continue
            mode = path.lstat().st_mode
        except (OSError, ValueError) as exc:
            result.problems.append(Problem("PATH", str(path), str(exc)))
            continue
        if stat.S_ISDIR(mode):
            walk(path, path)
        elif stat.S_ISREG(mode):
            select(path, path.name, explicit=True)
        else:
            result.problems.append(Problem("PATH", str(path),
                                           "input must be a regular file or directory"))

    result.files = sorted(selected, key=str)
    for path in result.files:
        _read(path, result)
    if not result.records and not result.problems:
        result.problems.append(Problem("NO_ANNOTATIONS", "$", "no annotations were found in the selected inputs"))
    return result
