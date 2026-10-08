"""``python -m formal_companion_annotations``: the command, as the console script runs it."""
from __future__ import annotations

import sys

from .cli import main

__all__: list[str] = []

if __name__ == "__main__":
    sys.exit(main())
