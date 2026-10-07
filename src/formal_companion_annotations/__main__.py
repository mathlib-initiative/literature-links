"""Run the current CLI, retaining historical bare-file validator commands."""
from __future__ import annotations

import sys

from . import cli, validate

#: An entry point, not an API: use ``cli.main`` or ``validate.main``.
__all__: list[str] = []

if __name__ == "__main__":
    arguments = sys.argv[1:]
    current = not arguments or arguments[0] in {
        "validate", "scan", "format", "migrate-v1", "-h", "--help", "--version",
    }
    sys.exit(cli.main(arguments) if current else validate.main(arguments))
