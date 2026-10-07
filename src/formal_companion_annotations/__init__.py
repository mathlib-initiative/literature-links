"""One informal–formal association per annotation, with offline validation.

``companion`` defines the format and its strict JSON codec.
``discovery`` reads annotations from selected files and directories.
``cli`` runs the ``validate`` and ``scan`` commands.
``schemacheck`` is the small JSON Schema evaluator that ``companion`` uses;
it is not a general-purpose JSON Schema implementation.

Submodules are not imported eagerly. Each declares its public names in __all__.
"""
from __future__ import annotations

#: The public API: the version and the public modules, each of which states its
#: own names in its ``__all__``.  Listing the modules does not import them;
#: ``from formal_companion_annotations import *`` does.
__all__ = ["__version__", "schemacheck", "companion", "cli", "discovery"]

__version__ = "2.0.0a2"
