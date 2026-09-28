"""``python3 -m formal_companion_annotations``: the validator, as the console script runs it."""
from __future__ import annotations

import sys

from .validate import main

if __name__ == "__main__":
    sys.exit(main())
