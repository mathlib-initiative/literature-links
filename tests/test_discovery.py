"""Reading annotations from files and directories, with their origins and problems."""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if importlib.util.find_spec("literature_links") is None:
    sys.path.insert(0, str(ROOT / "src"))

from literature_links import companion, discovery


def annotation(page: int = 1) -> dict:
    return {"subject": [{"type": "pdf", "uri": "../source/book.pdf", "location": {"page": page}}],
            "object": [{"type": "html", "uri": "../site/Module.html#result"}]}


def first_page(record: discovery.Record) -> int:
    return record.annotation["subject"][0]["location"]["page"]


class TestDiscovery(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def write(self, relative: str, value: object) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def raw(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def symlink(self, path: Path, target: Path, *, directory: bool = False) -> None:
        try:
            path.symlink_to(target, target_is_directory=directory)
        except NotImplementedError:
            self.skipTest("symbolic links are unavailable on this platform")
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1314:
                self.skipTest("this Windows user cannot create symbolic links")
            raise

    def test_json_and_jsonl_files_are_walked_in_order_with_their_origins(self):
        single = self.write("a.json", annotation(1))
        nested = self.write("chapter/b.json", annotation(2))
        jsonl = self.raw("chapter/c.jsonl", "\n" + json.dumps(annotation(3)) + "\n\n" + json.dumps(annotation(4)))
        ndjson = self.raw("z.ndjson", json.dumps(annotation(5)) + "\n")
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [single, nested, jsonl, ndjson])
        self.assertEqual([first_page(r) for r in result.records], list(range(1, 6)))
        self.assertEqual([r.line for r in result.records], [None, None, 2, 4, 1])

    def test_every_record_uses_its_file_as_reference_base(self):
        first = self.raw("first/links.jsonl", json.dumps(annotation()) + "\n" + json.dumps(annotation(2)))
        second = self.write("second/link.json", annotation())
        result = discovery.collect([first, second])
        self.assertEqual(result.problems, [])
        self.assertEqual([r.base_uri for r in result.records],
                         [first.as_uri(), first.as_uri(), second.as_uri()])
        self.assertEqual(result.records[0].annotation["subject"][0]["uri"], "../source/book.pdf")
        self.assertEqual(result.records[0].annotation["object"][0]["uri"], "../site/Module.html#result")

    def test_the_base_does_not_follow_later_file_system_changes(self):
        file = self.write("original/link.json", annotation())
        record = discovery.collect([file]).records[0]
        captured = record.base_uri
        file.parent.rename(self.root / "moved")
        replacement = self.root / "replacement"
        replacement.mkdir()
        self.symlink(file.parent, replacement, directory=True)
        self.assertEqual(record.path, file)
        self.assertEqual(record.base_uri, captured)
        self.assertEqual(record.base_uri, file.as_uri())

    def test_repeated_ids_equal_records_and_equal_objects_are_preserved(self):
        first = annotation()
        first["id"] = "optional-id"
        second = annotation(2)
        second["id"] = "optional-id"
        original = [first, copy.deepcopy(first), second]
        self.raw("links.jsonl", "\n".join(map(json.dumps, original)))
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual([r.annotation for r in result.records], original)

    def test_overlapping_inputs_do_not_read_the_same_file_twice(self):
        path = self.write("nested/a.json", annotation())
        result = discovery.collect([path, self.root, path.parent, self.root / "nested" / ".." / "nested" / "a.json"])
        self.assertEqual(result.problems, [])
        self.assertEqual(len(result.files), 1)
        self.assertEqual(len(result.records), 1)

    def test_default_selection_has_no_hidden_directory_exclusions(self):
        first = self.write(".annotations/a.JSON", annotation())
        self.raw("readme.txt", "not JSON")
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [first])

    def test_include_and_exclude_patterns_scope_a_repository(self):
        first = self.write("a.annotation.json", annotation())
        second = self.write("chapters/b.annotation.json", annotation())
        self.write("graph.json", {"version": 1, "nodes": {}})
        self.raw("cache/broken.annotation.json", "bad JSON")
        result = discovery.collect([self.root], include=["**/*.annotation.json"], exclude=["cache/**"])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [first, second])

    def test_include_can_select_custom_suffix_and_exclude_wins(self):
        selected = self.write("chapter/link.annotation", annotation())
        self.raw("chapter/broken.annotation", "bad JSON")
        result = discovery.collect([self.root], include=["*.annotation"], exclude=["*/broken.annotation"])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [selected])

    def test_patterns_are_case_sensitive(self):
        self.write("a.json", annotation())
        self.assertEqual([p.code for p in discovery.collect([self.root], include=["*.JSON"]).problems], ["NO_ANNOTATIONS"])

    def test_explicit_files_support_arbitrary_suffixes_and_patterns(self):
        selected = self.write("link.data", annotation())
        self.assertEqual(discovery.collect([selected]).files, [selected])
        result = discovery.collect([selected], include=["link.*"])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [selected])
        result = discovery.collect([selected], exclude=["link.*"])
        self.assertEqual([p.code for p in result.problems], ["NO_ANNOTATIONS"])

    def test_selected_unrelated_json_fails_instead_of_searching_inside_it(self):
        nested = self.write("graph.json", {"nodes": {"one": annotation()}})
        result = discovery.collect([self.root])
        self.assertEqual(result.records, [])
        self.assertTrue(result.problems)
        self.assertTrue(all(str(nested) in p.path for p in result.problems))

    def test_a_json_file_holding_an_array_is_a_problem(self):
        good = self.write("good.json", annotation())
        arrays = [self.write(f"links-{size}.json", [annotation()] * size) for size in (0, 1, 2)]
        result = discovery.collect([self.root])
        self.assertEqual([r.path for r in result.records], [good])
        self.assertEqual([(p.code, p.path, p.message) for p in result.problems],
                         [("SHAPE", str(path), "a JSON file holds one annotation, an object, not an array")
                          for path in arrays])
        named = self.write("links.data", [annotation()])
        self.assertEqual([p.code for p in discovery.collect([named]).problems], ["SHAPE"])
        rows = discovery.collect([self.raw("links.jsonl", "\n".join(json.dumps(annotation()) for _ in range(2)))])
        self.assertEqual((len(rows.records), rows.problems), (2, []))

    def test_bad_jsonl_rows_report_their_line_and_keep_other_valid_records(self):
        bad = annotation()
        bad["subject"][0]["location"]["page"] = 0
        path = self.raw("links.jsonl", "\n".join(map(json.dumps, [annotation(), bad, None, annotation(3)])))
        result = discovery.collect([path])
        self.assertEqual([r.line for r in result.records], [1, 4])
        # The path is the file, then the line, then the place in the annotation.
        self.assertEqual([(p.code, p.path) for p in result.problems],
                         [("SCHEMA", f"{path} (line 2) $.subject[0].location.page"), ("SHAPE", f"{path} (line 3)")])

    def test_jsonl_reports_physical_line_and_disallows_array_rows(self):
        path = self.raw("links.jsonl", "\n" + json.dumps(annotation()) + "\n{broken}\n[]\n" + json.dumps(annotation(2)))
        result = discovery.collect([path])
        self.assertEqual([r.line for r in result.records], [2, 5])
        self.assertTrue(any(p.code == "JSON" and "line 3" in p.path for p in result.problems))
        self.assertTrue(any(p.code == "SHAPE" and "line 4" in p.path for p in result.problems))

    def test_jsonl_crlf_and_cr_end_lines(self):
        path = self.root / "links.JSONL"
        path.write_bytes(b"\r\n".join(json.dumps(annotation(page)).encode() for page in (1, 2)) + b"\r"
                         + json.dumps(annotation(3)).encode())
        result = discovery.collect([path])
        self.assertEqual(result.problems, [])
        self.assertEqual([r.line for r in result.records], [1, 2, 3])

    def test_jsonl_lines_do_not_end_at_unicode_line_separators(self):
        value = annotation()
        value["extensions"] = {"example": {"text": "first\u2028second\u2029third"}}
        path = self.raw("links.jsonl", json.dumps(value, ensure_ascii=False) + "\n")
        result = discovery.collect([path])
        self.assertEqual(result.problems, [])
        self.assertEqual([r.annotation for r in result.records], [value])

    def test_strict_json_rejects_duplicates_nonfinite_and_surrogates(self):
        cases = ['{"version": 2, "version": 2}', '{"number": NaN}', '{"number": 1e999}',
                 '{"text": "\\ud800"}']
        for index, text in enumerate(cases):
            with self.subTest(text=text):
                path = self.raw(f"bad-{index}.json", text)
                result = discovery.collect([path])
                self.assertEqual([p.code for p in result.problems], ["JSON"])

    def test_a_byte_order_mark_is_a_json_problem(self):
        message = "not JSON: the text starts with a byte order mark"
        single = self.raw("a.json", "\ufeff" + json.dumps(annotation()))
        rows = self.raw("b.jsonl", "\ufeff" + json.dumps(annotation(1)) + "\n" + json.dumps(annotation(2)) + "\n")
        result = discovery.collect([self.root])
        self.assertEqual([(p.code, p.path, p.message) for p in result.problems],
                         [("JSON", str(single), message), ("JSON", f"{rows} (line 1)", message)])
        self.assertEqual([(r.path, r.line) for r in result.records], [(rows, 2)])

    def test_generic_locations_and_extension_values_are_opaque(self):
        value = {"subject": [{"type": "generic", "uri": "urn:example:record", "location": {"z": [3, 2, 1], "a": {}}}],
                 "object": [{"type": "generic", "uri": "urn:example:formal"}],
                 "extensions": {"example": {"large": 2 ** 100, "order": [False, None, "a"]}}}
        path = self.write("link.json", value)
        result = discovery.collect([path])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.records[0].annotation, value)
        self.assertEqual(list(result.records[0].annotation["subject"][0]["location"]), ["z", "a"])

    def test_missing_path_and_invalid_utf8_are_reported_with_other_results(self):
        good = self.write("good.json", annotation())
        invalid = self.root / "invalid.json"
        invalid.write_bytes(b"\xff")
        missing = self.root / "missing"
        result = discovery.collect([good, invalid, missing])
        self.assertEqual(len(result.records), 1)
        self.assertEqual({p.code for p in result.problems}, {"PATH", "IO"})
        self.assertTrue(any(str(missing) == p.path for p in result.problems))

    def test_files_are_read_in_the_same_order_on_every_platform(self):
        nested = self.write("a/x.json", annotation())
        flat = self.write("a0.json", annotation())
        self.assertEqual(discovery.collect([self.root]).files, [nested.resolve(), flat.resolve()])

    def test_alias_paths_keep_canonical_origins_and_read_once(self):
        file = self.write("link.json", annotation())
        child = self.root / "child"
        child.mkdir()
        alias = child / ".." / file.name
        result = discovery.collect([alias, file])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [file.resolve()])
        self.assertEqual(result.records[0].path, file.resolve())
        self.assertEqual(result.records[0].base_uri, file.resolve().as_uri())

    def test_impossible_api_path_is_reported_without_aborting_other_files(self):
        file = self.write("valid.json", annotation())
        result = discovery.collect([file, self.root / "invalid\x00name.json"])
        self.assertEqual(len(result.records), 1)
        self.assertEqual([problem.code for problem in result.problems], ["PATH"])

    def test_a_bare_string_is_refused(self):
        for arguments in ({"paths": "links"}, {"paths": [self.root], "include": "*.json"},
                          {"paths": [self.root], "exclude": "*.json"}):
            with self.subTest(arguments=arguments), self.assertRaises(TypeError):
                discovery.collect(**arguments)

    def test_unreadable_directory_is_not_silently_empty(self):
        with patch.object(Path, "iterdir", side_effect=PermissionError("test access denied")):
            result = discovery.collect([self.root])
        self.assertEqual([p.code for p in result.problems], ["IO"])

    def test_an_empty_selection_and_files_without_annotations_are_errors(self):
        for paths in ([], [self.root]):
            with self.subTest(paths=paths):
                result = discovery.collect(paths)
                self.assertEqual([p.code for p in result.problems], ["NO_ANNOTATIONS"])
        first = self.raw("empty.jsonl", "\n \t\r\n")
        second = self.raw("empty.ndjson", "")
        result = discovery.collect([first, second])
        self.assertEqual([p.code for p in result.problems], ["NO_ANNOTATIONS"])
        self.write("valid.json", annotation())
        self.assertEqual(discovery.collect([self.root]).problems, [])

    def test_symlink_loops_and_escapes_are_skipped_but_explicit_links_error(self):
        good = self.write("good.json", annotation())
        link = self.root / "alias.json"
        self.symlink(link, good)
        self.symlink(self.root / "loop", self.root, directory=True)
        self.symlink(self.root / "broken.json", self.root / "absent")
        result = discovery.collect([self.root])
        self.assertEqual(result.problems, [])
        self.assertEqual(result.files, [good])
        explicit = discovery.collect([link])
        self.assertEqual([p.code for p in explicit.problems], ["SYMLINK"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX named pipes")
    def test_selected_nonregular_files_are_reported_without_reading(self):
        fifo = self.root / "pipe.json"
        os.mkfifo(fifo)
        result = discovery.collect([self.root])
        self.assertEqual([p.code for p in result.problems], ["PATH"])
        self.assertEqual(result.files, [])
        self.assertEqual([p.code for p in discovery.collect([fifo]).problems], ["PATH"])

    def test_discovery_performs_no_network_access(self):
        value = annotation()
        value["subject"][0]["uri"] = "https://example.invalid/book.pdf"
        path = self.write("link.json", value)
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")), \
             patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            result = discovery.collect([path])
        self.assertEqual(result.problems, [])
        self.assertEqual(companion.validate(result.records[0].annotation), [])


if __name__ == "__main__":
    unittest.main()
