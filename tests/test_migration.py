"""Migration must report omissions and preserve semantics instead of guessing."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

if importlib.util.find_spec("formal_companion_annotations") is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from formal_companion_annotations.migration import MigrationError, migrate_v1

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "annotations"
EXTENSION = "org.mathlib-initiative.fca-v1"


def load(name: str = "web-passage") -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def exact_destination(doc: dict, declaration: str, href: str = "https://formal.example.org/decl") -> None:
    existing = [destination for destination in doc.get("destinations", [])
                if destination.get("declaration") != declaration]
    existing.append({"id": declaration + "@migration", "declaration": declaration,
                     "site": "doc_gen4", "href": href, "fragment": declaration, "resolution": "exact"})
    doc["destinations"] = sorted(existing, key=lambda destination: destination["id"])


def codes(result) -> set[str]:
    return {diagnostic["code"] for diagnostic in result.diagnostics}


def associations(result) -> list[dict]:
    return result.documents


class TestMigration(unittest.TestCase):
    def test_normalized_quote_and_alternatives_stay_generic(self):
        doc = load()
        result = migrate_v1(doc)
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0]["source"]["type"], "generic")
        location = associations(result)[0]["location"]
        self.assertEqual(location["target"], doc["locations"][0]["target"])
        self.assertEqual(location["text_layer"], doc["sources"][0]["text_layer"])
        self.assertIn("generic_locator", codes(result))

    def test_exact_destination_query_and_fragment_preserved(self):
        doc = load()
        doc["destinations"][0]["href"] = "https://formal.example.org/page?revision=7"
        result = migrate_v1(doc)
        self.assertEqual(associations(result)[0]["target"],
                         "https://formal.example.org/page?revision=7#Ideal.IsPrime")

    def test_unresolved_declarations_do_not_get_invented_urls(self):
        result = migrate_v1(load())
        unresolved = {diagnostic["record_id"] for diagnostic in result.diagnostics
                      if diagnostic["code"] == "unresolved_target"}
        self.assertIn("passage-f6ebb863/key/Ideal.span_singleton_prime", unresolved)
        self.assertIn("passage-lead-definition/attributed/Ideal.IsPrime.ne_top'", unresolved)
        self.assertEqual(len(associations(result)), 1)

    def test_full_archive_is_equal_and_independent(self):
        doc = load("mixed")
        before = deepcopy(doc)
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(doc, before)
        self.assertEqual(result.original, before)
        result.original["items"][0]["title"] = "Changed archive"
        result.documents[0]["source"]["extensions"][EXTENSION]["source"]["title"] = "Changed projection"
        self.assertEqual(doc, before)

    def test_legacy_graph_metadata_is_reported_as_archived(self):
        result = migrate_v1(load("mixed"), target_base="https://formal.example.org/")
        self.assertIn("original_archived", codes(result))
        archived = {diagnostic["record_type"] for diagnostic in result.diagnostics
                    if diagnostic["code"] == "metadata_archived"}
        self.assertTrue({"verdicts", "changelog", "provenance", "declarations"} <= archived)
        self.assertIn("orphaned_link", codes(result))
        self.assertIn("cluster_link", codes(result))

    def test_relative_destination_requires_known_base(self):
        doc = load()
        doc["destinations"][0]["href"] = "Mathlib/Ideal.html"
        missing = migrate_v1(doc)
        self.assertEqual(missing.documents, [])
        self.assertIn("relative_target_without_base", codes(missing))
        resolved = migrate_v1(doc, target_base="https://formal.example.org/docs/")
        self.assertEqual(associations(resolved)[0]["target"],
                         "https://formal.example.org/docs/Mathlib/Ideal.html#Ideal.IsPrime")

    def test_fallback_is_not_promoted_to_exact_target(self):
        doc = load()
        doc["destinations"][0]["resolution"] = "fallback"
        doc["destinations"][0]["fallback_label"] = "module page only"
        doc["destinations"][0].pop("fragment")
        result = migrate_v1(doc)
        self.assertEqual(result.documents, [])
        self.assertIn("fallback_destination", codes(result))

    def test_simple_css_maps_to_html(self):
        doc = load()
        doc["locations"][0]["target"] = {"source": doc["sources"][0]["id"],
                                         "selector": [{"type": "CssSelector", "value": "#definition"}]}
        result = migrate_v1(doc)
        self.assertEqual(result.documents[0]["source"]["type"], "html")
        self.assertEqual(associations(result)[0]["location"], {"css": "#definition"})

    def test_simple_html_fragment_maps_to_html(self):
        doc = load()
        doc["locations"][0]["target"] = {"source": doc["sources"][0]["id"], "selector": [{
            "type": "FragmentSelector", "conformsTo": "http://tools.ietf.org/rfc/rfc3236", "value": "definition"}]}
        self.assertEqual(associations(migrate_v1(doc))[0]["location"], {"fragment": "definition"})

    def test_ambiguous_percent_encoding_remains_generic(self):
        doc = load()
        doc["locations"][0]["target"] = {"source": doc["sources"][0]["id"], "selector": [{
            "type": "FragmentSelector", "conformsTo": "http://tools.ietf.org/rfc/rfc3236", "value": "a%20b"}]}
        self.assertEqual(migrate_v1(doc).documents[0]["source"]["type"], "generic")

    def test_legacy_html_fragment_controls_remain_generic_without_loss(self):
        from formal_companion_annotations import companion, validate
        for control in ("\u0000", "\u0007", "\u007f", "\u0080", "\u009f"):
            with self.subTest(control=repr(control)):
                doc = load()
                target = {"source": doc["sources"][0]["id"], "selector": [{
                    "type": "FragmentSelector", "conformsTo": "http://tools.ietf.org/rfc/rfc3236",
                    "value": "definition" + control}]}
                doc["locations"][0]["target"] = target
                self.assertEqual(validate.check(doc).problems, [])
                result = migrate_v1(doc)
                self.assertEqual(len(result.documents), 1)
                annotation = result.documents[0]
                self.assertEqual(annotation["source"]["type"], "generic")
                self.assertEqual(annotation["location"]["target"], target)
                self.assertEqual(companion.validate(annotation), [])
                self.assertEqual(result.original, doc)
                self.assertIn("generic_locator", codes(result))

    def test_pdf_page_maps_but_region_does_not_assume_rotation(self):
        doc = load("ledger-graph")
        exact_destination(doc, "Notes.Box")
        result = migrate_v1(doc)
        self.assertEqual({document["source"]["type"] for document in result.documents}, {"generic"})
        region = associations(result)[0]["location"]["target"]["selector"][0]
        self.assertEqual(region["type"], "PdfRegionSelector")
        doc["locations"][0]["target"]["selector"] = [{"type": "FragmentSelector",
            "conformsTo": "http://tools.ietf.org/rfc/rfc8118", "value": "page=7"}]
        result = migrate_v1(doc)
        self.assertEqual({document["source"]["type"] for document in result.documents}, {"pdf", "generic"})
        self.assertEqual(result.documents[0]["location"], {"page": 7})

    def test_tex_lines_convert_half_open_zero_based_to_inclusive_one_based(self):
        doc = load("tex-lines")
        exact_destination(doc, "Blueprint.sum_comm")
        location = next(location for location in doc["locations"] if location["id"] == "theorem-1.3@tex")
        location["target"]["selector"] = [location["target"]["selector"][0]]
        result = migrate_v1(doc)
        self.assertEqual(result.documents[0]["source"]["type"], "latex")
        self.assertEqual(result.documents[0]["source"]["uri"], "blueprint/src/chapter1.tex")
        self.assertEqual(associations(result)[0]["location"], {"lines": [42, 47]})

    def test_link_page_takes_priority_over_item_location(self):
        doc = load("mixed")
        link = next(link for link in doc["links"] if link["id"] == "definition-1.1/key/Notes.Box")
        link["pages"] = {"first": 8, "basis": "physical", "anchor": "own"}
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(associations(result)[0]["location"], {"page": 8})

    def test_printed_page_requires_explicit_offset_and_span_stays_generic(self):
        doc = load("mixed")
        link = next(link for link in doc["links"] if link["id"] == "definition-1.1/key/Notes.Box")
        link["pages"] = {"first": 3, "basis": "printed", "anchor": "own"}
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(associations(result)[0]["location"], {"page": 7})
        link["pages"]["last"] = 4
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(associations(result)[0]["location"]["pages"], link["pages"])

    def test_refined_css_is_not_broadened_to_parent_element(self):
        doc = load()
        doc["locations"][0]["target"] = {"source": doc["sources"][0]["id"], "selector": [{
            "type": "CssSelector", "value": "#definition", "refinedBy": {
                "type": "TextPositionSelector", "start": 1, "end": 5}}]}
        result = migrate_v1(doc)
        self.assertEqual(result.documents[0]["source"]["type"], "generic")
        self.assertIn("refinedBy", associations(result)[0]["location"]["target"]["selector"][0])

    def test_tex_length_checks_and_alternatives_are_not_dropped(self):
        doc = load("tex-lines")
        exact_destination(doc, "Blueprint.finSum")
        result = migrate_v1(doc)
        self.assertEqual(result.documents[0]["source"]["type"], "generic")
        self.assertEqual(len(associations(result)[0]["location"]["target"]["selector"]), 2)

    def test_missing_source_uri_needs_explicit_mapping(self):
        doc = load("site-pages")
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(result.documents, [])
        self.assertIn("missing_source_uri", codes(result))
        result = migrate_v1(doc, source_uris={"book-pdf": "notes.pdf"}, target_base="https://formal.example.org/")
        self.assertTrue(result.documents)
        self.assertEqual(result.documents[0]["source"]["uri"], "notes.pdf")

    def test_unlocated_items_are_not_broadened_to_the_entire_source(self):
        doc = load("web-passage")
        exact_destination(doc, "Ideal.span_singleton_prime")
        result = migrate_v1(doc)
        for annotation in associations(result):
            self.assertIn("location", annotation)
        unknown = next(annotation for annotation in associations(result)
                       if annotation["extensions"][EXTENSION]["item_id"] == "passage-f6ebb863")
        self.assertIn("item", unknown["location"])

    def test_original_link_relation_and_provenance_references_survive(self):
        result = migrate_v1(load())
        metadata = associations(result)[0]["extensions"][EXTENSION]
        self.assertEqual(metadata["role"], "key")
        self.assertEqual(metadata["relation"], "exact")
        self.assertEqual(metadata["confidence"], 0.9)
        self.assertEqual(metadata["provenance_id"], "prov-agents")

    def test_results_are_deterministic(self):
        doc = load("mixed")
        self.assertEqual(migrate_v1(doc, target_base="https://formal.example.org/"),
                         migrate_v1(doc, target_base="https://formal.example.org/"))

    def test_each_location_and_destination_pair_is_an_independent_record(self):
        doc = load("ledger-graph")
        exact_destination(doc, "Notes.Box")
        second = deepcopy(next(destination for destination in doc["destinations"]
                               if destination.get("declaration") == "Notes.Box"))
        second["id"] += "-second"
        second["href"] = "https://another.example.org/decl"
        doc["destinations"].append(second)
        doc["destinations"].sort(key=lambda destination: destination["id"])
        result = migrate_v1(doc)
        self.assertEqual(len(result.documents), 4)
        pairs = [(annotation["extensions"][EXTENSION]["location_id"], annotation["target"])
                 for annotation in result.documents]
        self.assertEqual(len(set(pairs)), 4)
        self.assertEqual([pair[0] for pair in pairs],
                         ["definition-1.1@p007", "definition-1.1@p007",
                          "definition-1.1@p007-2", "definition-1.1@p007-2"])
        for annotation in result.documents:
            self.assertNotIn("annotations", annotation)
            self.assertEqual(annotation["source"]["extensions"][EXTENSION]["source"], doc["sources"][0])
        result.documents[0]["source"]["extensions"][EXTENSION]["source"]["title"] = "Changed first copy"
        self.assertEqual(result.documents[1]["source"]["extensions"][EXTENSION]["source"], doc["sources"][0])
        result.documents[0]["location"]["target"]["selector"].clear()
        self.assertTrue(result.documents[1]["location"]["target"]["selector"])

    def test_different_sources_and_modes_have_no_shared_wrapper(self):
        doc = load("mixed")
        doc["links"].append({"id": "passage-bcffcbba/key/Notes.Box", "item": "passage-bcffcbba",
                             "declaration": "Notes.Box", "role": "key", "provenance": "prov-curation"})
        doc["links"].sort(key=lambda link: link["id"])
        doc["locations"].append({"id": "passage-bcffcbba@html", "items": ["passage-bcffcbba"],
                                 "provenance": "prov-curation", "target": {"source": "notes-errata",
                                 "selector": [{"type": "CssSelector", "value": "#correction"}]}})
        doc["locations"].sort(key=lambda location: location["id"])
        result = migrate_v1(doc, target_base="https://formal.example.org/")
        self.assertEqual(len(result.documents), 3)
        self.assertEqual([annotation["source"]["type"] for annotation in result.documents],
                         ["html", "generic", "generic"])
        self.assertEqual(result.documents[0]["source"]["uri"], "https://notes.example.org/errata.html")
        self.assertEqual(result.documents[0]["location"], {"css": "#correction"})
        self.assertTrue(all(annotation["source"]["uri"].endswith("elementary-sets.pdf")
                            for annotation in result.documents[1:]))

    def test_no_fetching(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("must stay offline")):
            self.assertTrue(migrate_v1(load()).documents)

    def test_invalid_input_is_rejected_before_projection(self):
        with self.assertRaisesRegex(MigrationError, "Invalid v1 document"):
            migrate_v1(load("invalid-dangling-reference"))
        with self.assertRaisesRegex(MigrationError, "Invalid v1 document"):
            migrate_v1({"version": 2, "source": {"type": "pdf", "uri": "notes.pdf"}, "annotations": []})

    def test_pr_release_candidate_is_explicitly_unsupported(self):
        # Its marker identifies a distinct dialect, even if other fields happen
        # to overlap. The legacy validator must not be applied after renaming it.
        doc = {"schema": "formal-companion/annotations", "schema_version": "1.0",
               "companion": {"name": "Synthetic release candidate"},
               "sources": [], "items": [], "declarations": [], "links": [], "provenance": []}
        before = deepcopy(doc)
        with patch("formal_companion_annotations.migration.legacy.check",
                   side_effect=AssertionError("wrong validator must not run")):
            with self.assertRaisesRegex(MigrationError, "Unsupported PR #2 release-candidate dialect"):
                migrate_v1(doc)
        self.assertEqual(doc, before)

    def test_non_json_extension_values_fail_before_traversal(self):
        for value in (float("inf"), {1: "integer key"}, {1, 2}):
            doc = load()
            doc["x_extension"] = value
            with self.subTest(value=value), self.assertRaisesRegex(MigrationError, "Invalid v1 JSON"):
                migrate_v1(doc)

    def test_source_path_is_encoded_as_path_not_fragment_or_query(self):
        doc = load("tex-lines")
        exact_destination(doc, "Blueprint.sum_comm")
        doc["sources"][0]["path"] = "chapter:1/50%#theorem?.tex"
        result = migrate_v1(doc)
        self.assertEqual(result.documents[0]["source"]["uri"], "chapter%3A1/50%25%23theorem%3F.tex")

    def test_all_projected_documents_pass_v2_validation(self):
        from formal_companion_annotations import companion
        for path in EXAMPLES.glob("*.json"):
            if path.name.startswith("invalid-"):
                continue
            doc = json.loads(path.read_text(encoding="utf-8"))
            mappings = {source["id"]: f"https://sources.example.org/{index}" for index, source in enumerate(doc["sources"])}
            result = migrate_v1(doc, source_uris=mappings, target_base="https://formal.example.org/")
            for projected in result.documents:
                with self.subTest(example=path.name, mode=projected["source"]["type"]):
                    self.assertEqual(companion.validate(projected), [])

    def test_invalid_configuration_is_rejected(self):
        for mapping in ({"absent": "notes.pdf"}, {"wiki-prime-ideal": "bad uri"}, []):
            with self.subTest(mapping=mapping), self.assertRaises(MigrationError):
                migrate_v1(load(), source_uris=mapping)
        for base in ("relative/path", "https://bad uri.example/", "", "https://[bad"):
            with self.subTest(base=base), self.assertRaises(MigrationError):
                migrate_v1(load(), target_base=base)

    def test_unparseable_legacy_destination_is_reported(self):
        doc = load()
        doc["destinations"][0]["href"] = "https://[bad"
        result = migrate_v1(doc)
        self.assertEqual(result.documents, [])
        self.assertIn("unusable_destination", codes(result))

    def test_legacy_destination_with_c1_control_is_reported(self):
        doc = load()
        doc["destinations"][0]["href"] = "https://formal.example.org/a\u0080"
        result = migrate_v1(doc)
        self.assertEqual(result.documents, [])
        self.assertIn("unusable_destination", codes(result))
        self.assertEqual(result.original, doc)

    def test_legacy_source_with_c1_control_is_reported(self):
        doc = load()
        doc["sources"][0]["url"] = "https://sources.example.org/a\u0080"
        result = migrate_v1(doc)
        self.assertEqual(result.documents, [])
        self.assertIn("missing_source_uri", codes(result))
        self.assertEqual(result.original, doc)

    def test_every_existing_example_has_a_lossless_archive(self):
        for path in EXAMPLES.glob("*.json"):
            if path.name.startswith("invalid-"):
                continue
            with self.subTest(example=path.name):
                doc = json.loads(path.read_text(encoding="utf-8"))
                result = migrate_v1(doc)
                self.assertEqual(result.original, doc)
                for annotation in result.documents:
                    self.assertIn("source", annotation)
                    self.assertIn("target", annotation)
                    self.assertNotIn("annotations", annotation)


if __name__ == "__main__":
    unittest.main()
