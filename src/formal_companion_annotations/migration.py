"""Conservative, offline projection of v1 graphs into single annotations.

The complete v1 input travels separately as ``MigrationResult.original``.  The
documents are useful associations, not a replacement for the archived graph.
Unresolved formal destinations are reported, never synthesized from Lean names.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from . import companion, validate as legacy

__all__ = ["MigrationError", "MigrationResult", "migrate_v1"]

_EXTENSION = "org.mathlib-initiative.fca-v1"
_PROFILE = "urn:formal-companion:legacy-v1:locator"
_PDF_GRAMMARS = {"http://tools.ietf.org/rfc/rfc8118", "http://tools.ietf.org/rfc/rfc3778"}
_TEXT_GRAMMAR = "http://tools.ietf.org/rfc/rfc5147"
_HTML_GRAMMAR = "http://tools.ietf.org/rfc/rfc3236"


class MigrationError(ValueError):
    """Invalid v1 input or invalid explicit URI mappings."""


@dataclass
class MigrationResult:
    """Projected documents, structured diagnostics, and an independent archive."""

    documents: list[dict[str, Any]]
    diagnostics: list[dict[str, Any]]
    original: dict[str, Any]


def _reference(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and not any(
        char.isspace() or ord(char) < 32 or 127 <= ord(char) <= 159 for char in value
    ) and re.search(r"%(?![0-9a-fA-F]{2})", value) is None


def _mode(source: dict[str, Any]) -> str:
    kind, media = source["kind"], source.get("media_type")
    if kind == "pdf" or media == "application/pdf":
        return "pdf"
    if kind == "tex":
        return "latex"
    if kind == "web" or media in {"text/html", "application/xhtml+xml"}:
        return "html"
    return "generic"


def _native_selector(source: dict[str, Any], target: dict[str, Any]) -> dict[str, Any] | None:
    """Translate only an entire selector with identical, known semantics."""
    selectors = target["selector"]
    if len(selectors) != 1 or target.get("state"):
        return None
    selector = selectors[0]
    if "refinedBy" in selector:
        return None
    mode = _mode(source)
    if selector["type"] == "CssSelector" and mode == "html":
        return {"css": selector["value"]}
    if selector["type"] != "FragmentSelector":
        # Quote normalization and PDF rotation cannot be inferred from v1.
        return None
    grammar, value = selector.get("conformsTo"), selector["value"]
    if mode == "pdf" and grammar in _PDF_GRAMMARS:
        match = re.fullmatch(r"page=([1-9][0-9]*)", value)
        if match:
            return {"page": int(match[1])}
    if mode == "latex" and grammar == _TEXT_GRAMMAR:
        match = re.fullmatch(r"line=([0-9]+),([0-9]+)", value)
        if match:
            # RFC 5147 uses zero-based, half-open line boundaries.
            return {"lines": [int(match[1]) + 1, int(match[2])]}
    if (mode == "html" and grammar == _HTML_GRAMMAR and "%" not in value
            and not value.startswith("#") and _reference(value)):
        # Legacy HTML IDs admit some control characters that the atomic core
        # excludes. Preserve those selectors generically instead of aborting.
        return {"fragment": value}
    return None


def _native_pages(source: dict[str, Any], pages: dict[str, Any]) -> dict[str, Any] | None:
    if _mode(source) != "pdf" or pages.get("anchor", "own") != "own":
        return None
    if pages.get("last", pages["first"]) != pages["first"]:
        return None
    page = pages["first"]
    if pages["basis"] == "printed":
        if "printed_page_offset" not in source:
            return None
        page += source["printed_page_offset"]
    if page < 1:
        return None
    return {"page": page}


def _locators(
    link: dict[str, Any], item: dict[str, Any], locations: list[dict[str, Any]],
    source: dict[str, Any],
) -> list[tuple[str, dict[str, Any], str | None]]:
    """Choose link-specific anchors before item anchors; never broaden silently."""
    if "locations" in link:
        selected = [location for location in locations if location["id"] in link["locations"]]
    elif "pages" in link:
        selected = []
    else:
        selected = [location for location in locations if item["id"] in location["items"]]
    if selected:
        result = []
        for location in selected:
            native = _native_selector(source, location["target"])
            if native is not None:
                result.append((_mode(source), native, location["id"]))
            else:
                opaque = {"profile": _PROFILE, "target": deepcopy(location["target"])}
                if "text_layer" in source:
                    opaque["text_layer"] = deepcopy(source["text_layer"])
                result.append(("generic", opaque, location["id"]))
        return result
    # An explicit empty location list cannot be changed into a different anchor.
    if "locations" not in link:
        if "pages" in link:
            pages = link["pages"]
            native = _native_pages(source, pages)
            return [(_mode(source), native, None)] if native is not None else [
                ("generic", {"profile": _PROFILE, "pages": deepcopy(pages)}, None)
            ]
        if "quote" not in item and "pages" in item:
            native = _native_pages(source, item["pages"])
            if native is not None:
                return [(_mode(source), native, None)]
    # Unlocated numbered items are not the entire document. Keep their identity
    # opaque rather than treating absence of a selector as a whole-source claim.
    return [("generic", {"profile": _PROFILE, "item": deepcopy(item)}, None)]


def migrate_v1(
    document: dict[str, Any], *, source_uris: dict[str, str] | None = None,
    target_base: str | None = None,
) -> MigrationResult:
    """Project valid original v1 links into independent v2 annotation records.

    ``source_uris`` maps original source IDs to concrete resource references.
    It overrides missing or unsuitable source addresses. ``target_base`` is an
    explicit absolute base for relative formal destinations; without one their
    resolution context is unknown and they remain archived with a diagnostic.
    Sources are visited in input order. Annotation order then follows links,
    locations, and destinations from the original arrays. Every association gets
    its own record; the return list is an API result, not a companion schema.
    The distinct release-candidate dialect from PR #2 is not supported.
    No source, repository, schema, or destination is fetched.
    """
    try:
        companion.dumps(document)
    except companion.LoadError as exc:
        raise MigrationError(f"Invalid v1 JSON value: {exc}") from exc
    if isinstance(document, dict) and document.get("schema") == "formal-companion/annotations":
        raise MigrationError(
            "Unsupported PR #2 release-candidate dialect: formal-companion/annotations. "
            "migrate_v1 supports only the original lean-companion/annotations format; "
            "the release candidate needs its own schema/rule validation and explicit "
            "source/target mappings. Renaming its schema identifier is not a migration."
        )
    if (not isinstance(document, dict) or document.get("schema") != "lean-companion/annotations"
            or "version" in document):
        raise MigrationError("Invalid v1 document: expected lean-companion/annotations legacy format")
    report = legacy.check(document)
    if report.problems:
        raise MigrationError("Invalid v1 document:\n" + "\n".join(report.problems))
    mappings = {} if source_uris is None else source_uris
    source_ids = {source["id"] for source in document["sources"]}
    if not isinstance(mappings, dict) or any(
        key not in source_ids or not _reference(value) for key, value in mappings.items()
    ):
        raise MigrationError("source_uris must map existing source IDs to nonempty URI/IRI references")
    if target_base is not None:
        try:
            valid_base = _reference(target_base) and bool(urlsplit(target_base).scheme)
        except ValueError:
            valid_base = False
        if not valid_base:
            raise MigrationError("target_base must be an absolute URI/IRI")

    diagnostics: list[dict[str, Any]] = []

    def diagnose(code: str, message: str, kind: str = "document", record_id: str | None = None,
                 severity: str = "warning") -> None:
        diagnostic: dict[str, Any] = {"code": code, "severity": severity, "message": message,
                                     "record_type": kind}
        if record_id is not None:
            diagnostic["record_id"] = record_id
        diagnostics.append(diagnostic)

    diagnose("original_archived", "The complete v1 graph is retained in original; v2 documents are projections.",
             severity="info")
    for warning in report.warnings:
        diagnose("legacy_validation_warning", warning)
    items = {item["id"]: item for item in document["items"]}
    destinations = document.get("destinations", [])
    locations = document.get("locations", [])
    documents: list[dict[str, Any]] = []
    emitted_items: set[str] = set()
    used_destinations: set[str] = set()

    for source in document["sources"]:
        # TeX URL may identify a repository, while path identifies its actual file.
        uri = mappings.get(source["id"])
        if uri is None:
            # A repository path is not already URI-escaped: '#' and '?' can be
            # literal filename characters, and ':' in its first segment is legal.
            uri = quote(source["path"], safe="/") if "path" in source else source.get("url")
        source_links = [(index, link) for index, link in enumerate(document["links"])
                        if items[link["item"]]["source"] == source["id"]]
        if source.get("scope") == "site":
            if source_links:
                diagnose("source_not_concrete", "Site-wide source needs an adapter that splits individual pages.",
                         "source", source["id"])
            continue
        if not _reference(uri):
            if source_links:
                diagnose("missing_source_uri", "No usable concrete resource reference; supply source_uris for this source.",
                         "source", source["id"])
            continue
        if source_links and not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", uri):
            diagnose("relative_source_context", "Relative source URI keeps its original resolution context; relocate with an explicit source_uris mapping.",
                     "source", source["id"])
        for link_index, link in source_links:
            if link.get("orphaned"):
                diagnose("orphaned_link", "Retired formal target remains archived, without a live association.",
                         "link", link["id"])
                continue
            if "declaration" not in link:
                diagnose("cluster_link", "Cluster membership is not a direct formal destination; link remains archived.",
                         "link", link["id"])
                continue
            targets: list[tuple[str, str]] = []
            for destination in destinations:
                if destination.get("declaration") != link["declaration"]:
                    continue
                if destination["resolution"] != "exact":
                    diagnose("fallback_destination", "Fallback destination is not promoted to an exact formal target.",
                             "destination", destination["id"])
                    continue
                try:
                    href = destination["href"]
                    if "fragment" in destination:
                        parts = urlsplit(href)
                        href = urlunsplit((*parts[:4], destination["fragment"]))
                    if not urlsplit(href).scheme:
                        if target_base is None:
                            diagnose("relative_target_without_base", "Relative formal destination needs an explicit target_base.",
                                     "destination", destination["id"])
                            continue
                        href = urljoin(target_base, href)
                    usable = _reference(href) and bool(urlsplit(href).scheme)
                except ValueError:
                    usable = False
                if not usable:
                    diagnose("unusable_destination", "Destination is not a usable absolute URI/IRI after resolution.",
                             "destination", destination["id"])
                    continue
                targets.append((destination["id"], href))
            if not targets:
                diagnose("unresolved_target", "No usable exact formal destination; no URL was inferred from the declaration.",
                         "link", link["id"])
                continue
            item = items[link["item"]]
            for location_index, (mode, locator, location_id) in enumerate(_locators(link, item, locations, source)):
                if mode == "generic":
                    diagnose("generic_locator", "Legacy locator semantics are preserved opaquely; generic support is required.",
                             "location" if location_id else "item", location_id or item["id"])
                for target_index, (destination_id, href) in enumerate(targets):
                    metadata = {"link_id": link["id"], "item_id": item["id"],
                                "destination_id": destination_id, "role": link["role"],
                                "provenance_id": link["provenance"]}
                    if location_id is not None:
                        metadata["location_id"] = location_id
                    for key in ("relation", "note", "sub", "confidence"):
                        if key in link:
                            metadata[key] = deepcopy(link[key])
                    documents.append({
                        "version": 2,
                        "source": {"type": mode, "uri": uri,
                                   "extensions": {_EXTENSION: {"source": deepcopy(source)}}},
                        "id": f"v1-link-{link_index + 1}-location-{location_index + 1}-target-{target_index + 1}",
                        "location": deepcopy(locator), "target": href, "extensions": {_EXTENSION: metadata},
                    })
                    emitted_items.add(item["id"])
                    used_destinations.add(destination_id)

    for item in document["items"]:
        if item["id"] not in emitted_items:
            diagnose("item_without_annotation", "Item has no exported association; it remains intact in original.",
                     "item", item["id"])
    for category in ("companion", "sources", "items", "links", "locations", "declarations", "provenance",
                     "artifacts", "clusters", "memberships", "verdicts", "unattributed", "changelog", "snippets"):
        if document.get(category):
            diagnose("metadata_archived", f"{category} remains in original and is not part of the small core.",
                     category, severity="info")
    for destination in destinations:
        if destination["id"] not in used_destinations:
            diagnose("destination_not_exported", "Destination remains in original without an exported association.",
                     "destination", destination["id"], severity="info")
    for converted in documents:
        problems = companion.validate(converted)
        if problems:
            raise MigrationError("Projected document is not valid v2:\n" + "\n".join(problems))
    return MigrationResult(documents, diagnostics, deepcopy(document))
