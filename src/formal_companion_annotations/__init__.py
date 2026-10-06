"""Small companion documents, with legacy v1 annotation compatibility.

The v2 format is specified in docs/companion-v2.md and implemented by
``companion``. The legacy format is specified in docs/annotations.md; its JSON Schema is
schema/annotations-v1.schema.json (schema_version "1.0"), shipped inside this
package as ``schema/annotations-v1.schema.json``.  ``validate`` is the checker
(and a CLI) and the RFC 8785 canonicaliser, ``schemacheck`` the small JSON
Schema evaluator it runs, because this package is standard library only,
``ids`` the mechanical id rules of docs/annotations.md section 5 (statement-hash
ids for anonymous declarations, and quote- or page-and-title-hash ids for
unnumbered passages), and ``vocab`` the format's enums and id grammar.

Extracted from the formal-companion skill (scripts/annotations/ and the
annotation block of scripts/cflib/vocab.py); CHANGELOG.md names the commits.
The submodules are not imported here, so ``python3 -m
formal_companion_annotations.validate`` runs without a double import.
"""
from __future__ import annotations

#: The public API (README.md): the version and the public
#: modules, each of which states its own names in its ``__all__``.  Listing the
#: modules does not import them; ``from formal_companion_annotations import *``
#: does.
__all__ = ["__version__", "ids", "schemacheck", "validate", "vocab", "companion", "migration", "cli"]

__version__ = "2.0.0a1"
