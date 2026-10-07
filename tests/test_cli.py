"""End-to-end command behavior, migration relocation, and file preservation."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(ROOT / "src"))

import formal_companion_annotations
from formal_companion_annotations import cli, companion, validate


def current_annotation() -> dict:
    return {"source": {"type": "generic", "uri": "../source.json"},
            "id": "z", "target": "urn:formal:first",
            "location": {"custom": {"z": 2**100, "a": [3, 2, 1]}},
            "extensions": {"tool": {"z": "α", "a": None}, "owner.example": {"unrecognized": True}}}


def v1(name: str = "web-passage") -> dict:
    doc = json.loads((ROOT / "examples" / "annotations" / f"{name}.json").read_text(encoding="utf-8"))
    if name == "tex-lines":
        doc["destinations"] = [{"id": "sum-comm", "declaration": "Blueprint.sum_comm", "site": "doc_gen4",
                                "href": "https://formal.example.org/Blueprint.html", "fragment": "Blueprint.sum_comm",
                                "resolution": "exact"}]
    return doc


class CommandCase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="companion-cli-")
        self.addCleanup(self.workspace.cleanup)
        self.directory = Path(self.workspace.name)

    def write(self, name: str, document: dict) -> Path:
        path = self.directory / name
        path.write_text(companion.dumps(document), encoding="utf-8", newline="\n")
        return path

    def run_command(self, *arguments: str, entry=cli.main) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = entry(list(arguments))
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def run_module(self, module: str, *arguments: str, parser_failure: bool = False) -> subprocess.CompletedProcess:
        package_root = str(Path(formal_companion_annotations.__file__).resolve().parent.parent)
        environment = dict(os.environ, PYTHONPATH=package_root, PYTHONDONTWRITEBYTECODE="1")
        if parser_failure:
            script = """import json, runpy, sys
from unittest.mock import patch
sys.argv = sys.argv[1:]
with patch.object(json, 'loads', side_effect=RecursionError('simulated JSON parser limit')):
    runpy.run_module(sys.argv[0], run_name='__main__')
"""
            command = [sys.executable, "-c", script, module, *arguments]
        else:
            command = [sys.executable, "-m", module, *arguments]
        return subprocess.run(command, cwd=self.directory,
                              env=environment, capture_output=True, text=True, check=False)


class TestValidationCommands(CommandCase):
    def test_both_formats_work_through_new_and_legacy_entry_points(self):
        small, legacy = self.write("small.json", current_annotation()), self.write("legacy.json", v1())
        status, out, err = self.run_command("validate", str(small), str(legacy))
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(out.count(": ok ("), 2)
        for path in (small, legacy):
            status, out, err = self.run_command(str(path), entry=validate.main)
            self.assertEqual((status, err), (0, ""))
            self.assertIn(": ok (", out)

    def test_invalid_documents_exit_one_with_paths(self):
        doc = current_annotation()
        doc["target"] = "with spaces"
        path = self.write("invalid.json", doc)
        status, out, err = self.run_command("validate", str(path))
        self.assertEqual(status, 1)
        self.assertIn(str(path), out)
        self.assertIn("target", out)
        self.assertNotIn("Traceback", out + err)

    def test_version_is_rejected_by_both_validation_entry_points(self):
        for key, value in (("version", 2), ("schema_version", "1.0")):
            doc = current_annotation()
            doc[key] = value
            path = self.write("versioned.json", doc)
            for entry, arguments in ((cli.main, ("validate", str(path))),
                                     (validate.main, (str(path),))):
                with self.subTest(key=key, entry=entry.__module__):
                    status, out, err = self.run_command(*arguments, entry=entry)
                    self.assertEqual(status, 1)
                    self.assertNotIn("Traceback", out + err)

    def test_new_validate_reports_mixed_valid_and_invalid_files(self):
        first, second = self.write("valid.json", current_annotation()), self.write("invalid.json", {"version": 3})
        status, out, err = self.run_command("validate", str(first), str(second))
        self.assertEqual(status, 1)
        self.assertIn(f"{first}: ok", out)
        self.assertIn(str(second), out)
        self.assertEqual(err, "")

    def test_single_annotations_reject_legacy_canonical_apis_and_flags(self):
        doc = current_annotation()
        with self.assertRaisesRegex(ValueError, "v1-only"):
            validate.canonicalize(doc)
        with self.assertRaisesRegex(ValueError, "v1-only"):
            validate.canonical_dumps(doc)
        self.assertTrue(validate.check(doc, canonical=True).problems)
        self.assertTrue(validate.check(doc, schema={}).problems)
        path = self.write("small.json", doc)
        status, out, err = self.run_command("validate", str(path), "--canonical")
        self.assertEqual(status, 1)
        self.assertIn("canonical", out + err)
        status, out, err = self.run_command(str(path), "--print-canonical", entry=validate.main)
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertIn("legacy v1", err)

    def test_legacy_canonical_command_still_works(self):
        path = self.directory / "legacy.json"
        doc = validate.canonicalize(v1())
        path.write_bytes(validate.canonical_dumps(doc).encode("utf-8"))
        status, out, err = self.run_command("validate", str(path), "--canonical")
        self.assertEqual((status, err), (0, ""))
        self.assertIn(": ok", out)

    def test_invalid_json_and_missing_files_exit_two_without_tracebacks(self):
        for index, content in enumerate((b"{", b'{"version":2,"version":2}', b"\xff", b"1e999")):
            path = self.directory / f"malformed-{index}.json"
            path.write_bytes(content)
            for command in (("validate", str(path)), ("format", str(path))):
                status, out, err = self.run_command(*command)
                with self.subTest(command=command, content=content):
                    # The legacy parser reads 1e999 as inf; schema validation
                    # still rejects it. The single-annotation codec rejects it on loading.
                    self.assertIn(status, (1, 2))
                    self.assertNotIn("Traceback", out + err)
        status, out, err = self.run_command("validate", str(self.directory / "missing.json"))
        self.assertEqual(status, 2)
        self.assertNotIn("Traceback", out + err)

    def test_deep_input_fails_cleanly_in_supported_module_entry_points(self):
        path = self.directory / "too-deep.json"
        # Parser nesting limits vary between Python releases. A parser may
        # reject this input, or accept it and let validation reject its shape.
        path.write_text("[" * 100_000 + "0" + "]" * 100_000, encoding="utf-8")
        for module, arguments in (("formal_companion_annotations.cli", ["validate", str(path)]),
                                  ("formal_companion_annotations.validate", [str(path)]),
                                  ("formal_companion_annotations", [str(path)])):
            result = self.run_module(module, *arguments)
            with self.subTest(module=module):
                self.assertIn(result.returncode, (1, 2), result.stdout + result.stderr)
                self.assertIn(str(path), result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_parser_failures_exit_two_in_supported_module_entry_points(self):
        path = self.write("annotation.json", current_annotation())
        for module, arguments in (("formal_companion_annotations.cli", ["validate", str(path)]),
                                  ("formal_companion_annotations.validate", [str(path)]),
                                  ("formal_companion_annotations", [str(path)])):
            result = self.run_module(module, *arguments, parser_failure=True)
            with self.subTest(module=module):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("simulated JSON parser limit", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_lone_surrogate_is_reported_without_writing_invalid_utf8(self):
        path = self.directory / "surrogate.json"
        doc = current_annotation()
        doc["extensions"] = {"tool": "\ud800"}
        path.write_text(json.dumps(doc, ensure_ascii=True), encoding="utf-8")
        for command in (("validate", str(path)), ("format", str(path))):
            status, out, err = self.run_command(*command)
            self.assertIn(status, (1, 2))
            self.assertIn("surrogate", out + err)
            self.assertNotIn("Traceback", out + err)


class TestFormattingCommands(CommandCase):
    def test_stdout_format_preserves_large_integer_order_and_unknown_payloads(self):
        doc = current_annotation()
        path = self.write("small.json", doc)
        before = path.read_bytes()
        status, out, err = self.run_command("format", str(path))
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(companion.loads(out), doc)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(companion.loads(out)["extensions"]["tool"]), ["z", "a"])
        self.assertEqual(companion.loads(out)["location"]["custom"]["a"], [3, 2, 1])

    def test_explicit_output_writes_valid_json_without_changing_input(self):
        path = self.write("small.json", current_annotation())
        before = path.read_bytes()
        output = self.directory / "formatted.json"
        status, out, err = self.run_command("format", str(path), "--output", str(output))
        self.assertEqual((status, out, err), (0, "", ""))
        self.assertEqual(companion.loads(output.read_text(encoding="utf-8")), current_annotation())
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), ["formatted.json", "small.json"])

    def test_invalid_input_does_not_change_existing_output_or_input(self):
        path = self.write("invalid.json", {"version": 3})
        output = self.directory / "precious.json"
        output.write_bytes(b"original output")
        original = path.read_bytes()
        for destination in (output, path):
            status, out, err = self.run_command("format", str(path), "--output", str(destination))
            self.assertEqual(status, 1)
            self.assertEqual(output.read_bytes(), b"original output")
            self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(self.directory.glob(".companion-*")))

    def test_legacy_documents_are_not_rewritten_as_single_annotations_by_format(self):
        path = self.write("legacy.json", v1())
        before = path.read_bytes()
        status, out, err = self.run_command("format", str(path), "--output", str(path))
        self.assertEqual(status, 1)
        self.assertEqual(path.read_bytes(), before)

    def test_failed_output_creation_does_not_change_source(self):
        path = self.write("small.json", current_annotation())
        before = path.read_bytes()
        status, out, err = self.run_command("format", str(path), "--output", str(self.directory / "missing" / "out.json"))
        self.assertEqual(status, 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertNotIn("Traceback", out + err)

    def test_failed_atomic_replace_preserves_existing_output_and_cleans_staging(self):
        path = self.write("small.json", current_annotation())
        output = self.directory / "existing.json"
        output.write_bytes(b"keep this output")
        with patch.object(cli.os, "replace", side_effect=OSError("simulated write failure")):
            status, out, err = self.run_command("format", str(path), "--output", str(output))
        self.assertEqual(status, 2)
        self.assertEqual(output.read_bytes(), b"keep this output")
        self.assertFalse(list(self.directory.glob(".companion-*")))

    def test_explicit_in_place_formatting_preserves_companion_data(self):
        path = self.directory / "small.json"
        path.write_text(json.dumps(current_annotation(), ensure_ascii=False), encoding="utf-8")
        status, out, err = self.run_command("format", str(path), "--output", str(path))
        self.assertEqual((status, out, err), (0, "", ""))
        self.assertEqual(companion.loads(path.read_text(encoding="utf-8")), current_annotation())


class TestMigrationCommands(CommandCase):
    def test_success_preserves_exact_original_bytes_and_reports_omissions(self):
        original = self.directory / "legacy.json"
        content = (json.dumps(v1(), ensure_ascii=False, indent="\t").replace("\n", "\r\n") + "\r\n").encode("utf-8")
        original.write_bytes(content)
        output = self.directory / "migration"
        status, out, err = self.run_command("migrate-v1", str(original), "--output", str(output))
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(original.read_bytes(), content)
        self.assertEqual((output / "original-v1.json").read_bytes(), content)
        report = companion.loads((output / "report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["documents"])
        self.assertTrue(any(item["code"] == "unresolved_target" for item in report["diagnostics"]))
        for name in report["documents"]:
            self.assertEqual(companion.validate(companion.loads((output / name).read_text(encoding="utf-8"))), [])
        self.assertIn("review report.json", out)

    def test_relative_sources_require_explicit_context(self):
        path = self.write("legacy.json", v1("tex-lines"))
        output = self.directory / "migration"
        original = path.read_bytes()
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
        self.assertEqual(status, 2)
        self.assertIn("--source-base", err)
        self.assertFalse(output.exists())
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list(self.directory.glob(".companion-migration-*")))

    def test_source_base_resolves_paths_without_guessing_input_directory(self):
        path = self.write("legacy.json", v1("tex-lines"))
        output = self.directory / "migration"
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output),
                                            "--source-base", "https://sources.example.org/revision/")
        self.assertEqual((status, err), (0, ""))
        report = companion.loads((output / "report.json").read_text(encoding="utf-8"))
        documents = [companion.loads((output / name).read_text(encoding="utf-8")) for name in report["documents"]]
        self.assertEqual({doc["source"]["uri"] for doc in documents},
                         {"https://sources.example.org/revision/blueprint/src/chapter1.tex"})

    def test_source_path_punctuation_is_uri_escaped_before_joining(self):
        doc = v1("tex-lines")
        doc["sources"][0]["path"] = "chapter:α#part?x%20.tex"
        path = self.write("legacy.json", doc)
        output = self.directory / "migration"
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output),
                                            "--source-base", "file:///work/project/")
        self.assertEqual((status, err), (0, ""))
        report = companion.loads((output / "report.json").read_text(encoding="utf-8"))
        converted = companion.loads((output / report["documents"][0]).read_text(encoding="utf-8"))
        self.assertEqual(converted["source"]["uri"], "file:///work/project/chapter%3A%CE%B1%23part%3Fx%2520.tex")

    def test_absolute_source_override_is_preserved(self):
        path = self.write("legacy.json", v1("tex-lines"))
        output = self.directory / "migration"
        override = "file:///custom/chapter%20one.tex"
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output),
                                            "--source-uri", f"blueprint-ch1={override}")
        self.assertEqual((status, err), (0, ""))
        report = companion.loads((output / "report.json").read_text(encoding="utf-8"))
        converted = companion.loads((output / report["documents"][0]).read_text(encoding="utf-8"))
        self.assertEqual(converted["source"]["uri"], override)

    def test_absolute_source_references_are_not_parsed_or_rebased(self):
        path = self.write("legacy.json", v1("tex-lines"))
        for index, uri in enumerate(("https://[opaque", "file:chapter.tex", "urn:example:chapter", "https://example.org/α%2Fβ#")):
            output = self.directory / f"migration-{index}"
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output),
                                              "--source-uri", f"blueprint-ch1={uri}",
                                              "--source-base", "file:///ignored/")
            with self.subTest(uri=uri):
                self.assertEqual((status, err), (0, ""))
                report = companion.loads((output / "report.json").read_text(encoding="utf-8"))
                converted = companion.loads((output / report["documents"][0]).read_text(encoding="utf-8"))
                self.assertEqual(converted["source"]["uri"], uri)

    def test_unresolvable_source_base_reports_the_problem_without_publication(self):
        path = self.write("legacy.json", v1("tex-lines"))
        for index, base in enumerate(("https://[malformed", "urn:opaque:base")):
            output = self.directory / f"migration-{index}"
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output), "--source-base", base)
            with self.subTest(base=base):
                self.assertEqual(status, 2)
                self.assertIn("--source-base cannot resolve", err)
                self.assertFalse(output.exists())
                self.assertNotIn("Traceback", out + err)

    def test_invalid_relative_or_duplicate_source_overrides_do_not_write_output(self):
        path = self.write("legacy.json", v1("tex-lines"))
        invalid = [("--source-base", "relative/"), ("--source-uri", "blueprint-ch1=relative.tex"),
                   ("--source-base", "https://example.org/revision/\n"),
                   ("--source-uri", "bad assignment"), ("--source-uri", "unknown=https://example.org/a"),
                   ("--source-uri", "blueprint-ch1=https://example.org/a", "--source-uri", "blueprint-ch1=https://example.org/b")]
        for index, options in enumerate(invalid):
            output = self.directory / f"migration-{index}"
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output), *options)
            with self.subTest(options=options):
                self.assertEqual(status, 2)
                self.assertFalse(output.exists())
                self.assertNotIn("Traceback", out + err)

    def test_relative_formal_targets_require_explicit_target_base(self):
        doc = v1()
        doc["destinations"][0]["href"] = "Mathlib/Ideal.html"
        path = self.write("legacy.json", doc)
        first = self.directory / "without-base"
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(first))
        self.assertEqual((status, err), (0, ""))
        report = companion.loads((first / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["documents"], [])
        self.assertTrue(any(item["code"] == "relative_target_without_base" for item in report["diagnostics"]))
        second = self.directory / "with-base"
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(second),
                                            "--target-base", "https://formal.example.org/docs/")
        self.assertEqual((status, err), (0, ""))
        report = companion.loads((second / "report.json").read_text(encoding="utf-8"))
        converted = companion.loads((second / report["documents"][0]).read_text(encoding="utf-8"))
        self.assertEqual(converted["target"],
                         "https://formal.example.org/docs/Mathlib/Ideal.html#Ideal.IsPrime")

    def test_existing_files_directories_and_input_are_protected(self):
        path = self.write("legacy.json", v1())
        existing_file = self.directory / "existing-file"
        existing_file.write_bytes(b"preserve me")
        existing_directory = self.directory / "existing-directory"
        existing_directory.mkdir()
        marker = existing_directory / "marker"
        marker.write_bytes(b"preserve marker")
        original = path.read_bytes()
        for output in (path, existing_file, existing_directory):
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
            with self.subTest(output=output):
                self.assertEqual(status, 2)
                self.assertIn("already exists", err)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(existing_file.read_bytes(), b"preserve me")
        self.assertEqual(marker.read_bytes(), b"preserve marker")

    def test_existing_symlink_is_protected(self):
        path = self.write("legacy.json", v1())
        symlink = self.directory / "dangling-link"
        try:
            symlink.symlink_to(self.directory / "not-created")
        except NotImplementedError:
            self.skipTest("symbolic links are unavailable on this platform")
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("this Windows user cannot create symbolic links")
            raise
        status, out, err = self.run_command("migrate-v1", str(path), "--output", str(symlink))
        self.assertEqual(status, 2)
        self.assertIn("already exists", err)
        self.assertTrue(symlink.is_symlink())

    def test_malformed_v1_input_never_creates_a_partial_directory(self):
        for index, content in enumerate((b"{", b'{"schema":"unknown"}', b'{"a":NaN}', b"\xff")):
            path = self.directory / f"malformed-{index}.json"
            path.write_bytes(content)
            output = self.directory / f"migration-{index}"
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
            self.assertEqual(status, 2)
            self.assertFalse(output.exists())
            self.assertEqual(path.read_bytes(), content)
            self.assertNotIn("Traceback", out + err)
        self.assertFalse(list(self.directory.glob(".companion-migration-*")))

    def test_failure_after_archiving_still_leaves_no_partial_output(self):
        path = self.write("legacy.json", v1())
        original = path.read_bytes()
        output = self.directory / "migration"
        real_dumps = companion.dumps

        def fail_on_projection(value):
            if isinstance(value, dict) and "source" in value and "target" in value:
                raise companion.LoadError("simulated projection serialization failure")
            return real_dumps(value)

        with patch.object(companion, "dumps", side_effect=fail_on_projection):
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
        self.assertEqual(status, 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.directory.glob(".companion-migration-*")))

    def test_migration_never_replaces_a_concurrently_created_empty_directory(self):
        path = self.write("legacy.json", v1())
        output = self.directory / "migration"
        publish = cli._publish_directory
        existing_inode = None

        def race(source, destination):
            nonlocal existing_inode
            destination.mkdir()
            existing_inode = destination.stat().st_ino
            return publish(source, destination)

        with patch.object(cli, "_publish_directory", side_effect=race):
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
        self.assertEqual(status, 2)
        self.assertEqual(list(output.iterdir()), [])
        self.assertEqual(output.stat().st_ino, existing_inode)
        self.assertNotIn("Traceback", out + err)
        self.assertFalse(list(self.directory.glob(".companion-migration-*")))

    def test_unsupported_atomic_publication_fails_without_partial_output(self):
        path = self.write("legacy.json", v1())
        output = self.directory / "migration"
        with patch.object(cli.sys, "platform", "unsupported"), \
             patch.object(cli.ctypes, "CDLL", side_effect=AssertionError("must not load a native library")):
            status, out, err = self.run_command("migrate-v1", str(path), "--output", str(output))
        self.assertEqual(status, 2)
        self.assertIn("atomic no-replace", err)
        self.assertNotIn("Traceback", out + err)
        self.assertFalse(output.exists())
        self.assertFalse(list(self.directory.glob(".companion-migration-*")))


class TestSingleAnnotationDiscovery(CommandCase):
    def test_machine_validation_reports_every_input_and_read_error_wins(self):
        invalid = self.write("invalid.json", {"version": 3})
        missing = self.directory / "missing.json"
        valid = self.write("valid.json", current_annotation())
        status, out, err = self.run_command("validate", str(invalid), str(missing), str(valid), "--format", "json")
        reports = [json.loads(line) for line in out.splitlines()]
        self.assertEqual((status, err), (2, ""))
        self.assertEqual([report["status"] for report in reports], [1, 2, 0])
        self.assertEqual(reports[0]["problems"][0]["code"], "SCHEMA")
        self.assertEqual(reports[1]["problems"][0]["code"], "IO")
        self.assertTrue(reports[2]["valid"])

    def test_release_candidate_is_reported_as_distinct_dialect(self):
        path = self.write("rc3.json", {"schema": "formal-companion/annotations", "schema_version": "1.0"})
        status, out, err = self.run_command("validate", str(path), "--format", "json")
        report = json.loads(out)
        self.assertEqual((status, err), (1, ""))
        self.assertEqual(report["problems"][0]["code"], "UNSUPPORTED_FORMAT")
        self.assertIn("PR #2", report["problems"][0]["message"])

    def test_collection_carriers_are_separate_from_single_annotation_validation(self):
        first = self.write("chapter.json", [current_annotation(), current_annotation()])
        nested = self.directory / "nested"
        nested.mkdir()
        second = nested / "generated.jsonl"
        second.write_text("\n" + json.dumps(current_annotation()) + "\n", encoding="utf-8")
        status, _, _ = self.run_command("validate", str(first))
        self.assertEqual(status, 1)
        status, out, err = self.run_command("scan", str(self.directory), str(first), "--format", "json")
        report = json.loads(out)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(len(report["files"]), 2)
        records = report["records"]
        self.assertEqual([record["annotation"] for record in records], [current_annotation(), current_annotation(), current_annotation()])
        self.assertEqual([record["origin"]["pointer"] for record in records], ["/0", "/1", ""])
        self.assertEqual(records[2]["origin"]["line"], 2)
        self.assertEqual(records[0]["origin"]["base_uri"], first.resolve().as_uri())
        self.assertEqual(records[2]["origin"]["base_uri"], second.resolve().as_uri())
        self.assertNotEqual(records[0]["origin"]["base_uri"], records[2]["origin"]["base_uri"])

    def test_scan_preserves_valid_records_but_reports_failure_and_exact_origins(self):
        self.write("array.json", [current_annotation(), {"version": 99}])
        stream = self.directory / "stream.jsonl"
        stream.write_text(json.dumps(current_annotation()) + "\n{\n" + json.dumps(current_annotation()) + "\n", encoding="utf-8")
        status, out, err = self.run_command("scan", str(self.directory), "--format", "json")
        result = json.loads(out)
        self.assertEqual((status, err), (2, ""))
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["records"]), 3)
        self.assertTrue(any("#/1" in problem["path"] for problem in result["problems"]))
        self.assertTrue(any("line 2" in problem["path"] and problem["code"] == "JSON"
                            for problem in result["problems"]))

    def test_scope_patterns_leave_graph_and_reports_as_application_data(self):
        self.write("one.annotations.json", current_annotation())
        self.write("graph.json", {"nodes": [{"annotation": current_annotation()}]})
        status, _, _ = self.run_command("scan", str(self.directory))
        self.assertEqual(status, 1)
        status, out, err = self.run_command("scan", str(self.directory), "--include", "*.annotations.json", "--format", "json")
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(len(json.loads(out)["records"]), 1)
        status, out, err = self.run_command("scan", str(self.directory), "--exclude", "*", "--format", "json")
        self.assertEqual((status, err), (2, ""))
        self.assertEqual(json.loads(out)["problems"][0]["code"], "NO_ANNOTATIONS")

    def test_scan_broken_install_keeps_machine_error_output(self):
        path = self.write("one.json", current_annotation())
        with patch.object(companion, "SCHEMA_PATH", self.directory / "missing-schema.json"):
            status, out, err = self.run_command("scan", str(path), "--format", "json")
        self.assertEqual((status, err), (2, ""))
        self.assertFalse(json.loads(out)["valid"])

    def test_source_collection_draft_is_not_silently_unwrapped(self):
        old = {"source": current_annotation()["source"], "annotations": [{"target": "urn:formal:one"}]}
        path = self.write("old-draft.json", old)
        before = path.read_bytes()
        status, _, _ = self.run_command("format", str(path), "--output", str(path))
        self.assertEqual(status, 1)
        self.assertEqual(path.read_bytes(), before)


class TestJsonStdout(CommandCase):
    def run_ansi(self, *arguments: str) -> subprocess.CompletedProcess:
        package_root = str(Path(formal_companion_annotations.__file__).resolve().parent.parent)
        environment = dict(os.environ, PYTHONPATH=package_root, PYTHONDONTWRITEBYTECODE="1",
                           PYTHONIOENCODING="cp1252")
        return subprocess.run([sys.executable, *arguments], cwd=self.directory,
                              env=environment, capture_output=True, check=False)

    def decode_output(self, result: subprocess.CompletedProcess, status: int = 0):
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertTrue(result.stdout.endswith(b"\n"))
        self.assertNotIn(b"\r\n", result.stdout)
        return companion.loads(result.stdout.decode("utf-8"))

    def test_current_json_commands_write_utf8_even_when_stdout_uses_an_ansi_codepage(self):
        # é is representable in cp1252 but has different bytes; α is not
        # representable at all. Both must survive a redirected JSON protocol.
        for text in ("é", "α"):
            doc = current_annotation()
            doc["extensions"] = {"example": text}
            path = self.write(f"annotation-{text}.json", doc)
            for command in (("format", str(path)), ("scan", str(path), "--format", "json"),
                            ("validate", str(path), "--format", "json")):
                with self.subTest(text=text, command=command[0]):
                    result = self.run_ansi("-m", "formal_companion_annotations.cli", *command)
                    output = self.decode_output(result)
                    if command[0] == "format":
                        self.assertEqual(output, doc)
                    elif command[0] == "scan":
                        self.assertEqual(output["records"][0]["annotation"], doc)
                    else:
                        self.assertTrue(output["valid"])
                        self.assertEqual(output["document"], str(path))

    def test_scan_machine_error_is_utf8_with_an_ansi_stdout(self):
        path = self.write("annotation.json", current_annotation())
        script = """from pathlib import Path
import sys
from formal_companion_annotations import cli, companion
companion.SCHEMA_PATH = Path(sys.argv[1])
raise SystemExit(cli.main(['scan', sys.argv[2], '--format', 'json']))
"""
        for text in ("é", "α"):
            with self.subTest(text=text):
                missing = self.directory / f"missing-schema-{text}.json"
                result = self.run_ansi("-c", script, str(missing), str(path))
                output = self.decode_output(result, status=2)
                self.assertFalse(output["valid"])
                self.assertIn(repr(str(missing)), output["problems"][0]["message"])

    def test_legacy_canonical_stdout_is_exact_utf8_with_an_ansi_stdout(self):
        for text in ("é", "α"):
            with self.subTest(text=text):
                doc = v1()
                doc["companion"]["name"] = f"companion-{text}"
                path = self.write("legacy.json", doc)
                result = self.run_ansi("-m", "formal_companion_annotations.validate", str(path), "--print-canonical")
                self.assertEqual(self.decode_output(result), validate.canonicalize(doc))
                self.assertEqual(result.stdout, validate.canonical_dumps(validate.canonicalize(doc)).encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
