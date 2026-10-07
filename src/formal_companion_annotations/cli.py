"""Offline commands for the unversioned companion draft and explicit v1 migration."""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict
import errno
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import quote, urljoin

from . import __version__, companion, discovery, migration, validate as legacy

__all__ = ["main"]


def _absolute(reference: str) -> bool:
    return re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", reference) is not None


def _write_text(path: Path, text: str) -> None:
    """Replace one explicitly requested output only after writing it completely."""
    descriptor, name = tempfile.mkstemp(prefix=".companion-", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def _publish_directory(source: Path, destination: Path) -> None:
    """Atomically publish a new directory without replacing a racing writer."""
    if sys.platform == "win32":
        # Windows rename refuses an existing destination, including directories.
        os.rename(source, destination)
        return
    if not (sys.platform.startswith("linux") or sys.platform == "darwin"):
        raise OSError(errno.ENOTSUP, "atomic no-replace directory publication is unavailable on this platform")
    library = ctypes.CDLL(None, use_errno=True)
    try:
        if sys.platform.startswith("linux"):
            rename = library.renameat2
            rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                               ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)  # AT_FDCWD, RENAME_NOREPLACE
        elif sys.platform == "darwin":
            rename = library.renamex_np
            rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
            rename.restype = ctypes.c_int
            result = rename(os.fsencode(source), os.fsencode(destination), 0x00000004)  # RENAME_EXCL
    except AttributeError as exc:
        raise OSError(errno.ENOTSUP, "atomic no-replace directory publication is unavailable on this platform") from exc
    if result:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def _validate(args: argparse.Namespace) -> int:
    """Report every input, including after unreadable files; status 2 wins."""
    status = 0
    for path in args.documents:
        item_status = 0
        warnings: list[dict[str, str]] = []
        problems: list[dict[str, str]] = []
        description = "annotation"
        try:
            text = path.read_bytes().decode("utf-8")
            document = companion.loads(text)
            if not (isinstance(document, dict)
                    and any(key in document for key in ("schema", "schema_version"))):
                report = companion.check(document)
                problems = [asdict(problem) for problem in report.problems]
                warnings = [asdict(warning) for warning in report.warnings]
                if args.canonical:
                    problems.append({"code": "UNSUPPORTED_OPERATION", "path": "$",
                                     "message": "canonical validation is v1-only; use format for single annotations"})
                if not problems:
                    description = f"1 annotation, {document['source']['type']}"
            elif isinstance(document, dict) and document.get("schema") == "formal-companion/annotations":
                problems = [{"code": "UNSUPPORTED_FORMAT", "path": "$.schema",
                             "message": "PR #2 rc3 is a distinct companion format; use its checker. "
                                        "It is not legacy v1 or the single-annotation draft."}]
            else:
                legacy_report = legacy.check(document, text=text, canonical=args.canonical)
                problems = [{"code": "LEGACY_V1", "path": "$", "message": message}
                            for message in legacy_report.problems]
                warnings = [{"code": "LEGACY_V1", "path": "$", "message": message}
                            for message in legacy_report.warnings]
                description = "legacy v1"
            item_status = 1 if problems else 0
        except (OSError, UnicodeError, ValueError, RecursionError) as exc:
            item_status = 2
            code = "IO" if isinstance(exc, OSError) else "JSON"
            problems = [{"code": code, "path": "$", "message": str(exc)}]
        status = max(status, item_status)
        if args.format == "json":
            print(json.dumps({"document": str(path), "valid": not problems, "status": item_status,
                              "problems": problems, "warnings": warnings}, ensure_ascii=True, allow_nan=False))
        else:
            for warning in warnings:
                print(f"{path}: warning: {warning['path']}: {warning['message']} [{warning['code']}]")
            for problem in problems:
                print(f"{path}: {problem['path']}: {problem['message']} [{problem['code']}]",
                      file=sys.stderr if item_status == 2 else sys.stdout)
            if not problems:
                print(f"{path}: ok ({description})")
    return status


def _scan(args: argparse.Namespace) -> int:
    collection = discovery.collect(args.paths, include=args.include, exclude=args.exclude)
    # File, parsing, and selection failures are operational errors. An annotation
    # with the wrong schema is invalid data, even when found inside a shard.
    operational = {"IO", "JSON", "NO_ANNOTATIONS", "SYMLINK", "PATH"}
    status = (2 if any(problem.code in operational for problem in collection.problems)
              else 1 if collection.problems else 0)
    if args.format == "json":
        result = {"valid": not collection.problems, "status": status,
                  "files": [str(path) for path in collection.files],
                  "records": [{"annotation": record.annotation,
                               "origin": {"path": str(record.path), "pointer": record.pointer,
                                          "line": record.line, "base_uri": record.base_uri}}
                              for record in collection.records],
                  "problems": [asdict(problem) for problem in collection.problems]}
        print(companion.dumps(result), end="")
    else:
        for problem in collection.problems:
            print(f"{problem.path}: {problem.message} [{problem.code}]")
        print(f"{len(collection.records)} annotations from {len(collection.files)} shards; "
              f"{len(collection.problems)} problems")
    return status


def _migrate(args: argparse.Namespace) -> int:
    # Read the original bytes separately: the archive is identical to the input,
    # while the strict codec rejects values that cannot survive JSON interchange.
    original_bytes = args.document.read_bytes()
    document = companion.loads(original_bytes.decode("utf-8"))
    mappings: dict[str, str] = {}
    for assignment in args.source_uri:
        identity, separator, uri = assignment.partition("=")
        if not separator or not identity or not uri or identity in mappings:
            raise ValueError("--source-uri requires a distinct SOURCE_ID=URI for each source")
        mappings[identity] = uri
    if args.source_base is not None:
        if (not args.source_base or any(char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159
                                        for char in args.source_base)
                or not _absolute(args.source_base)):
            raise ValueError("--source-base must be an absolute URI without whitespace/controls, "
                             "such as file:///path/to/project/")
    # The v1 source path is commonly repository-relative. The CLI must not
    # assume that the directory containing annotations.json was that repository.
    # Obtain the original mode/records only after the adapter validates v1.
    result = migration.migrate_v1(document, source_uris=mappings, target_base=args.target_base)
    if args.source_base is not None:
        for source in document["sources"]:
            uri = mappings.get(source["id"])
            if uri is None:
                uri = quote(source["path"], safe="/") if "path" in source else source.get("url")
            if isinstance(uri, str) and not _absolute(uri):
                try:
                    resolved = urljoin(args.source_base, uri)
                except ValueError as exc:
                    raise ValueError("--source-base cannot resolve source reference " + repr(uri)) from exc
                if not _absolute(resolved):
                    raise ValueError("--source-base cannot resolve source reference " + repr(uri))
                mappings[source["id"]] = resolved
        result = migration.migrate_v1(document, source_uris=mappings, target_base=args.target_base)
    for converted in result.documents:
        uri = converted["source"]["uri"]
        if not _absolute(uri):
            raise ValueError("migration would relocate a relative source reference; supply --source-base "
                             "or an absolute --source-uri for " + repr(uri))
        problems = companion.validate(converted)
        if problems:
            raise ValueError("migration produced an invalid companion: " + "; ".join(problems))

    destination = args.output
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"migration output already exists: {destination}")
    staged = Path(tempfile.mkdtemp(prefix=".companion-migration-", dir=destination.parent))
    try:
        manifest = {"format": "companion-v1-migration-report", "version": 1,
                    "original": "original-v1.json", "documents": [], "diagnostics": result.diagnostics,
                    "options": {"source_base": args.source_base, "source_uris": mappings,
                                "target_base": args.target_base}}
        (staged / "original-v1.json").write_bytes(original_bytes)
        for index, converted in enumerate(result.documents, start=1):
            name = f"annotation-{index:03d}.json"
            (staged / name).write_text(companion.dumps(converted), encoding="utf-8")
            manifest["documents"].append(name)
        (staged / "report.json").write_text(companion.dumps(manifest), encoding="utf-8")
        # All conversion and serialization has succeeded before exposing output.
        _publish_directory(staged, destination)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    warning_count = sum(item["severity"] == "warning" for item in result.diagnostics)
    print(f"{destination}: {len(result.documents)} annotations, {warning_count} warnings; "
          "review report.json; original preserved in original-v1.json")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run an offline command; return 0 on success, 1 on invalid data, 2 on error."""
    parser = argparse.ArgumentParser(prog="formal-companion-annotations",
                                     description="Single formal/informal annotations and companion discovery (unversioned draft).",
                                     epilog="Legacy bare-file commands remain available through python -m formal_companion_annotations.validate.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validation = subparsers.add_parser("validate", help="validate single annotations or legacy v1 JSON")
    validation.add_argument("documents", nargs="+", type=Path)
    validation.add_argument("--canonical", action="store_true", help="legacy v1 only")
    validation.add_argument("--format", choices=("text", "json"), default="text", help="JSON emits one report per input")
    scanning = subparsers.add_parser("scan", help="recursively discover annotations in JSON/JSONL shards")
    scanning.add_argument("paths", nargs="+", type=Path)
    scanning.add_argument("--include", action="append", help="select root-relative file patterns (repeatable)")
    scanning.add_argument("--exclude", action="append", default=[], help="exclude root-relative file patterns (repeatable)")
    scanning.add_argument("--format", choices=("text", "json"), default="text")
    formatting = subparsers.add_parser("format", help="pretty-print a single annotation while retaining data and ordering")
    formatting.add_argument("document", type=Path)
    formatting.add_argument("--output", type=Path,
                            help="write to a file; relative references stay unchanged, so preserve their base")
    conversion = subparsers.add_parser("migrate-v1", help="project legacy links and archive their original graph")
    conversion.add_argument("document", type=Path)
    conversion.add_argument("--output", type=Path, required=True, help="new output directory (must not exist)")
    conversion.add_argument("--source-uri", action="append", default=[], metavar="SOURCE_ID=URI")
    conversion.add_argument("--source-base", help="absolute base URI for relative source paths; directory bases end in /")
    conversion.add_argument("--target-base", help="absolute base URI for relative formal destinations")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "scan":
            return _scan(args)
        if args.command == "migrate-v1":
            return _migrate(args)
        document = companion.loads(args.document.read_text(encoding="utf-8"))
        problems = companion.validate(document)
        if problems:
            for problem in problems:
                print(f"{args.document}: {problem}", file=sys.stderr)
            return 1
        formatted = companion.dumps(document)
        if args.output is None:
            sys.stdout.write(formatted)
        else:
            _write_text(args.output, formatted)
        return 0
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        if args.command == "scan" and args.format == "json":
            print(companion.dumps({"valid": False, "status": 2, "files": [], "records": [],
                                   "problems": [{"code": "IO", "path": "$", "message": str(exc)}]}), end="")
            return 2
        print(f"{parser.prog}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
