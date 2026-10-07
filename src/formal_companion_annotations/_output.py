"""Encoding-stable output for the command-line JSON protocols."""
from __future__ import annotations

import sys


def write_json(text: str) -> None:
    """Write serialized UTF-8/LF JSON without the terminal's encoding policy."""
    binary = getattr(sys.stdout, "buffer", None)
    if binary is None:
        # Embedders and tests may supply a text-only stream such as StringIO.
        sys.stdout.write(text)
    else:
        binary.write(text.encode("utf-8"))
