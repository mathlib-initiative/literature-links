"""One informal–formal association per annotation, with offline validation.

``companion`` defines the current unversioned format and its strict JSON codec.
``discovery`` reads complete annotations from selected files and directories.
``migration`` explicitly projects original v1 data into the current format.

The retained ``validate``, ``ids``, and ``vocab`` modules implement legacy v1.
``schemacheck`` is the limited, dependency-free evaluator used by both schemas;
its public API is not a general-purpose JSON Schema implementation. See the
specification and compatibility guide in docs/ for the format boundaries.

Submodules are not imported eagerly. Each declares its public names in __all__.
"""
from __future__ import annotations

#: The public API (README.md): the version and the public
#: modules, each of which states its own names in its ``__all__``.  Listing the
#: modules does not import them; ``from formal_companion_annotations import *``
#: does.
__all__ = ["__version__", "ids", "schemacheck", "validate", "vocab", "companion", "migration", "cli", "discovery"]

__version__ = "2.0.0a2"
