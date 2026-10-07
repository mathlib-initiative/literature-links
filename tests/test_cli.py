"""End-to-end behavior of the validate and scan commands."""
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
            status, out, err = self.run_command("validate", str(path))
            with self.subTest(content=content):
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
        status, out, err = self.run_command("validate", str(path))
        self.assertIn(status, (1, 2))
        self.assertIn("surrogate", out + err)
        self.assertNotIn("Traceback", out + err)


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
            for command in (("scan", str(path), "--format", "json"),
                            ("validate", str(path), "--format", "json")):
                with self.subTest(text=text, command=command[0]):
                    result = self.run_ansi("-m", "formal_companion_annotations.cli", *command)
                    output = self.decode_output(result)
                    if command[0] == "scan":
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
