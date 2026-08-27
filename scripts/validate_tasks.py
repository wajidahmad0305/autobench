"""CLI: validate every task_*.json under tasks/ against the schema.

Usage: python scripts/validate_tasks.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autobench.schema import validate_all_tasks  # noqa: E402


def main() -> int:
    try:
        specs = validate_all_tasks("tasks")
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    print(f"\n{len(specs)} task(s) validated successfully.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
