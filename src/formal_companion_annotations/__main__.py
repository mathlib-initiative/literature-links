"""``python -m formal_companion_annotations``: the command, as the console script runs it."""
from __future__ import annotations

import sys

from .cli import main

#: An entry point, not an API: nothing here is public (use ``cli.main``).
__all__: list[str] = []

if __name__ == "__main__":
    sys.exit(main())
