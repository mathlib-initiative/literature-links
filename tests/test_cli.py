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
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

import literature_links
from literature_links import cli, companion


def current_annotation() -> dict:
    return {"subject": [{"type": "generic", "uri": "../source.json",
                         "location": {"custom": {"z": 2**100, "a": [3, 2, 1]}}}],
            "id": "z", "object": [{"type": "generic", "uri": "urn:formal:first"}],
            "extensions": {"tool": {"z": "α", "a": None}, "owner.example": {"unrecognized": True}}}


class CommandCase(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix="companion-cli-")
        self.addCleanup(self.workspace.cleanup)
        self.directory = Path(self.workspace.name)

    def write(self, name: str, document: dict) -> Path:
        path = self.directory / name
        path.write_text(companion.dumps(document), encoding="utf-8", newline="\n")
        return path

    def run_command(self, *arguments: str) -> tuple[int, str, str]:
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                status = cli.main(list(arguments))
            except SystemExit as exc:
                status = exc.code
        return status, stdout.getvalue(), stderr.getvalue()

    def run_module(self, module: str, *arguments: str, parser_failure: bool = False) -> subprocess.CompletedProcess:
        package_root = str(Path(literature_links.__file__).resolve().parent.parent)
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
    def test_new_validate_reports_mixed_valid_and_invalid_files(self):
        first, second = self.write("valid.json", current_annotation()), self.write("invalid.json", {"version": 3})
        status, out, err = self.run_command("validate", str(first), str(second))
        self.assertEqual(status, 1)
        self.assertIn(f"{first}: ok", out)
        self.assertIn(f"{second}: $: is missing required key 'subject' [SCHEMA]", out)
        self.assertIn(f"{second}: $: is missing required key 'object' [SCHEMA]", out)
        self.assertEqual(err, "")

    def test_invalid_json_and_missing_files_exit_two_without_tracebacks(self):
        for index, content in enumerate((b"{", b'{"version":2,"version":2}', b"\xff", b"1e999", b'"\\ud800"')):
            path = self.directory / f"malformed-{index}.json"
            path.write_bytes(content)
            status, out, err = self.run_command("validate", str(path))
            with self.subTest(content=content):
                self.assertEqual(status, 2)
                self.assertNotIn("Traceback", out + err)
        status, out, err = self.run_command("validate", str(self.directory / "missing.json"))
        self.assertEqual(status, 2)
        self.assertNotIn("Traceback", out + err)

    def test_deep_input_fails_cleanly_in_supported_module_entry_points(self):
        path = self.directory / "too-deep.json"
        # Parser nesting limits vary between Python releases. A parser may
        # reject this input, or accept it and let validation reject its shape.
        path.write_text("[" * 100_000 + "0" + "]" * 100_000, encoding="utf-8")
        for module in ("literature_links.cli", "literature_links"):
            result = self.run_module(module, "validate", str(path))
            with self.subTest(module=module):
                self.assertIn(result.returncode, (1, 2), result.stdout + result.stderr)
                self.assertIn(str(path), result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_parser_failures_exit_two_in_supported_module_entry_points(self):
        path = self.write("annotation.json", current_annotation())
        for module in ("literature_links.cli", "literature_links"):
            result = self.run_module(module, "validate", str(path), parser_failure=True)
            with self.subTest(module=module):
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("simulated JSON parser limit", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)


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
        undecodable = self.directory / "undecodable.json"
        undecodable.write_bytes(b"\xff")
        status, out, _ = self.run_command("validate", str(undecodable), "--format", "json")
        self.assertEqual((status, json.loads(out)["problems"][0]["code"]), (2, "IO"))

    def test_many_annotations_go_in_jsonl_which_scan_reads(self):
        first = self.write("chapter.json", current_annotation())
        nested = self.directory / "nested"
        nested.mkdir()
        second = nested / "generated.jsonl"
        second.write_text("\n" + json.dumps(current_annotation()) + "\n" + json.dumps(current_annotation()) + "\n",
                          encoding="utf-8")
        status, out, err = self.run_command("scan", str(self.directory), str(first), "--format", "json")
        report = json.loads(out)
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(len(report["files"]), 2)
        records = report["records"]
        self.assertEqual([record["annotation"] for record in records], [current_annotation()] * 3)
        self.assertEqual([record["origin"]["line"] for record in records], [None, 2, 3])
        self.assertEqual(records[0]["origin"]["base_uri"], first.resolve().as_uri())
        self.assertEqual(records[1]["origin"]["base_uri"], second.resolve().as_uri())

    def test_a_json_file_holding_an_array_exits_one(self):
        array = self.write("chapter.json", [current_annotation(), current_annotation()])
        message = "a JSON file holds one annotation, an object, not an array"
        status, out, err = self.run_command("validate", str(array))
        self.assertEqual((status, out, err), (1, f"{array}: $: {message} [SHAPE]\n", ""))
        status, out, _ = self.run_command("validate", str(array), "--format", "json")
        self.assertEqual((status, json.loads(out)["problems"]), (1, [{"code": "SHAPE", "path": "$", "message": message}]))
        status, out, _ = self.run_command("scan", str(array), "--format", "json")
        self.assertEqual((status, json.loads(out)["problems"]),
                         (1, [{"code": "SHAPE", "path": str(array.resolve()), "message": message}]))

    def test_validate_and_scan_agree_that_a_scalar_is_not_an_annotation(self):
        message = "each annotation must be a JSON object"
        for text in ("1", "null", '"x"'):
            path = self.directory / "scalar.json"
            path.write_text(text, encoding="utf-8")
            with self.subTest(text=text):
                self.assertEqual(self.run_command("validate", str(path)), (1, f"{path}: $: {message} [SHAPE]\n", ""))
                status, out, _ = self.run_command("scan", str(path), "--format", "json")
                self.assertEqual((status, json.loads(out)["problems"]),
                                 (1, [{"code": "SHAPE", "path": str(path.resolve()), "message": message}]))

    def test_validate_reads_jsonl_by_line(self):
        rows = self.directory / "rows.jsonl"
        rows.write_text("\n" + json.dumps(current_annotation()) + "\r\n\n" + json.dumps(current_annotation()) + "\n",
                        encoding="utf-8", newline="")
        self.assertEqual(self.run_command("validate", str(rows)), (0, f"{rows}: ok (2 annotations, generic)\n", ""))
        bad = self.directory / "bad.ndjson"
        bad.write_text("\n".join([json.dumps(current_annotation()), '{"subject": {}}', "[]",
                                  json.dumps(current_annotation())]), encoding="utf-8")
        status, out, err = self.run_command("validate", str(bad), "--format", "json")
        self.assertEqual((status, err), (1, ""))
        self.assertEqual([(problem["code"], problem["path"]) for problem in json.loads(out)["problems"]],
                         [("SCHEMA", "line 2 $"), ("SCHEMA", "line 2 $.subject"), ("SHAPE", "line 3 $")])
        broken = self.directory / "broken.jsonl"
        broken.write_text(json.dumps(current_annotation()) + "\n{\n[]\n", encoding="utf-8")
        status, out, err = self.run_command("validate", str(broken))
        self.assertEqual(status, 2)
        self.assertIn(f"{broken}: line 2 $: not JSON", err)
        self.assertIn(f"{broken}: line 3 $: each annotation must be a JSON object [SHAPE]", err)
        empty = self.directory / "empty.jsonl"
        empty.write_text(" \n\t\n", encoding="utf-8")
        self.assertEqual(self.run_command("validate", str(empty)),
                         (2, "", f"{empty}: $: the file holds no annotations [NO_ANNOTATIONS]\n"))

    def test_validate_names_each_type_of_end_once_in_order_of_appearance(self):
        mathlib = {"type": "lean", "uri": "https://github.com/leanprover-community/mathlib4"}
        rows = self.directory / "rows.jsonl"
        rows.write_text("\n".join(json.dumps(row) for row in (
            {"subject": [{"type": "pdf", "uri": "a.pdf"}], "object": [mathlib]},
            {"subject": [{"type": "html", "uri": "a.html"}, {"type": "pdf", "uri": "b.pdf"}], "object": []},
            {"subject": [{"type": "latex", "uri": "a.tex"}], "object": [{"type": "generic", "uri": "x"}, mathlib]})),
            encoding="utf-8")
        self.assertEqual(self.run_command("validate", str(rows)),
                         (0, f"{rows}: ok (3 annotations, pdf, lean, html, latex, generic)\n", ""))

    def test_validate_reports_a_broken_defaults_file_once_per_jsonl_file(self):
        (self.directory / "_defaults.json").write_text("[]", encoding="utf-8")
        rows = self.directory / "rows.jsonl"
        rows.write_text((json.dumps(current_annotation()) + "\n") * 3, encoding="utf-8")
        defaults = (self.directory / "_defaults.json").resolve()
        self.assertEqual(self.run_command("validate", str(rows)),
                         (1, f"{rows}: {defaults}: a defaults file must hold one JSON object [DEFAULTS]\n", ""))

    def test_scan_preserves_valid_records_but_reports_failure_and_exact_origins(self):
        self.write("single.json", current_annotation())
        self.write("invalid.json", {"version": 99})
        stream = self.directory / "stream.jsonl"
        stream.write_text(json.dumps(current_annotation()) + "\n{\n" + json.dumps(current_annotation()) + "\n", encoding="utf-8")
        status, out, err = self.run_command("scan", str(self.directory), "--format", "json")
        result = json.loads(out)
        self.assertEqual((status, err), (2, ""))
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["records"]), 3)
        self.assertTrue(any(problem["path"].startswith(f"{(self.directory / 'invalid.json').resolve()} $")
                            and problem["code"] == "SCHEMA" for problem in result["problems"]))
        self.assertTrue(any("line 2" in problem["path"] and problem["code"] == "JSON"
                            for problem in result["problems"]))

    def test_the_json_reports_have_this_shape(self):
        good = self.write("a.json", current_annotation())
        bad = self.write("b.json", [current_annotation()])
        status, out, err = self.run_command("scan", str(self.directory), "--format", "json")
        self.assertEqual((status, err), (1, ""))
        self.assertEqual(json.loads(out), {
            "valid": False, "status": 1, "files": [str(good.resolve()), str(bad.resolve())],
            "records": [{"annotation": current_annotation(),
                         "origin": {"path": str(good.resolve()), "line": None,
                                    "base_uri": good.resolve().as_uri(), "defaults": []}}],
            "problems": [{"code": "SHAPE", "path": str(bad.resolve()),
                          "message": "a JSON file holds one annotation, an object, not an array"}]})
        status, out, err = self.run_command("validate", str(good), "--format", "json")
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(json.loads(out), {"document": str(good), "valid": True, "status": 0, "defaults": [],
                                           "problems": [], "warnings": []})

    def test_a_defaults_file_that_is_not_an_object_exits_one(self):
        self.write("a.json", current_annotation())
        (self.directory / "_defaults.json").write_text("[]", encoding="utf-8")
        status, out, _ = self.run_command("scan", str(self.directory), "--format", "json")
        self.assertEqual((status, [problem["code"] for problem in json.loads(out)["problems"]]), (1, ["DEFAULTS"]))

    def test_options_are_not_abbreviated(self):
        good = self.write("a.json", current_annotation())
        for arguments in (("scan", str(good), "--form", "json"), ("validate", str(good), "--form", "json"),
                          ("scan", str(good), "--incl", "*"), ("--vers",)):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.run_command(*arguments)[0], 2)

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

    def test_scan_text_summary_counts_in_words_and_a_run_problem_has_no_path(self):
        self.write("one.json", current_annotation())
        status, out, err = self.run_command("scan", str(self.directory))
        self.assertEqual((status, out, err), (0, "1 annotation from 1 file; 0 problems\n", ""))
        status, out, err = self.run_command("scan", str(self.directory), "--exclude", "*")
        self.assertEqual((status, err), (2, ""))
        self.assertEqual(out, "no annotations were found in the selected inputs [NO_ANNOTATIONS]\n"
                              "0 annotations from 0 files; 1 problem\n")

    def test_help_names_the_arguments_and_the_exit_statuses(self):
        for command, metavars in (("validate", ("FILE",)), ("scan", ("PATH", "PATTERN"))):
            status, out, _ = self.run_command(command, "--help")
            with self.subTest(command=command):
                self.assertEqual(status, 0)
                for metavar in metavars:
                    self.assertIn(metavar, out)
                self.assertIn("exit status: 0", out)

    def test_scan_read_path_and_symlink_failures_exit_two(self):
        unreadable = self.directory / "unreadable.json"
        unreadable.write_bytes(b"\xff")
        cases = [unreadable, self.directory / "missing.json"]
        link = self.directory / "link.json"
        try:
            link.symlink_to(self.write("good.json", current_annotation()))
            cases.append(link)
        except (NotImplementedError, OSError):
            pass  # Windows without symlink privilege
        for path in cases:
            with self.subTest(path=path.name):
                self.assertEqual(self.run_command("scan", str(path))[0], 2)

    def test_scan_broken_install_exits_two_in_json_and_text(self):
        path = self.write("one.json", current_annotation())
        with patch.object(companion, "SCHEMA_PATH", self.directory / "missing-schema.json"):
            status, out, err = self.run_command("scan", str(path), "--format", "json")
            text_status, text_out, text_err = self.run_command("scan", str(path))
        self.assertEqual((status, err), (2, ""))
        self.assertFalse(json.loads(out)["valid"])
        self.assertEqual((text_status, text_out), (2, ""))
        self.assertTrue(text_err.startswith("literature-links: "), text_err)
        self.assertIn("missing-schema.json", text_err)


class TestJsonStdout(CommandCase):
    def run_ansi(self, *arguments: str) -> subprocess.CompletedProcess:
        package_root = str(Path(literature_links.__file__).resolve().parent.parent)
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
                    result = self.run_ansi("-m", "literature_links.cli", *command)
                    output = self.decode_output(result)
                    if command[0] == "scan":
                        self.assertEqual(output["records"][0]["annotation"], doc)
                    else:
                        self.assertTrue(output["valid"])
                        self.assertEqual(output["document"], str(path))

    def test_text_output_escapes_what_an_ansi_stdout_cannot_encode(self):
        path = self.write("annotation-α.json", current_annotation())
        later = self.write("later.json", current_annotation())
        result = self.run_ansi("-m", "literature_links.cli", "validate", str(path), str(later))
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertIn(b"annotation-\\u03b1.json: ok", result.stdout)
        self.assertIn(b"later.json: ok", result.stdout)

    def test_text_output_keeps_a_surrogateescape_stdout(self):
        # UTF-8 mode and LC_ALL=C print a non-UTF-8 file name as its own bytes.
        buffer = io.BytesIO()
        stdout = io.TextIOWrapper(buffer, encoding="utf-8", errors="surrogateescape")
        with redirect_stdout(stdout), redirect_stderr(io.StringIO()):
            cli.main(["scan", str(self.directory / "caf\udce9.json")])
        stdout.flush()
        self.assertIn(b"caf\xe9.json: ", buffer.getvalue())

    def test_scan_machine_error_is_utf8_with_an_ansi_stdout(self):
        path = self.write("annotation.json", current_annotation())
        script = """from pathlib import Path
import sys
from literature_links import cli, companion
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

if __name__ == "__main__":
    unittest.main()
