#!/usr/bin/env python
"""Rebuild the AI knowledge-base index from scratch.

Usage (any of the following, all from the project root):
    python scripts/reindex_kb.py             # clear + reindex
    python scripts/reindex_kb.py --no-clear  # keep existing rows, upsert
    python -m ai.ingestion.indexer           # equivalent, no script needed
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `import ai` works no matter
# where this script was launched from (e.g. `python scripts/reindex_kb.py`).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ingestion.indexer import reindex  # noqa: E402  (post-path-fix import)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = list(sys.argv[1:] if argv is None else argv)
    clear_first = "--no-clear" not in args

    report = reindex(clear_first=clear_first, progress=True)
    print(
        f"Done. Indexed {report['chunks']} chunks from "
        f"{report['documents']} documents in {report['elapsed_seconds']}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())